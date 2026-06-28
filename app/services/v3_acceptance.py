from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session, selectinload

from app.config import Settings
from app.models import (
    Enterprise,
    EnterprisePersonnel,
    EnterpriseProject,
    EnterpriseQualification,
    QualificationStandard,
    QualificationStandardCondition,
)
from app.services.storage import prepare_storage


@dataclass(frozen=True)
class V3AcceptanceCheck:
    name: str
    status: str
    detail: str


@dataclass(frozen=True)
class V3AcceptanceReport:
    checks: list[V3AcceptanceCheck]
    path: str | None = None

    @property
    def failed_count(self) -> int:
        return sum(1 for check in self.checks if check.status == "fail")

    @property
    def passed_count(self) -> int:
        return sum(1 for check in self.checks if check.status == "ok")


def run_v3_acceptance_check(db: Session, settings: Settings) -> V3AcceptanceReport:
    checks = [
        check_tables(db),
        check_standard_write_and_read(db),
        check_enterprise_write_and_read(db),
    ]
    report = V3AcceptanceReport(checks=checks)
    path = write_v3_acceptance_report(report, settings)
    return V3AcceptanceReport(checks=checks, path=str(path))


def v3_stats(db: Session) -> dict[str, int]:
    return {
        "qualification_standards": db.query(QualificationStandard).count(),
        "qualification_standard_conditions": db.query(QualificationStandardCondition).count(),
        "enterprises": db.query(Enterprise).count(),
        "enterprise_qualifications": db.query(EnterpriseQualification).count(),
        "enterprise_personnel": db.query(EnterprisePersonnel).count(),
        "enterprise_projects": db.query(EnterpriseProject).count(),
    }


def check_tables(db: Session) -> V3AcceptanceCheck:
    tables = set(inspect(db.bind).get_table_names())
    expected = {
        "qualification_standards",
        "qualification_standard_conditions",
        "enterprises",
        "enterprise_qualifications",
        "enterprise_personnel",
        "enterprise_projects",
    }
    missing = expected - tables
    if missing:
        return V3AcceptanceCheck("tables", "fail", f"缺少表：{', '.join(sorted(missing))}")
    return V3AcceptanceCheck("tables", "ok", "V3.1 资质标准库和企业档案表已存在")


def check_standard_write_and_read(db: Session) -> V3AcceptanceCheck:
    standard = seed_sample_standard(db)
    loaded = db.scalar(
        select(QualificationStandard)
        .options(selectinload(QualificationStandard.conditions))
        .where(QualificationStandard.id == standard.id)
    )
    if loaded and loaded.conditions:
        return V3AcceptanceCheck(
            "standard_library",
            "ok",
            f"standard={loaded.code} conditions={len(loaded.conditions)}",
        )
    return V3AcceptanceCheck("standard_library", "fail", "未能写入或读取资质标准条件")


def check_enterprise_write_and_read(db: Session) -> V3AcceptanceCheck:
    enterprise = seed_sample_enterprise(db)
    loaded = db.scalar(
        select(Enterprise)
        .options(
            selectinload(Enterprise.qualifications),
            selectinload(Enterprise.personnel),
            selectinload(Enterprise.projects),
        )
        .where(Enterprise.id == enterprise.id)
    )
    if loaded and loaded.qualifications and loaded.personnel and loaded.projects:
        return V3AcceptanceCheck(
            "enterprise_profile",
            "ok",
            (
                f"enterprise={loaded.name} qualifications={len(loaded.qualifications)} "
                f"personnel={len(loaded.personnel)} projects={len(loaded.projects)}"
            ),
        )
    return V3AcceptanceCheck("enterprise_profile", "fail", "未能写入或读取企业档案明细")


