from pathlib import Path

from app.config import BASE_DIR


def test_readme_reports_current_cross_platform_acceptance_status():
    readme = Path(BASE_DIR / "README.md").read_text(encoding="utf-8")

    assert "截至 2026-06-28" in readme
    assert "V1 MVP 和 V2 轻量本地知识库 MVP 已完成" in readme
    assert "Ubuntu / Windows Python 3.11 / 3.12" in readme
    assert "macOS/Linux 脚本状态" in readme
    assert "Windows 实机验收记录模板" in readme


def test_v1_acceptance_record_has_latest_status_summary():
    doc = Path(BASE_DIR / "docs" / "V1_MVP验收记录.md").read_text(encoding="utf-8")

    assert "## 最新结论：2026-06-28" in doc
    assert "storage/exports/v1_acceptance_report_20260628_084040.md" in doc
    assert "部署自检：`ok=9 warn=0 fail=0`" in doc
    assert "scripts/windows/run-local-acceptance.ps1" in doc
    assert "scripts/run-local-acceptance.sh" in doc


def test_v2_acceptance_record_has_latest_status_summary():
    doc = Path(BASE_DIR / "docs" / "V2_验收验证记录.md").read_text(encoding="utf-8")

    assert "## 最新结论：2026-06-28" in doc
    assert "storage/exports/v2_acceptance_report_20260628_082541.md" in doc
    assert "汇总：`ok=13 fail=0`" in doc
    assert "/api/openclaw/kb/ask" in doc
