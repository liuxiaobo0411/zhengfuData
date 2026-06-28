from pathlib import Path

from app.config import BASE_DIR


def test_windows_deployment_scripts_exist_and_use_project_relative_paths():
    bootstrap = BASE_DIR / "scripts" / "windows" / "_bootstrap.ps1"
    bootstrap_content = bootstrap.read_text(encoding="utf-8")
    assert "PYTHONUTF8" in bootstrap_content
    assert "PYTHONIOENCODING" in bootstrap_content
    assert "OutputEncoding" in bootstrap_content

    scripts = [
        BASE_DIR / "scripts" / "windows" / "setup.ps1",
        BASE_DIR / "scripts" / "windows" / "run-server.ps1",
        BASE_DIR / "scripts" / "windows" / "run-daily-crawl.ps1",
        BASE_DIR / "scripts" / "windows" / "run-local-acceptance.ps1",
        BASE_DIR / "scripts" / "windows" / "retry-failed-attachments.ps1",
        BASE_DIR / "scripts" / "windows" / "validate-sources.ps1",
        BASE_DIR / "scripts" / "windows" / "export-acceptance-report.ps1",
        BASE_DIR / "scripts" / "windows" / "export-deployment-package.ps1",
        BASE_DIR / "scripts" / "windows" / "verify-deployment-package.ps1",
        BASE_DIR / "scripts" / "windows" / "doctor.ps1",
        BASE_DIR / "scripts" / "windows" / "acceptance-check.ps1",
        BASE_DIR / "scripts" / "windows" / "v2-acceptance-check.ps1",
        BASE_DIR / "scripts" / "windows" / "install-daily-task.ps1",
    ]

    for script in scripts:
        assert script.exists()
        content = script.read_text(encoding="utf-8")
        assert "Resolve-Path" in content
        assert "$PSScriptRoot" in content
        assert '. "$PSScriptRoot\\_bootstrap.ps1"' in content


def test_windows_deployment_doc_references_scripts_and_acceptance_steps():
    doc = Path(BASE_DIR / "docs" / "Windows本地部署说明.md").read_text(encoding="utf-8")

    assert "scripts\\windows\\setup.ps1" in doc
    assert "scripts\\windows\\run-server.ps1" in doc
    assert "scripts\\windows\\run-daily-crawl.ps1" in doc
    assert "scripts\\windows\\run-local-acceptance.ps1" in doc
    assert "scripts\\windows\\retry-failed-attachments.ps1" in doc
    assert "scripts\\windows\\validate-sources.ps1" in doc
    assert "scripts\\windows\\export-acceptance-report.ps1" in doc
    assert "scripts\\windows\\export-deployment-package.ps1" in doc
    assert "scripts\\windows\\verify-deployment-package.ps1" in doc
    assert "scripts\\windows\\doctor.ps1" in doc
    assert "scripts\\windows\\acceptance-check.ps1" in doc
    assert "scripts\\windows\\v2-acceptance-check.ps1" in doc
    assert "scripts\\windows\\install-daily-task.ps1" in doc
    assert "验收清单" in doc


def test_windows_local_acceptance_script_runs_required_steps():
    script = (BASE_DIR / "scripts" / "windows" / "run-local-acceptance.ps1").read_text(
        encoding="utf-8"
    )

    assert '"local-acceptance-check"' in script
    assert "--source-limit" in script
    assert "--daily-limit" in script
    assert "SkipSourceValidation" in script
    assert "--skip-source-validation" in script
    assert "--skip-daily-crawl" in script
    assert "--skip-v2" in script
    assert "$LASTEXITCODE" in script


def test_ci_runs_windows_local_acceptance_script_in_light_mode():
    workflow = (BASE_DIR / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")

    assert "Run Windows local acceptance script" in workflow
    assert "scripts\\windows\\run-local-acceptance.ps1" in workflow
    assert "-SkipSourceValidation" in workflow
    assert "-SkipDailyCrawl" in workflow
    assert "-SkipV2" in workflow
    assert "Export Windows deployment package" in workflow
    assert "scripts\\windows\\export-deployment-package.ps1" in workflow
    assert "ci_windows_deployment.zip" in workflow
    assert "Verify exported Windows deployment package" in workflow
    assert "scripts\\windows\\verify-deployment-package.ps1" in workflow


def test_windows_deployment_package_verifier_checks_clean_package_and_runs_acceptance():
    script = (BASE_DIR / "scripts" / "windows" / "verify-deployment-package.ps1").read_text(
        encoding="utf-8"
    )

    assert "Expand-Archive" in script
    assert "DEPLOYMENT_PACKAGE_MANIFEST.txt" in script
    assert '"scripts\\windows\\setup.ps1"' in script
    assert '"scripts\\windows\\doctor.ps1"' in script
    assert '"scripts\\windows\\run-local-acceptance.ps1"' in script
    assert ".env" in script
    assert "storage" in script
    assert ".venv" in script


def test_unix_local_acceptance_script_wraps_cross_platform_cli():
    script = (BASE_DIR / "scripts" / "run-local-acceptance.sh").read_text(encoding="utf-8")

    assert "local-acceptance-check" in script
    assert "--source-limit" in script
    assert "--daily-limit" in script
    assert "--skip-source-validation" in script
    assert "--skip-daily-crawl" in script
    assert "--skip-v2" in script
    assert 'PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"' in script


def test_unix_deployment_package_script_wraps_cross_platform_cli():
    script = (BASE_DIR / "scripts" / "export-deployment-package.sh").read_text(encoding="utf-8")

    assert "export-deployment-package" in script
    assert "--output" in script
    assert 'PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"' in script
