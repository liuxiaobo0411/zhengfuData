from __future__ import annotations

import argparse
from pathlib import Path

from app.config import get_settings, resolve_project_path
from app.database import SessionLocal
from app.services.crawler import crawl_section
from app.services.notifier import send_daily_report
from app.services.scheduler import run_daily_crawl
from app.services.site_importer import import_sites_from_yaml
from app.services.source_validator import validate_enabled_sources


def main() -> None:
    parser = argparse.ArgumentParser(prog="zhengfudata")
    subparsers = parser.add_subparsers(dest="command", required=True)

    import_parser = subparsers.add_parser("import-sites")
    import_parser.add_argument("--file", default="configs/sites.yaml")

    crawl_parser = subparsers.add_parser("crawl-section")
    crawl_parser.add_argument("section_id", type=int)

    crawl_enabled_parser = subparsers.add_parser("crawl-enabled")
    crawl_enabled_parser.add_argument("--limit", type=int, default=0)

    daily_parser = subparsers.add_parser("run-daily-crawl")
    daily_parser.add_argument("--limit", type=int, default=0)
    daily_parser.add_argument("--no-notify", action="store_true")

    validate_parser = subparsers.add_parser("validate-sources")
    validate_parser.add_argument("--limit", type=int, default=0)

    subparsers.add_parser("send-daily-report")

    args = parser.parse_args()
    if args.command == "import-sites":
        import_sites(Path(args.file))
    elif args.command == "crawl-section":
        crawl_one(args.section_id)
    elif args.command == "crawl-enabled":
        crawl_enabled(args.limit)
    elif args.command == "run-daily-crawl":
        run_daily(args.limit, notify=not args.no_notify)
    elif args.command == "validate-sources":
        validate_sources(args.limit)
    elif args.command == "send-daily-report":
        send_report()


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
    result = run_daily_crawl(
        settings=get_settings(),
        limit=limit,
        notify=False,
        triggered_by="cli",
    )
    for section_id, run in zip(result.section_ids, result.runs, strict=True):
        print(
            f"section={section_id} run={run.run_no} status={run.status} new_items={run.new_items}"
        )


def run_daily(limit: int, notify: bool) -> None:
    result = run_daily_crawl(
        settings=get_settings(),
        limit=limit,
        notify=notify,
        triggered_by="cli_daily",
    )
    print(
        f"daily sections={len(result.section_ids)} success={result.success_count} "
        f"failed={result.failed_count}"
    )
    if result.notification:
        print(
            f"notification={result.notification.id} status={result.notification.status} "
            f"reason={result.notification.failure_reason or ''}"
        )


def send_report() -> None:
    with SessionLocal() as db:
        log = send_daily_report(db, settings=get_settings())
    print(f"notification={log.id} status={log.status} reason={log.failure_reason or ''}")


def validate_sources(limit: int) -> None:
    summary = validate_enabled_sources(limit=limit)
    for result in summary.results:
        if result.status == "success":
            print(
                f"OK section={result.section_id} records={result.record_count} "
                f"strategy={result.strategy} name={result.section_name} "
                f"sample={result.sample_title[:60]}"
            )
        else:
            print(
                f"FAIL section={result.section_id} strategy={result.strategy} "
                f"name={result.section_name} reason={result.failure_reason}"
            )
    print(
        f"summary total={summary.total_count} success={summary.success_count} "
        f"failed={summary.failed_count}"
    )
    if summary.failed_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
