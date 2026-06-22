from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from sqlalchemy import func, inspect, select, text
from sqlalchemy.orm import Session

from app.config import BASE_DIR, Settings, get_settings
from app.models import Site, SiteSection
from app.services.storage import prepare_storage


@dataclass(frozen=True)
class DoctorCheck:
    name: str
    status: str
    message: str


@dataclass(frozen=True)
class DoctorReport:
    checks: list[DoctorCheck]

    @property
    def failed_count(self) -> int:
        return sum(check.status == "fail" for check in self.checks)

    @property
    def warning_count(self) -> int:
        return sum(check.status == "warn" for check in self.checks)

    @property
    def ok_count(self) -> int:
        return sum(check.status == "ok" for check in self.checks)


def run_system_doctor(
    db: Session,
    settings: Settings | None = None,
) -> DoctorReport:
    settings = settings or get_settings()
    checks = [
        check_database(db),
        check_database_schema(db),
        check_security_defaults(settings),
        check_storage(settings),
        check_sites_config(),
        check_imported_sources(db),
        check_openclaw(settings),
        check_windows_scripts(),
    ]
    return DoctorReport(checks=checks)


def check_database(db: Session) -> DoctorCheck:
    try:
        db.execute(text("select 1")).scalar_one()
        return DoctorCheck("database", "ok", "数据库连接正常")
    except Exception as exc:
        return DoctorCheck("database", "fail", f"数据库连接失败：{type(exc).__name__}: {exc}")


def check_database_schema(db: Session) -> DoctorCheck:
    required_tables = {
        "users",
        "sites",
        "site_sections",
        "crawl_runs",
        "announcements",
        "attachments",
        "attachment_versions",
        "change_logs",
        "notification_logs",
    }
    try:
        existing_tables = set(inspect(db.get_bind()).get_table_names())
    except Exception as exc:
        return DoctorCheck(
            "database_schema", "fail", f"读取数据库表失败：{type(exc).__name__}: {exc}"
        )
    missing = sorted(required_tables - existing_tables)
    if missing:
        return DoctorCheck(
            "database_schema",
            "fail",
            f"数据库缺少核心表：{', '.join(missing)}；请执行 alembic upgrade head",
        )
    return DoctorCheck("database_schema", "ok", "数据库核心表完整")


def check_security_defaults(settings: Settings) -> DoctorCheck:
    warnings: list[str] = []
    if settings.admin_password == "change-me":
        warnings.append("ADMIN_PASSWORD 仍为默认值")
    if settings.app_secret_key == "change-me":
        warnings.append("APP_SECRET_KEY 仍为默认值")
    if warnings:
        return DoctorCheck("security", "warn", "；".join(warnings))
    return DoctorCheck("security", "ok", "后台密码和应用密钥已修改")


def check_storage(settings: Settings) -> DoctorCheck:
    try:
        storage = prepare_storage(settings)
        probe = storage.logs / ".doctor-write-test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return DoctorCheck("storage", "ok", f"storage 可写：{storage.root}")
    except Exception as exc:
        return DoctorCheck("storage", "fail", f"storage 不可写：{type(exc).__name__}: {exc}")


def check_sites_config() -> DoctorCheck:
    path = BASE_DIR / "configs" / "sites.yaml"
    if not path.exists():
        return DoctorCheck("sites_config", "fail", "未找到 configs/sites.yaml")
    return DoctorCheck("sites_config", "ok", "configs/sites.yaml 存在")


def check_imported_sources(db: Session) -> DoctorCheck:
    try:
        site_count = int(db.scalar(select(func.count(Site.id))) or 0)
        enabled_section_count = int(
            db.scalar(
                select(func.count(SiteSection.id))
                .join(Site, Site.id == SiteSection.site_id)
                .where(Site.enabled.is_(True))
                .where(SiteSection.enabled.is_(True))
            )
            or 0
        )
    except Exception as exc:
        return DoctorCheck("sources", "fail", f"来源统计失败：{type(exc).__name__}: {exc}")

    if site_count == 0 or enabled_section_count == 0:
        return DoctorCheck(
            "sources",
            "warn",
            "数据库尚未导入站点；请执行 zhengfudata import-sites --file configs/sites.yaml",
        )
    if enabled_section_count < 10:
        return DoctorCheck(
            "sources",
            "warn",
            f"启用栏目只有 {enabled_section_count} 个，V1 建议不少于 10 个",
        )
    return DoctorCheck(
        "sources", "ok", f"已导入站点 {site_count} 个，启用栏目 {enabled_section_count} 个"
    )


def check_openclaw(settings: Settings) -> DoctorCheck:
    if settings.openclaw_notify_mode == "cli":
        if not settings.wecom_notify_target_id:
            return DoctorCheck(
                "openclaw",
                "warn",
                "OPENCLAW_NOTIFY_MODE=cli，但 WECOM_NOTIFY_TARGET_ID 未配置；需要 group:<chatid>",
            )
        if not openclaw_gateway_reachable(settings.openclaw_dashboard_url):
            return DoctorCheck(
                "openclaw",
                "warn",
                "OPENCLAW_NOTIFY_MODE=cli，但 OpenClaw 控制台不可访问："
                f"{settings.openclaw_dashboard_url}",
            )
        return DoctorCheck(
            "openclaw",
            "ok",
            "OPENCLAW_NOTIFY_MODE=cli，OpenClaw 本机服务可访问，企微目标已配置",
        )
    if not settings.openclaw_webhook_url:
        return DoctorCheck(
            "openclaw",
            "warn",
            "OPENCLAW_WEBHOOK_URL 未配置；抓取可运行，但不会发送真实企微日报",
        )
    return DoctorCheck("openclaw", "ok", "OPENCLAW_WEBHOOK_URL 已配置")


def openclaw_gateway_reachable(url: str) -> bool:
    try:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return False
        with httpx.Client(timeout=3, trust_env=False) as client:
            response = client.get(url)
        return response.status_code < 500
    except Exception:
        return False


def check_windows_scripts() -> DoctorCheck:
    scripts = [
        "setup.ps1",
        "run-server.ps1",
        "run-daily-crawl.ps1",
        "validate-sources.ps1",
        "export-acceptance-report.ps1",
        "install-daily-task.ps1",
        "doctor.ps1",
    ]
    missing = [
        script for script in scripts if not (BASE_DIR / "scripts" / "windows" / script).exists()
    ]
    if missing:
        return DoctorCheck("windows_scripts", "fail", f"缺少 Windows 脚本：{', '.join(missing)}")
    return DoctorCheck("windows_scripts", "ok", "Windows 部署脚本完整")


def format_doctor_report(report: DoctorReport) -> str:
    lines = ["系统自检结果"]
    for check in report.checks:
        lines.append(f"[{check.status.upper()}] {check.name}: {check.message}")
    lines.append(
        f"summary ok={report.ok_count} warn={report.warning_count} fail={report.failed_count}"
    )
    return "\n".join(lines)
