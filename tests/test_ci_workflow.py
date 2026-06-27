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
