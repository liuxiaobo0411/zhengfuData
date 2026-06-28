from __future__ import annotations

import argparse
from datetime import datetime, time
from pathlib import Path

from app.config import get_settings, resolve_project_path
from app.database import SessionLocal
from app.models import Attachment
from app.services.acceptance_report import export_acceptance_report
from app.services.crawler import crawl_section, retry_attachment_download
from app.services.deployment_package import export_deployment_package
from app.services.kb import (
    SEARCH_ENTITY_TYPES,
    ask_knowledge,
    kb_stats,
    parse_attachment,
    parse_attachments,
    rebuild_search_index,
    search_knowledge,
)
from app.services.notifier import send_daily_report
from app.services.scheduler import run_daily_crawl
from app.services.site_importer import import_sites_from_yaml
from app.services.source_validator import validate_enabled_sources
from app.services.system_doctor import format_doctor_report, run_system_doctor


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

    report_parser = subparsers.add_parser("export-acceptance-report")
    report_parser.add_argument("--output", default="")

    deployment_package_parser = subparsers.add_parser("export-deployment-package")
    deployment_package_parser.add_argument("--output", default="")

    acceptance_parser = subparsers.add_parser("acceptance-check")
    acceptance_parser.add_argument("--source-limit", type=int, default=2)
    acceptance_parser.add_argument("--skip-source-validation", action="store_true")

    local_acceptance_parser = subparsers.add_parser("local-acceptance-check")
    local_acceptance_parser.add_argument("--source-limit", type=int, default=2)
    local_acceptance_parser.add_argument("--daily-limit", type=int, default=2)
    local_acceptance_parser.add_argument("--skip-source-validation", action="store_true")
    local_acceptance_parser.add_argument("--skip-daily-crawl", action="store_true")
    local_acceptance_parser.add_argument("--skip-v2", action="store_true")

    subparsers.add_parser("doctor")
    subparsers.add_parser("send-daily-report")

    parse_attachments_parser = subparsers.add_parser("parse-attachments")
    parse_attachments_parser.add_argument("--limit", type=int, default=20)

    retry_attachments_parser = subparsers.add_parser("retry-failed-attachments")
    retry_attachments_parser.add_argument("--limit", type=int, default=0)
    retry_attachments_parser.add_argument("--timeout", type=int, default=0)

    parse_attachment_parser = subparsers.add_parser("parse-attachment")
    parse_attachment_parser.add_argument("attachment_id", type=int)

    subparsers.add_parser("rebuild-search-index")

    kb_search_parser = subparsers.add_parser("kb-search")
    kb_search_parser.add_argument("query")
    kb_search_parser.add_argument("--limit", type=int, default=10)
    kb_search_parser.add_argument("--entity-type", default="")
    kb_search_parser.add_argument("--site-name", default="")
    kb_search_parser.add_argument("--published-from", default="")
    kb_search_parser.add_argument("--published-to", default="")

    kb_ask_parser = subparsers.add_parser("kb-ask")
    kb_ask_parser.add_argument("question")
    kb_ask_parser.add_argument("--limit", type=int, default=5)

    subparsers.add_parser("v2-acceptance-check")

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
    elif args.command == "export-acceptance-report":
        export_report(Path(args.output) if args.output else None)
    elif args.command == "export-deployment-package":
        export_deploy_package(Path(args.output) if args.output else None)
    elif args.command == "acceptance-check":
        acceptance_check(args.source_limit, skip_source_validation=args.skip_source_validation)
    elif args.command == "local-acceptance-check":
        local_acceptance_check(
            source_limit=args.source_limit,
            daily_limit=args.daily_limit,
            skip_source_validation=args.skip_source_validation,
            skip_daily_crawl=args.skip_daily_crawl,
            skip_v2=args.skip_v2,
        )
    elif args.command == "doctor":
        doctor()
    elif args.command == "send-daily-report":
        send_report()
    elif args.command == "parse-attachments":
        parse_attachment_batch(args.limit)
    elif args.command == "retry-failed-attachments":
        retry_failed_attachments(args.limit, args.timeout)
    elif args.command == "parse-attachment":
        parse_attachment_one(args.attachment_id)
    elif args.command == "rebuild-search-index":
        rebuild_index()
    elif args.command == "kb-search":
        kb_search(
            args.query,
            args.limit,
            entity_type=args.entity_type,
            site_name=args.site_name,
            published_from=args.published_from,
            published_to=args.published_to,
        )
    elif args.command == "kb-ask":
        kb_ask(args.question, args.limit)
    elif args.command == "v2-acceptance-check":
        v2_acceptance_check()


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
        f"partial={result.partial_count} failed={result.failed_count}"
    )
    if result.parse_summary:
        print(
            f"parse total={result.parse_summary.total} success={result.parse_summary.success} "
            f"failed={result.parse_summary.failed} "
            f"unsupported={result.parse_summary.unsupported}"
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


def parse_attachment_batch(limit: int) -> None:
    with SessionLocal() as db:
        summary = parse_attachments(db, limit=limit, settings=get_settings())
        stats = kb_stats(db)
    print(
        f"parse total={summary.total} success={summary.success} "
        f"failed={summary.failed} unsupported={summary.unsupported}"
    )
    print(
        f"kb document_texts={stats['document_texts']} parsed_success={stats['parsed_success']} "
        f"search_index={stats['search_index']}"
    )


def retry_failed_attachments(limit: int, timeout: int) -> None:
    settings = get_settings()
    if timeout > 0:
        settings = settings.model_copy(update={"crawler_attachment_timeout_seconds": timeout})

    success = 0
    failed = 0
    with SessionLocal() as db:
        query = (
            db.query(Attachment.id)
            .filter(Attachment.download_status == "failed")
            .order_by(Attachment.id)
        )
        if limit > 0:
            query = query.limit(limit)
        attachment_ids = [row[0] for row in query.all()]

        for attachment_id in attachment_ids:
            attachment = retry_attachment_download(
                db,
                attachment_id,
                triggered_by="cli_retry_failed_attachments",
                settings=settings,
            )
            status = attachment.download_status if attachment else "missing"
            reason = (attachment.failure_reason or "") if attachment else "attachment not found"
            if status == "success":
                success += 1
            else:
                failed += 1
            print(f"attachment={attachment_id} status={status} reason={reason}")

    print(f"retry_failed_attachments total={len(attachment_ids)} success={success} failed={failed}")


def parse_attachment_one(attachment_id: int) -> None:
    with SessionLocal() as db:
        document_text = parse_attachment(db, attachment_id, settings=get_settings())
    print(
        f"attachment={attachment_id} status={document_text.status} "
        f"text_length={document_text.text_length} reason={document_text.error_message or ''}"
    )


def rebuild_index() -> None:
    with SessionLocal() as db:
        count = rebuild_search_index(db)
        stats = kb_stats(db)
    print(f"rebuild_search_index count={count} total={stats['search_index']}")


def kb_search(
    query: str,
    limit: int,
    *,
    entity_type: str = "",
    site_name: str = "",
    published_from: str = "",
    published_to: str = "",
) -> None:
    entity_type_filter = parse_entity_type(entity_type)
    published_from_filter = parse_date_start(published_from)
    published_to_filter = parse_date_end(published_to)
    if (
        published_from_filter
        and published_to_filter
        and published_from_filter > published_to_filter
    ):
        raise SystemExit("published-from 不能晚于 published-to")

    with SessionLocal() as db:
        results = search_knowledge(
            db,
            query,
            limit=limit,
            entity_type=entity_type_filter,
            site_name=site_name or None,
            published_from=published_from_filter,
            published_to=published_to_filter,
        )
    for result in results:
        print(
            f"{result.entity_type}#{result.entity_id} score={result.score} "
            f"title={result.title[:80]}"
        )
        if result.snippet:
            print(f"  snippet={result.snippet[:160]}")
        if result.source_url:
            print(f"  source={result.source_url}")
    print(f"summary total={len(results)}")


def parse_entity_type(value: str) -> str | None:
    if not value:
        return None
    if value not in SEARCH_ENTITY_TYPES:
        allowed = ", ".join(sorted(SEARCH_ENTITY_TYPES))
        raise SystemExit(f"entity-type 仅支持：{allowed}")
    return value


def parse_date_start(value: str) -> datetime | None:
    parsed = parse_cli_date(value)
    return datetime.combine(parsed, time.min) if parsed else None


def parse_date_end(value: str) -> datetime | None:
    parsed = parse_cli_date(value)
    return datetime.combine(parsed, time.max) if parsed else None


def parse_cli_date(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise SystemExit(f"日期格式应为 YYYY-MM-DD：{value}") from exc


def kb_ask(question: str, limit: int) -> None:
    with SessionLocal() as db:
        result = ask_knowledge(db, question, limit=limit)
    print(result["answer"])
    for index, item in enumerate(result["items"], start=1):
        print(f"{index}. {item['title']}")
        if item.get("source_url"):
            print(f"   {item['source_url']}")


def validate_sources(limit: int) -> None:
    summary = validate_enabled_sources(limit=limit)
    print_source_validation_summary(summary)
    if summary.failed_count:
        raise SystemExit(1)


def print_source_validation_summary(summary) -> None:
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


def export_report(output_path: Path | None) -> None:
    target = resolve_project_path(output_path) if output_path else None
    with SessionLocal() as db:
        report = export_acceptance_report(db, settings=get_settings(), output_path=target)
    print(f"acceptance_report={report.path}")


def export_deploy_package(output_path: Path | None) -> None:
    package = export_deployment_package(output_path=output_path)
    print(
        f"deployment_package={package.path} "
        f"files={package.file_count} size_bytes={package.size_bytes}"
    )


def doctor() -> None:
    with SessionLocal() as db:
        report = run_system_doctor(db, settings=get_settings())
    print(format_doctor_report(report))
    if report.failed_count:
        raise SystemExit(1)


def acceptance_check(source_limit: int, skip_source_validation: bool = False) -> None:
    settings = get_settings()
    failed = False
    with SessionLocal() as db:
        doctor_report = run_system_doctor(db, settings=settings)
        acceptance_report = export_acceptance_report(db, settings=settings)

    print(format_doctor_report(doctor_report))
    print(f"acceptance_report={acceptance_report.path}")
    if doctor_report.failed_count:
        failed = True

    if not skip_source_validation:
        summary = validate_enabled_sources(limit=source_limit)
        print_source_validation_summary(summary)
        if summary.failed_count:
            failed = True
    else:
        print("source_validation=skipped")

    if failed:
        raise SystemExit(1)


def local_acceptance_check(
    source_limit: int,
    daily_limit: int,
    *,
    skip_source_validation: bool = False,
    skip_daily_crawl: bool = False,
    skip_v2: bool = False,
) -> None:
    settings = get_settings()
    failed = False

    print("local_acceptance_check=start")
    with SessionLocal() as db:
        doctor_report = run_system_doctor(db, settings=settings)
    print(format_doctor_report(doctor_report))
    if doctor_report.failed_count:
        failed = True

    if skip_source_validation:
        print("source_validation=skipped")
    else:
        summary = validate_enabled_sources(limit=source_limit)
        print_source_validation_summary(summary)
        if summary.failed_count:
            failed = True

    if skip_daily_crawl:
        print("daily_crawl=skipped")
    else:
        daily_result = run_daily_crawl(
            settings=settings,
            limit=daily_limit,
            notify=False,
            triggered_by="cli_daily",
        )
        print(
            f"daily sections={len(daily_result.section_ids)} "
            f"success={daily_result.success_count} "
            f"partial={daily_result.partial_count} failed={daily_result.failed_count}"
        )
        if daily_result.parse_summary:
            print(
                f"parse total={daily_result.parse_summary.total} "
                f"success={daily_result.parse_summary.success} "
                f"failed={daily_result.parse_summary.failed} "
                f"unsupported={daily_result.parse_summary.unsupported}"
            )
        if daily_result.failed_count:
            failed = True

    if skip_v2:
        print("v2_acceptance=skipped")
    else:
        with SessionLocal() as db:
            v2_report = run_v2_acceptance_check(db, settings=settings)
        print(format_v2_acceptance_report(v2_report))
        if v2_report.failed_count:
            failed = True

    with SessionLocal() as db:
        acceptance_report = export_acceptance_report(db, settings=settings)
    print(f"acceptance_report={acceptance_report.path}")

    if failed:
        raise SystemExit(1)
    print("local_acceptance_check=passed")


def run_v2_acceptance_check(db, settings):
    from app.services import v2_acceptance

    return v2_acceptance.run_v2_acceptance_check(db, settings=settings)


def format_v2_acceptance_report(report) -> str:
    from app.services import v2_acceptance

    return v2_acceptance.format_v2_acceptance_report(report)


def v2_acceptance_check() -> None:
    with SessionLocal() as db:
        report = run_v2_acceptance_check(db, settings=get_settings())
    print(format_v2_acceptance_report(report))
    if report.failed_count:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
