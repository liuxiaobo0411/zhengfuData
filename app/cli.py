from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings, resolve_project_path
from app.database import SessionLocal
from app.models import SiteSection
from app.services.crawler import crawl_section
from app.services.site_importer import import_sites_from_yaml


def main() -> None:
    parser = argparse.ArgumentParser(prog="zhengfudata")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-sites")
    import_parser.add_argument("--file", default="configs/sites.yaml")

    crawl_parser = subparsers.add_parser("crawl-section")
    crawl_parser.add_argument("section_id", type=int)

    crawl_enabled_parser = subparsers.add_parser("crawl-enabled")
    crawl_enabled_parser.add_argument("--limit", type=int, default=0)

    args = parser.parse_args()
    if args.command == "import-sites":
        import_sites(Path(args.file))
    elif args.command == "crawl-section":
        crawl_one(args.section_id)
    elif args.command == "crawl-enabled":
        crawl_enabled(args.limit)


def import_sites(path: Path) -> None:
    config_path = resolve_project_path(path)
    with SessionLocal() as db:
        result = import_sites_from_yaml(db, config_path)
    print(f"imported sites={result['sites']} sections={result['sections']}")


def crawl_one(section_id: int) -> None:
    with SessionLocal() as db:
        run = crawl_section(db, section_id, triggered_by="cli", settings=get_settings())
    print(f"run={run.run_no} status={run.status} new_items={run.new_items}")


def crawl_enabled(limit: int) -> None:
    with SessionLocal() as db:
        query = select(SiteSection).where(SiteSection.enabled.is_(True)).order_by(SiteSection.id)
        sections = list(db.scalars(query).all())
        if limit > 0:
            sections = sections[:limit]
        for section in sections:
            run = crawl_section(db, section.id, triggered_by="cli", settings=get_settings())
            print(
                f"section={section.id} run={run.run_no} "
                f"status={run.status} new_items={run.new_items}"
            )


if __name__ == "__main__":
    main()
