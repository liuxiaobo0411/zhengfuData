from pathlib import Path

import app.models  # noqa: F401
from app.config import BASE_DIR
from app.database import Base, SessionLocal, configure_database
from app.models import Site, SiteSection
from app.services.site_importer import import_sites_from_yaml


def test_import_sites_from_yaml_upserts_site_and_section(tmp_path: Path):
    engine = configure_database(f"sqlite:///{tmp_path / 'sites.db'}")
    Base.metadata.create_all(engine)
    config = tmp_path / "sites.yaml"
    config.write_text(
        """
sites:
  - name: 测试站点
    slug: test-site
    homepage_url: https://example.gov.cn/
    organization: 测试单位
    region: 测试地区
    enabled: true
    sections:
      - name: 公告栏目
        url: https://example.gov.cn/list.html
        item_type: qualification_notice
        crawler_strategy: http_static
        list_selector: li.date
        title_selector: a
""",
        encoding="utf-8",
    )

    with SessionLocal() as db:
        first = import_sites_from_yaml(db, config)
        second = import_sites_from_yaml(db, config)

    assert first == {"sites": 1, "sections": 1}
    assert second == {"sites": 1, "sections": 1}
    with SessionLocal() as db:
        assert db.query(Site).count() == 1
        assert db.query(SiteSection).count() == 1
        assert db.query(SiteSection).one().crawler_strategy == "http_static"


def test_import_sites_from_yaml_updates_section_when_url_changes(tmp_path: Path):
    engine = configure_database(f"sqlite:///{tmp_path / 'sites.db'}")
    Base.metadata.create_all(engine)
    config = tmp_path / "sites.yaml"
    config.write_text(
        """
sites:
  - name: 测试站点
    slug: test-site
    homepage_url: https://example.gov.cn/
    sections:
      - name: 资质查询
        url: https://example.gov.cn/qualification
        crawler_strategy: browser_rendered
        enabled: false
""",
        encoding="utf-8",
    )

    with SessionLocal() as db:
        import_sites_from_yaml(db, config)
    config.write_text(
        """
sites:
  - name: 测试站点
    slug: test-site
    homepage_url: https://example.gov.cn/
    sections:
      - name: 资质查询
        url: https://example.gov.cn/api/qualification
        crawler_strategy: json_api
        enabled: true
""",
        encoding="utf-8",
    )

    with SessionLocal() as db:
        import_sites_from_yaml(db, config)

    with SessionLocal() as db:
        section = db.query(SiteSection).one()
        assert section.url == "https://example.gov.cn/api/qualification"
        assert section.crawler_strategy == "json_api"
        assert section.enabled is True


def test_repository_sites_config_imports_v1_seed_sections(tmp_path: Path):
    engine = configure_database(f"sqlite:///{tmp_path / 'sites.db'}")
    Base.metadata.create_all(engine)

    with SessionLocal() as db:
        result = import_sites_from_yaml(db, BASE_DIR / "configs" / "sites.yaml")

    assert result["sites"] >= 3
    assert result["sections"] >= 12
    with SessionLocal() as db:
        enabled_sections = db.query(SiteSection).where(SiteSection.enabled.is_(True)).count()
        assert enabled_sections >= 10
