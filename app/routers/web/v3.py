from __future__ import annotations

from datetime import datetime, time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from app.config import BASE_DIR
from app.database import SessionLocal
from app.models import (
    Enterprise,
    EnterprisePersonnel,
    EnterpriseProject,
    EnterpriseQualification,
    QualificationStandard,
    QualificationStandardCondition,
)
from app.routers.web.security import require_user
from app.services.v3_acceptance import v3_stats

router = APIRouter(tags=["v3"])
templates = Jinja2Templates(directory=str(BASE_DIR / "app" / "templates"))

CONDITION_TYPES = [
    ("asset", "资产"),
    ("personnel", "人员"),
    ("performance", "业绩"),
    ("equipment", "设备"),
    ("other", "其他"),
]


def clean_text(value: Any) -> str:
    return str(value or "").strip()


def parse_optional_date(value: Any) -> datetime | None:
    raw = clean_text(value)
    if not raw:
        return None
    try:
        return datetime.combine(datetime.strptime(raw, "%Y-%m-%d").date(), time.min)
    except ValueError as exc:
        raise ValueError("日期格式应为 YYYY-MM-DD") from exc


def redirect_or_user(request: Request):
    user = require_user(request)
    return user


@router.get("/qualification-standards", response_class=HTMLResponse)
def standards_page(request: Request, q: str = ""):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    query_text = clean_text(q)
    with SessionLocal() as db:
        query = select(QualificationStandard).order_by(QualificationStandard.updated_at.desc())
        if query_text:
            like_value = f"%{query_text}%"
            query = query.where(
                or_(
                    QualificationStandard.code.like(like_value),
                    QualificationStandard.name.like(like_value),
                    QualificationStandard.category.like(like_value),
                )
            )
        standards = db.scalars(query).all()
        stats = v3_stats(db)

    return templates.TemplateResponse(
        request,
        "v3/standards.html",
        {
            "active_nav": "qualification_standards",
            "user": user,
            "standards": standards,
            "stats": stats,
            "q": query_text,
        },
    )


@router.post("/qualification-standards")
async def create_standard(request: Request):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    error = validate_standard_form(form)
    if error:
        return standards_page_with_error(request, user, error)

    try:
        effective_date = parse_optional_date(form.get("effective_date"))
    except ValueError as exc:
        return standards_page_with_error(request, user, str(exc))

    standard = QualificationStandard(
        code=clean_text(form.get("code")),
        name=clean_text(form.get("name")),
        category=clean_text(form.get("category")) or None,
        level=clean_text(form.get("level")) or None,
        region=clean_text(form.get("region")) or None,
        authority=clean_text(form.get("authority")) or None,
        version=clean_text(form.get("version")) or None,
        source_url=clean_text(form.get("source_url")) or None,
        source_document_title=clean_text(form.get("source_document_title")) or None,
        effective_date=effective_date,
        summary=clean_text(form.get("summary")) or None,
        remark=clean_text(form.get("remark")) or None,
    )
    with SessionLocal() as db:
        db.add(standard)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return standards_page_with_error(request, user, "标准编码已存在")
    return RedirectResponse("/qualification-standards", status_code=303)


@router.get("/qualification-standards/{standard_id}", response_class=HTMLResponse)
def standard_detail_page(request: Request, standard_id: int):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        standard = db.scalar(
            select(QualificationStandard)
            .options(selectinload(QualificationStandard.conditions))
            .where(QualificationStandard.id == standard_id)
        )
        if standard is None:
            return RedirectResponse("/qualification-standards", status_code=303)

    return templates.TemplateResponse(
        request,
        "v3/standard_detail.html",
        {
            "active_nav": "qualification_standards",
            "user": user,
            "standard": standard,
            "condition_types": CONDITION_TYPES,
        },
    )


@router.post("/qualification-standards/{standard_id}/conditions")
async def create_standard_condition(request: Request, standard_id: int):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    title = clean_text(form.get("title"))
    requirement_text = clean_text(form.get("requirement_text"))
    if not title or not requirement_text:
        return standard_detail_with_error(request, user, standard_id, "条件名称和要求正文不能为空")

    condition = QualificationStandardCondition(
        standard_id=standard_id,
        condition_type=clean_text(form.get("condition_type")) or "other",
        title=title,
        requirement_text=requirement_text,
        metric_name=clean_text(form.get("metric_name")) or None,
        metric_value=clean_text(form.get("metric_value")) or None,
        metric_unit=clean_text(form.get("metric_unit")) or None,
        sort_order=parse_int(form.get("sort_order"), 0),
    )
    with SessionLocal() as db:
        if db.get(QualificationStandard, standard_id) is None:
            return RedirectResponse("/qualification-standards", status_code=303)
        db.add(condition)
        db.commit()
    return RedirectResponse(f"/qualification-standards/{standard_id}", status_code=303)


