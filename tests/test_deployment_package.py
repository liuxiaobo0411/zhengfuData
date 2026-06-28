from zipfile import ZipFile

from app.services.deployment_package import export_deployment_package


def test_export_deployment_package_contains_deployable_files_and_excludes_local_state(tmp_path):
    package = export_deployment_package(tmp_path / "zhengfudata.zip")

    assert package.path.exists()
    assert package.file_count > 10
    assert package.size_bytes > 0

    with ZipFile(package.path) as archive:
        names = set(archive.namelist())

    assert "zhengfudata/README.md" in names
    assert "zhengfudata/.env.example" in names
    assert "zhengfudata/pyproject.toml" in names
    assert "zhengfudata/alembic.ini" in names
    assert "zhengfudata/configs/sites.yaml" in names
    assert "zhengfudata/scripts/windows/setup.ps1" in names
    assert "zhengfudata/scripts/windows/run-local-acceptance.ps1" in names
    assert "zhengfudata/DEPLOYMENT_PACKAGE_MANIFEST.txt" in names

    assert "zhengfudata/.env" not in names
    assert not any(name.startswith("zhengfudata/.git/") for name in names)
    assert not any(name.startswith("zhengfudata/.venv/") for name in names)
    assert not any(name.startswith("zhengfudata/data/") for name in names)
    assert not any(name.startswith("zhengfudata/storage/") for name in names)
    assert not any(name.endswith(".pyc") for name in names)

    with ZipFile(package.path) as archive:
        manifest = archive.read("zhengfudata/DEPLOYMENT_PACKAGE_MANIFEST.txt").decode("utf-8")
    assert "generated_at=" in manifest
    assert f"file_count={package.file_count}" in manifest
    assert "本包不包含 .env、data、storage、.venv、.git 或本机缓存。" in manifest


def test_export_deployment_package_accepts_output_directory(tmp_path):
    output_dir = tmp_path / "exports"

    package = export_deployment_package(output_dir)

    assert package.path.parent == output_dir
    assert package.path.name.startswith("zhengfudata_deployment_")
    assert package.path.suffix == ".zip"
