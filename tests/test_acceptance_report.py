from __future__ import annotations

from datetime import datetime

import app.models  # noqa: F401
from app.config import Settings
from app.database import Base, SessionLocal, configure_database
from app.models import (
    Announcement,
    Attachment,
    AttachmentVersion,
    CrawlRun,
    NotificationLog,
    Site,
    SiteSection,
)
from app.services.acceptance_report import export_acceptance_report, render_acceptance_report


def setup_db(tmp_path):
    engine = configure_database(f"sqlite:///{tmp_path / 'report.db'}")
    Base.metadata.create_all(engine)


def seed_acceptance_data():
    with SessionLocal() as db:
        site = Site(
            name="测试站点",
            slug="test-site",
            homepage_url="https://example.gov.cn",
            enabled=True,
        )
        db.add(site)
        db.flush()
        section = SiteSection(
            site_id=site.id,
            name="公告栏目",
            url="https://example.gov.cn/list.html",
            enabled=True,
        )
        db.add(section)
        db.flush()
        run = CrawlRun(
            run_no="scheduled-test-1",
            run_type="scheduled",
            status="success",
            discovered_items=1,
            new_items=1,
            attachment_success_count=1,
            triggered_by="cli_daily",
        )
        db.add(run)
        db.flush()
        announcement = Announcement(
            site_id=site.id,
            section_id=section.id,
            run_id=run.id,
            identity_key="abc",
            identity_strategy="test",
            title="资质公告",
            item_type="qualification_notice",
            source_url="https://example.gov.cn/a.html",
        )
        db.add(announcement)
        db.flush()
        attachment = Attachment(
            announcement_id=announcement.id,
            site_id=site.id,
            run_id=run.id,
            attachment_key="att",
            name="附件",
            safe_name="a.pdf",
            source_url="https://example.gov.cn/a.pdf",
            local_path="attachments/test/a.pdf",
            file_hash="hash-v1",
            download_status="success",
        )
        db.add(attachment)
        db.flush()
        db.add(
            AttachmentVersion(
                attachment_id=attachment.id,
                announcement_id=announcement.id,
                site_id=site.id,
                run_id=run.id,
                version_no=1,
                name="附件",
                safe_name="a.pdf",
                source_url="https://example.gov.cn/a.pdf",
                local_path="attachments/test/a.pdf",
                file_hash="hash-v1",
                download_status="success",
                change_type="attachment_added",
            )
        )
        db.add(
            Attachment(
                announcement_id=announcement.id,
                site_id=site.id,
                run_id=run.id,
                attachment_key="failed-att",
                name="失败附件",
                safe_name="failed.pdf",
                source_url="https://example.gov.cn/failed.pdf",
                download_status="failed",
                failure_reason="timeout",
            )
        )
        db.add(
            NotificationLog(
                run_id=run.id,
                provider="openclaw",
                event_type="daily_crawl_report",
                status="success",
            )
        )
        db.add(
            NotificationLog(
                run_id=run.id,
                provider="openclaw",
                event_type="daily_crawl_report",
                status="failed",
                failure_reason="OPENCLAW_WEBHOOK_URL 未配置",
            )
        )
        db.commit()


def test_render_acceptance_report_summarizes_database(tmp_path):
    setup_db(tmp_path)
    seed_acceptance_data()

    with SessionLocal() as db:
        report = render_acceptance_report(
            db,
            settings=Settings(
                APP_STORAGE_ROOT=tmp_path / "storage",
                APP_SECRET_KEY="test-secret-key",
                ADMIN_PASSWORD="test-password",
                OPENCLAW_WEBHOOK_URL="http://openclaw.local/webhook",
            ),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert "V1 MVP 自动验收报告" in report
    assert "政府网站：1" in report
    assert "归档公告：1" in report
    assert "附件记录：2" in report
    assert "附件版本：1" in report
    assert "OpenClaw webhook：已配置" in report
    assert "scheduled-test-1" in report
    assert "1 个启用栏目的完整每日任务：已完成" in report
    assert "partial=0" in report
    assert "1 个启用栏目的完整每日任务验收。" not in report
    assert "后台页面验收入口" in report
    assert "部署自检摘要" in report
    assert "OK database_schema" in report
    assert "OK security" in report
    assert "公告列表：`http://127.0.0.1:8000/announcements`" in report
    assert "失败来源与处理建议" in report
    assert "失败附件" in report
    assert "附件管理页点击重试" in report
    assert "OPENCLAW_WEBHOOK_URL 未配置" in report


def test_render_acceptance_report_keeps_failed_full_daily_in_pending(tmp_path):
    setup_db(tmp_path)
    with SessionLocal() as db:
        site = Site(
            name="测试站点",
            slug="test-site",
            homepage_url="https://example.gov.cn",
            enabled=True,
        )
        db.add(site)
        db.flush()
        db.add_all(
            [
                SiteSection(
                    site_id=site.id,
                    name="公告栏目1",
                    url="https://example.gov.cn/list-1.html",
                    enabled=True,
                ),
                SiteSection(
                    site_id=site.id,
                    name="公告栏目2",
                    url="https://example.gov.cn/list-2.html",
                    enabled=True,
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                CrawlRun(
                    run_no="scheduled-test-1",
                    run_type="scheduled",
                    status="success",
                    triggered_by="cli_daily",
                    discovered_items=1,
                ),
                CrawlRun(
                    run_no="scheduled-test-2",
                    run_type="scheduled",
                    status="failed",
                    triggered_by="cli_daily",
                    error_summary="timeout",
                ),
            ]
        )
        db.commit()

    with SessionLocal() as db:
        report = render_acceptance_report(
            db,
            settings=Settings(APP_STORAGE_ROOT=tmp_path / "storage"),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert "2 个启用栏目的完整每日任务：已执行但有失败" in report
    assert "partial=0 failed=1" in report
    assert "2 个启用栏目的完整每日任务验收。" in report


def test_render_acceptance_report_marks_partial_success_as_pending(tmp_path):
    setup_db(tmp_path)
    with SessionLocal() as db:
        site = Site(
            name="测试站点",
            slug="test-site",
            homepage_url="https://example.gov.cn",
            enabled=True,
        )
        db.add(site)
        db.flush()
        db.add(
            SiteSection(
                site_id=site.id,
                name="公告栏目",
                url="https://example.gov.cn/list.html",
                enabled=True,
            )
        )
        db.add(
            CrawlRun(
                run_no="scheduled-test-1",
                run_type="scheduled",
                status="partial_success",
                triggered_by="cli_daily",
                discovered_items=1,
                attachment_failed_count=1,
            )
        )
        db.commit()

    with SessionLocal() as db:
        report = render_acceptance_report(
            db,
            settings=Settings(APP_STORAGE_ROOT=tmp_path / "storage"),
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert "1 个启用栏目的完整每日任务：已执行但有失败" in report
    assert "partial=1 failed=0" in report
    assert "1 个启用栏目的完整每日任务验收。" in report


def test_export_acceptance_report_writes_markdown_file(tmp_path):
    setup_db(tmp_path)
    seed_acceptance_data()
    target = tmp_path / "exports" / "report.md"

    with SessionLocal() as db:
        report = export_acceptance_report(
            db,
            settings=Settings(APP_STORAGE_ROOT=tmp_path / "storage"),
            output_path=target,
            now=datetime(2026, 6, 21, 12, 0),
        )

    assert report.path == target
    assert target.exists()
    assert target.read_text(encoding="utf-8") == report.markdown