def seed_sample_standard(db: Session) -> QualificationStandard:
    standard = db.scalar(
        select(QualificationStandard).where(QualificationStandard.code == "V3-SAMPLE-JZSG-2")
    )
    if standard is None:
        standard = QualificationStandard(
            code="V3-SAMPLE-JZSG-2",
            name="建筑工程施工总承包二级",
            category="施工总承包",
            level="二级",
            region="国家",
            authority="住房和城乡建设主管部门",
            version="V3.1 验收样例",
            status="active",
            source_url="https://example.gov.cn/qualification-standard",
            source_document_title="建筑业企业资质标准样例",
            summary="用于验证 V3.1 资质标准库的数据结构和后台录入链路。",
        )
        db.add(standard)
        db.flush()
    existing_condition = db.scalar(
        select(QualificationStandardCondition).where(
            QualificationStandardCondition.standard_id == standard.id
        )
    )
    if existing_condition is None:
        db.add_all(
            [
                QualificationStandardCondition(
                    standard_id=standard.id,
                    condition_type="asset",
                    title="净资产要求",
                    requirement_text="企业净资产达到资质标准规定的最低要求。",
                    metric_name="净资产",
                    metric_value="4000",
                    metric_unit="万元",
                    sort_order=10,
                ),
                QualificationStandardCondition(
                    standard_id=standard.id,
                    condition_type="personnel",
                    title="注册建造师要求",
                    requirement_text="建筑工程专业注册建造师数量满足标准要求。",
                    metric_name="注册建造师",
                    metric_value="5",
                    metric_unit="人",
                    sort_order=20,
                ),
            ]
        )
    db.commit()
    return standard


def seed_sample_enterprise(db: Session) -> Enterprise:
    standard = seed_sample_standard(db)
    enterprise = db.scalar(select(Enterprise).where(Enterprise.name == "V3.1 验收样例企业"))
    if enterprise is None:
        enterprise = Enterprise(
            name="V3.1 验收样例企业",
            unified_social_credit_code="91310000V31SAMPLE0X",
            legal_representative="验收负责人",
            region="上海",
            registered_capital="5000万元",
            contact_name="项目管理员",
            contact_phone="13800000000",
            address="本地验收数据地址",
            status="active",
            remark="用于验证 V3.1 企业档案本地录入能力。",
        )
        db.add(enterprise)
        db.flush()

    if not db.scalar(
        select(EnterpriseQualification).where(
            EnterpriseQualification.enterprise_id == enterprise.id
        )
    ):
        db.add(
            EnterpriseQualification(
                enterprise_id=enterprise.id,
                standard_id=standard.id,
                qualification_name=standard.name,
                category=standard.category,
                level=standard.level,
                certificate_no="D231V31SAMPLE",
                issuing_authority="住房和城乡建设主管部门",
                status="active",
            )
        )
    if not db.scalar(
        select(EnterprisePersonnel).where(EnterprisePersonnel.enterprise_id == enterprise.id)
    ):
        db.add(
            EnterprisePersonnel(
                enterprise_id=enterprise.id,
                name="张三",
                id_number_masked="310***********001X",
                role_type="注册建造师",
                certificate_name="建筑工程专业一级注册建造师",
                certificate_no="沪131V31SAMPLE",
                specialty="建筑工程",
                level="一级",
                status="active",
            )
        )
    if not db.scalar(
        select(EnterpriseProject).where(EnterpriseProject.enterprise_id == enterprise.id)
    ):
        db.add(
            EnterpriseProject(
                enterprise_id=enterprise.id,
                name="V3.1 验收样例项目",
                project_type="房屋建筑工程",
                contract_amount="1200万元",
                role="施工总承包",
                source_document="本地验收样例",
                remark="用于验证企业业绩录入。",
            )
        )
    db.commit()
    return enterprise


def format_v3_acceptance_report(report: V3AcceptanceReport) -> str:
    lines = ["V3.1 验收结果"]
    for check in report.checks:
        label = "OK" if check.status == "ok" else "FAIL"
        lines.append(f"[{label}] {check.name}: {check.detail}")
    lines.append(f"summary ok={report.passed_count} fail={report.failed_count}")
    if report.path:
        lines.append(f"v3_acceptance_report={report.path}")
    return "\n".join(lines)


def write_v3_acceptance_report(report: V3AcceptanceReport, settings: Settings):
    exports = prepare_storage(settings).exports
    path = exports / f"v3_1_acceptance_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    lines = [
        "# V3.1 验收报告",
        "",
        f"生成时间：{datetime.now().isoformat(timespec='seconds')}",
        "",
        "| 检查项 | 状态 | 详情 |",
        "| --- | --- | --- |",
    ]
    for check in report.checks:
        lines.append(f"| {check.name} | {check.status} | {check.detail} |")
    lines.extend(
        [
            "",
            f"汇总：ok={report.passed_count} fail={report.failed_count}",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
