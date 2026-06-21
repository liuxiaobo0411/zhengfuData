from pathlib import Path

from app.config import BASE_DIR


def test_windows_deployment_scripts_exist_and_use_project_relative_paths():
    scripts = [
        BASE_DIR / "scripts" / "windows" / "setup.ps1",
        BASE_DIR / "scripts" / "windows" / "run-server.ps1",
        BASE_DIR / "scripts" / "windows" / "run-daily-crawl.ps1",
        BASE_DIR / "scripts" / "windows" / "install-daily-task.ps1",
    ]

    for script in scripts:
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "Resolve-Path" in content
        assert "$PSScriptRoot" in content


def test_windows_deployment_doc_references_scripts_and_acceptance_steps():
    doc = Path(BASE_DIR / "docs" / "Windows本地部署说明.md").read_text(encoding="utf-8")

    assert "scripts\\windows\\setup.ps1" in doc
    assert "scripts\\windows\\run-server.ps1" in doc
    assert "scripts\\windows\\run-daily-crawl.ps1" in doc
    assert "scripts\\windows\\install-daily-task.ps1" in doc
    assert "验收清单" in doc
