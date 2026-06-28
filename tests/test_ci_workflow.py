from pathlib import Path

import yaml

from app.config import BASE_DIR


def test_ci_workflow_covers_windows_smoke_and_test_matrix():
    workflow = yaml.safe_load(
        Path(BASE_DIR / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    )

    test_matrix = workflow["jobs"]["test"]["strategy"]["matrix"]
    assert test_matrix["os"] == ["ubuntu-latest", "windows-latest"]
    assert test_matrix["python-version"] == ["3.11", "3.12"]

    smoke = workflow["jobs"]["windows-smoke"]
    assert smoke["runs-on"] == "windows-latest"
    commands = [step.get("run", "") for step in smoke["steps"]]
    assert "scripts\\windows\\setup.ps1 -PythonCommand python" in commands
    assert "scripts\\windows\\doctor.ps1" in commands
    assert (
        "scripts\\windows\\run-local-acceptance.ps1 -SkipSourceValidation -SkipDailyCrawl -SkipV2"
    ) in commands
    assert (
        "scripts\\windows\\export-deployment-package.ps1 -Output exports\\ci_windows_deployment.zip"
        in commands
    )
    assert any(
        "scripts\\windows\\verify-deployment-package.ps1" in command
        and "exports\\ci_windows_deployment.zip" in command
        for command in commands
    )
    upload_steps = [
        step for step in smoke["steps"] if step.get("uses") == "actions/upload-artifact@v4"
    ]
    assert upload_steps
    assert upload_steps[0]["with"]["name"] == "zhengfudata-windows-deployment"
    assert upload_steps[0]["with"]["path"] == "exports/ci_windows_deployment.zip"
    assert upload_steps[0]["with"]["if-no-files-found"] == "error"

    ubuntu_smoke = workflow["jobs"]["ubuntu-smoke"]
    assert ubuntu_smoke["runs-on"] == "ubuntu-latest"
    ubuntu_commands = [step.get("run", "") for step in ubuntu_smoke["steps"]]
    assert any("python -m alembic upgrade head" in command for command in ubuntu_commands)
    assert any(
        "python -m app.cli import-sites --file configs/sites.yaml" in command
        for command in ubuntu_commands
    )
    assert (
        "scripts/run-local-acceptance.sh --skip-source-validation --skip-daily-crawl --skip-v2"
    ) in ubuntu_commands
    assert (
        "scripts/export-deployment-package.sh --output /tmp/zhengfudata_ci_deployment.zip"
        in ubuntu_commands
    )