@router.get("/enterprises", response_class=HTMLResponse)
def enterprises_page(request: Request, q: str = ""):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    query_text = clean_text(q)
    with SessionLocal() as db:
        query = select(Enterprise).order_by(Enterprise.updated_at.desc())
        if query_text:
            like_value = f"%{query_text}%"
            query = query.where(
                or_(
                    Enterprise.name.like(like_value),
                    Enterprise.unified_social_credit_code.like(like_value),
                    Enterprise.region.like(like_value),
                )
            )
        enterprises = db.scalars(query).all()
        stats = v3_stats(db)

    return templates.TemplateResponse(
        request,
        "v3/enterprises.html",
        {
            "active_nav": "enterprises",
            "user": user,
            "enterprises": enterprises,
            "stats": stats,
            "q": query_text,
        },
    )


@router.post("/enterprises")
async def create_enterprise(request: Request):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    name = clean_text(form.get("name"))
    if not name:
        return enterprises_page_with_error(request, user, "企业名称不能为空")

    enterprise = Enterprise(
        name=name,
        unified_social_credit_code=clean_text(form.get("unified_social_credit_code")) or None,
        legal_representative=clean_text(form.get("legal_representative")) or None,
        region=clean_text(form.get("region")) or None,
        registered_capital=clean_text(form.get("registered_capital")) or None,
        contact_name=clean_text(form.get("contact_name")) or None,
        contact_phone=clean_text(form.get("contact_phone")) or None,
        address=clean_text(form.get("address")) or None,
        remark=clean_text(form.get("remark")) or None,
    )
    with SessionLocal() as db:
        db.add(enterprise)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            return enterprises_page_with_error(request, user, "企业名称或统一社会信用代码已存在")
    return RedirectResponse("/enterprises", status_code=303)


@router.get("/enterprises/{enterprise_id}", response_class=HTMLResponse)
def enterprise_detail_page(request: Request, enterprise_id: int):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    with SessionLocal() as db:
        enterprise = db.scalar(
            select(Enterprise)
            .options(
                selectinload(Enterprise.qualifications),
                selectinload(Enterprise.personnel),
                selectinload(Enterprise.projects),
            )
            .where(Enterprise.id == enterprise_id)
        )
        if enterprise is None:
            return RedirectResponse("/enterprises", status_code=303)
        standards = db.scalars(
            select(QualificationStandard).order_by(QualificationStandard.name)
        ).all()

    return templates.TemplateResponse(
        request,
        "v3/enterprise_detail.html",
        {
            "active_nav": "enterprises",
            "user": user,
            "enterprise": enterprise,
            "standards": standards,
        },
    )


@router.post("/enterprises/{enterprise_id}/qualifications")
async def create_enterprise_qualification(request: Request, enterprise_id: int):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    qualification_name = clean_text(form.get("qualification_name"))
    if not qualification_name:
        return enterprise_detail_with_error(request, user, enterprise_id, "资质名称不能为空")
    try:
        valid_from = parse_optional_date(form.get("valid_from"))
        valid_to = parse_optional_date(form.get("valid_to"))
    except ValueError as exc:
        return enterprise_detail_with_error(request, user, enterprise_id, str(exc))

    standard_id = parse_optional_int(form.get("standard_id"))
    qualification = EnterpriseQualification(
        enterprise_id=enterprise_id,
        standard_id=standard_id,
        qualification_name=qualification_name,
        category=clean_text(form.get("category")) or None,
        level=clean_text(form.get("level")) or None,
        certificate_no=clean_text(form.get("certificate_no")) or None,
        issuing_authority=clean_text(form.get("issuing_authority")) or None,
        valid_from=valid_from,
        valid_to=valid_to,
        remark=clean_text(form.get("remark")) or None,
    )
    with SessionLocal() as db:
        if db.get(Enterprise, enterprise_id) is None:
            return RedirectResponse("/enterprises", status_code=303)
        db.add(qualification)
        db.commit()
    return RedirectResponse(f"/enterprises/{enterprise_id}", status_code=303)


@router.post("/enterprises/{enterprise_id}/personnel")
async def create_enterprise_personnel(request: Request, enterprise_id: int):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    name = clean_text(form.get("name"))
    if not name:
        return enterprise_detail_with_error(request, user, enterprise_id, "人员姓名不能为空")
    try:
        valid_to = parse_optional_date(form.get("valid_to"))
    except ValueError as exc:
        return enterprise_detail_with_error(request, user, enterprise_id, str(exc))

    personnel = EnterprisePersonnel(
        enterprise_id=enterprise_id,
        name=name,
        id_number_masked=clean_text(form.get("id_number_masked")) or None,
        role_type=clean_text(form.get("role_type")) or None,
        certificate_name=clean_text(form.get("certificate_name")) or None,
        certificate_no=clean_text(form.get("certificate_no")) or None,
        specialty=clean_text(form.get("specialty")) or None,
        level=clean_text(form.get("level")) or None,
        valid_to=valid_to,
        remark=clean_text(form.get("remark")) or None,
    )
    with SessionLocal() as db:
        if db.get(Enterprise, enterprise_id) is None:
            return RedirectResponse("/enterprises", status_code=303)
        db.add(personnel)
        db.commit()
    return RedirectResponse(f"/enterprises/{enterprise_id}", status_code=303)


@router.post("/enterprises/{enterprise_id}/projects")
async def create_enterprise_project(request: Request, enterprise_id: int):
    user = redirect_or_user(request)
    if isinstance(user, RedirectResponse):
        return user

    form = await request.form()
    name = clean_text(form.get("name"))
    if not name:
        return enterprise_detail_with_error(request, user, enterprise_id, "项目名称不能为空")
    try:
        completed_at = parse_optional_date(form.get("completed_at"))
    except ValueError as exc:
        return enterprise_detail_with_error(request, user, enterprise_id, str(exc))

    project = EnterpriseProject(
        enterprise_id=enterprise_id,
        name=name,
        project_type=clean_text(form.get("project_type")) or None,
        contract_amount=clean_text(form.get("contract_amount")) or None,
        completed_at=completed_at,
        role=clean_text(form.get("role")) or None,
        source_document=clean_text(form.get("source_document")) or None,
        remark=clean_text(form.get("remark")) or None,
    )
    with SessionLocal() as db:
        if db.get(Enterprise, enterprise_id) is None:
            return RedirectResponse("/enterprises", status_code=303)
        db.add(project)
        db.commit()
    return RedirectResponse(f"/enterprises/{enterprise_id}", status_code=303)


def validate_standard_form(form) -> str | None:
    if not clean_text(form.get("code")):
        return "标准编码不能为空"
    if not clean_text(form.get("name")):
        return "标准名称不能为空"
    source_url = clean_text(form.get("source_url"))
    if source_url and not source_url.startswith(("http://", "https://")):
        return "来源地址必须是 http 或 https 地址"
    return None


def parse_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def parse_optional_int(value: Any) -> int | None:
    parsed = parse_int(value, 0)
    return parsed if parsed > 0 else None


def standards_page_with_error(request: Request, user, error: str):
    with SessionLocal() as db:
        standards = db.scalars(
            select(QualificationStandard).order_by(QualificationStandard.updated_at.desc())
        ).all()
        stats = v3_stats(db)
    return templates.TemplateResponse(
        request,
        "v3/standards.html",
        {
            "active_nav": "qualification_standards",
            "user": user,
            "standards": standards,
            "stats": stats,
            "q": "",
            "error": error,
        },
        status_code=400,
    )


def enterprises_page_with_error(request: Request, user, error: str):
    with SessionLocal() as db:
        enterprises = db.scalars(select(Enterprise).order_by(Enterprise.updated_at.desc())).all()
        stats = v3_stats(db)
    return templates.TemplateResponse(
        request,
        "v3/enterprises.html",
        {
            "active_nav": "enterprises",
            "user": user,
            "enterprises": enterprises,
            "stats": stats,
            "q": "",
            "error": error,
        },
        status_code=400,
    )


def standard_detail_with_error(request: Request, user, standard_id: int, error: str):
    response = standard_detail_page(request, standard_id)
    if isinstance(response, RedirectResponse):
        return response
    response.context["error"] = error
    response.status_code = 400
    return response


def enterprise_detail_with_error(request: Request, user, enterprise_id: int, error: str):
    response = enterprise_detail_page(request, enterprise_id)
    if isinstance(response, RedirectResponse):
        return response
    response.context["error"] = error
    response.status_code = 400
    return response
