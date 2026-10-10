from calendar import monthrange
from datetime import date, datetime, time, timedelta, timezone
from io import BytesIO
from typing import Literal
from zoneinfo import ZoneInfo
from xml.sax.saxutils import escape

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import Response
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import landscape, legal, letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session, joinedload

from app.api.deps import get_current_user, get_db, require_roles
from app.models.alert import Alert
from app.models.item import Item
from app.models.movement import Movement, MovementStatus
from app.models.report import Report
from app.models.user import User
from app.schemas.report import ReportPeriodSummary, ReportSummary
from app.services.audit_service import record_audit
from app.services.rate_limit_service import enforce_report_pdf_limit

router = APIRouter()
REPORT_TIMEZONE = ZoneInfo("America/Mexico_City")
MOVEMENT_REPORT_MAX_MONTHS = 12
MOVEMENT_REPORT_MAX_ROWS = 5000


def _add_months(value: date, months: int) -> date:
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def movement_report_window(start_date: date, end_date: date) -> tuple[datetime, datetime]:
    if end_date < start_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="La fecha final debe ser igual o posterior a la inicial")

    end_exclusive = end_date + timedelta(days=1)
    if end_exclusive > _add_months(start_date, MOVEMENT_REPORT_MAX_MONTHS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="El periodo maximo del reporte es de 12 meses",
        )

    start = datetime.combine(start_date, time.min, REPORT_TIMEZONE).astimezone(timezone.utc)
    end = datetime.combine(end_exclusive, time.min, REPORT_TIMEZONE).astimezone(timezone.utc)
    return start, end


def _report_local_datetime(value: datetime | None) -> str:
    if value is None:
        return "—"
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(REPORT_TIMEZONE).strftime("%Y-%m-%d %H:%M")


def report_windows(period: Literal["week", "month"], now: datetime) -> list[tuple[str, datetime, datetime]]:
    if period == "week":
        current_start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(days=now.weekday())
        previous_start = current_start - timedelta(days=7)
        older_start = current_start - timedelta(days=14)
        return [
            ("Semana actual", current_start, now),
            ("Semana anterior", previous_start, current_start),
            ("Hace dos semanas", older_start, previous_start),
        ]

    current_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    previous_start = (current_start - timedelta(days=1)).replace(day=1)
    older_start = (previous_start - timedelta(days=1)).replace(day=1)
    return [
        ("Mes actual", current_start, now),
        ("Mes anterior", previous_start, current_start),
        ("Hace dos meses", older_start, previous_start),
    ]


@router.get(
    "/summary",
    response_model=ReportSummary,
    dependencies=[Depends(require_roles("administrador", "jefe_area", "encargado_inventario"))],
)
def summarize_reports(
    period: Literal["week", "month"] = Query(default="week"),
    db: Session = Depends(get_db),
) -> ReportSummary:
    now = datetime.now(timezone.utc)
    summaries = []
    for label, start, end in report_windows(period, now):
        checkouts = db.query(func.count(Movement.id)).filter(
            Movement.checkout_at >= start, Movement.checkout_at < end
        ).scalar() or 0
        returns = db.query(func.count(Movement.id)).filter(
            Movement.checkin_at >= start, Movement.checkin_at < end
        ).scalar() or 0
        incidents = db.query(func.count(Alert.id)).filter(
            Alert.triggered_at >= start, Alert.triggered_at < end
        ).scalar() or 0

        duration_seconds = (
            (func.julianday(Movement.checkin_at) - func.julianday(Movement.checkout_at)) * 86400
            if db.get_bind().dialect.name == "sqlite"
            else func.extract("epoch", Movement.checkin_at - Movement.checkout_at)
        )
        average_usage = db.query(func.avg(duration_seconds)).filter(
            Movement.status == MovementStatus.CLOSED,
            Movement.checkout_at.is_not(None),
            Movement.checkin_at >= start,
            Movement.checkin_at < end,
        ).scalar()
        average_usage = round(average_usage) if average_usage is not None else None

        most_used = (
            db.query(Item.name, func.count(Movement.id).label("uses"))
            .join(Movement, Movement.item_id == Item.id)
            .filter(Movement.checkout_at >= start, Movement.checkout_at < end)
            .group_by(Item.id, Item.name)
            .order_by(func.count(Movement.id).desc(), Item.name.asc())
            .first()
        )
        summaries.append(ReportPeriodSummary(
            label=label,
            period_start=start,
            period_end=end,
            checkouts=checkouts,
            returns=returns,
            incidents=incidents,
            average_usage_seconds=average_usage,
            most_used_item=most_used[0] if most_used else None,
        ))

    return ReportSummary(period=period, periods=summaries)


@router.get(
    "/summary/pdf",
    dependencies=[Depends(require_roles("administrador", "jefe_area", "encargado_inventario"))],
)
def export_summary_pdf(
    period: Literal["week", "month"] = Query(default="week"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    enforce_report_pdf_limit(current_user.id)
    summary = summarize_reports(period, db)
    generated_at = datetime.now(timezone.utc)
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("ReportTitle", parent=styles["Title"], alignment=TA_CENTER, textColor=colors.HexColor("#176b8c"))
    cell_style = ParagraphStyle("ReportCell", parent=styles["BodyText"], fontSize=8, leading=10)
    story = [
        Paragraph("SIGMAT - Reporte " + ("semanal" if period == "week" else "mensual"), title_style),
        Spacer(1, 8),
        Paragraph(f"Generado: {generated_at:%Y-%m-%d %H:%M} UTC", styles["Normal"]),
        Spacer(1, 14),
    ]
    rows = [["Periodo", "Salidas", "Devoluciones", "Incidentes", "Tiempo promedio", "Articulo mas utilizado"]]
    for row in summary.periods:
        average = "Sin datos" if row.average_usage_seconds is None else f"{row.average_usage_seconds // 3600} h {(row.average_usage_seconds % 3600) // 60} min"
        rows.append([
            Paragraph(escape(row.label), cell_style),
            str(row.checkouts),
            str(row.returns),
            str(row.incidents),
            average,
            Paragraph(escape(row.most_used_item or "Sin datos"), cell_style),
        ])
    table = Table(rows, colWidths=[105, 65, 75, 65, 115, 295], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#143d5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dde5e9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(table)
    SimpleDocTemplate(buffer, pagesize=landscape(letter), title=f"SIGMAT - Reporte {period}").build(story)
    pdf_content = buffer.getvalue()

    report = Report(
        type=f"resumen_{period}_pdf",
        period_start=summary.periods[-1].period_start,
        period_end=summary.periods[0].period_end,
        generated_by_user_id=current_user.id,
    )
    db.add(report)
    try:
        db.flush()
        record_audit(
            db, user_id=current_user.id, action="report.export_pdf", entity_type="report", entity_id=report.id,
            details={"period": period}, commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="sigmat-reporte-{period}-{report.id}.pdf"',
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.get(
    "/movements/pdf",
    dependencies=[Depends(require_roles("administrador", "jefe_area", "encargado_inventario"))],
)
def export_movement_history_pdf(
    start_date: date = Query(...),
    end_date: date = Query(...),
    movement_status: MovementStatus | None = Query(default=None, alias="status"),
    item_id: int | None = Query(default=None, gt=0),
    category_id: int | None = Query(default=None, gt=0),
    location_id: int | None = Query(default=None, gt=0),
    responsible_user_id: int | None = Query(default=None, gt=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    start, end_exclusive = movement_report_window(start_date, end_date)
    enforce_report_pdf_limit(current_user.id)

    in_period = or_(
        and_(Movement.created_at >= start, Movement.created_at < end_exclusive),
        and_(Movement.checkout_at >= start, Movement.checkout_at < end_exclusive),
        and_(Movement.checkin_at >= start, Movement.checkin_at < end_exclusive),
    )
    query = (
        db.query(Movement)
        .join(Item, Movement.item_id == Item.id)
        .options(
            joinedload(Movement.item).joinedload(Item.category),
            joinedload(Movement.responsible_user),
            joinedload(Movement.authorized_by),
            joinedload(Movement.location),
        )
        .filter(in_period)
    )
    filter_values = {
        "status": movement_status.value if movement_status else None,
        "item_id": item_id,
        "category_id": category_id,
        "location_id": location_id,
        "responsible_user_id": responsible_user_id,
    }
    if movement_status is not None:
        query = query.filter(Movement.status == movement_status)
    if item_id is not None:
        query = query.filter(Movement.item_id == item_id)
    if category_id is not None:
        query = query.filter(Item.category_id == category_id)
    if location_id is not None:
        query = query.filter(Movement.location_id == location_id)
    if responsible_user_id is not None:
        query = query.filter(Movement.responsible_user_id == responsible_user_id)

    movements = query.order_by(Movement.created_at, Movement.id).limit(MOVEMENT_REPORT_MAX_ROWS + 1).all()
    if len(movements) > MOVEMENT_REPORT_MAX_ROWS:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="El reporte supera 5000 movimientos; reduzca el periodo o agregue filtros",
        )
    buffer = BytesIO()
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "MovementReportTitle", parent=styles["Title"], alignment=TA_CENTER,
        textColor=colors.HexColor("#176b8c"),
    )
    cell_style = ParagraphStyle("MovementReportCell", parent=styles["BodyText"], fontSize=6, leading=7)
    story = [
        Paragraph("SIGMAT - Historial de movimientos", title_style),
        Spacer(1, 8),
        Paragraph(
            f"Periodo local: {start_date.isoformat()} a {end_date.isoformat()} (incluye ambas fechas)",
            styles["Normal"],
        ),
        Paragraph(f"Generado: {_report_local_datetime(datetime.now(timezone.utc))} America/Mexico_City", styles["Normal"]),
        Paragraph(f"Movimientos incluidos: {len(movements)}", styles["Normal"]),
    ]
    active_filters = [f"{key}={value}" for key, value in filter_values.items() if value is not None]
    story.append(Paragraph("Filtros: " + escape("; ".join(active_filters) if active_filters else "ninguno"), styles["Normal"]))
    story.append(Spacer(1, 10))

    rows = [[
        "ID", "Registro", "Salida", "Devolucion", "Codigo", "Articulo / categoria",
        "Responsable", "Autorizo", "Ubicacion", "Proposito", "Estado",
    ]]
    status_labels = {
        MovementStatus.PENDING_AUTHORIZATION: "Pendiente de autorizacion",
        MovementStatus.OPEN: "En uso",
        MovementStatus.CLOSED: "Devuelto",
    }
    for movement in movements:
        category_name = movement.item.category.name if movement.item.category else "Sin categoria"
        rows.append([
            str(movement.id),
            _report_local_datetime(movement.created_at),
            _report_local_datetime(movement.checkout_at),
            _report_local_datetime(movement.checkin_at),
            Paragraph(escape(movement.item.code), cell_style),
            Paragraph(escape(f"{movement.item.name} / {category_name}"), cell_style),
            Paragraph(escape(movement.responsible_user.full_name), cell_style),
            Paragraph(escape(movement.authorized_by.full_name if movement.authorized_by else "Sin autorizador"), cell_style),
            Paragraph(escape(movement.location.name), cell_style),
            Paragraph(escape(movement.purpose), cell_style),
            Paragraph(escape(status_labels[movement.status]), cell_style),
        ])

    table = Table(
        rows,
        colWidths=[28, 55, 55, 55, 54, 105, 82, 82, 70, 142, 78],
        repeatRows=1,
    )
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#143d5c")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 6),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dde5e9")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f6f8")]),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(table)
    SimpleDocTemplate(
        buffer, pagesize=landscape(legal), leftMargin=24, rightMargin=24,
        title="SIGMAT - Historial de movimientos",
    ).build(story)
    pdf_content = buffer.getvalue()

    report = Report(
        type="movimientos_pdf",
        period_start=start,
        period_end=end_exclusive - timedelta(microseconds=1),
        generated_by_user_id=current_user.id,
    )
    db.add(report)
    try:
        db.flush()
        record_audit(
            db,
            user_id=current_user.id,
            action="report.export_movement_pdf",
            entity_type="report",
            entity_id=report.id,
            details={**filter_values, "start_date": start_date.isoformat(), "end_date": end_date.isoformat(), "row_count": len(movements)},
            commit=False,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    return Response(
        content=pdf_content,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="sigmat-movimientos-{report.id}.pdf"',
            "Cache-Control": "private, no-store",
            "Pragma": "no-cache",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/inventory", dependencies=[Depends(require_roles("administrador", "encargado_inventario"))])
def generate_inventory_report(
    period_start: datetime,
    period_end: datetime,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict:
    """Genera un resumen de movimientos del periodo; la generacion del PDF se delega a un job en background."""
    movements = (
        db.query(Movement).filter(Movement.checkout_at >= period_start, Movement.checkout_at <= period_end).all()
    )

    report = Report(
        type="inventario_periodico",
        period_start=period_start,
        period_end=period_end,
        generated_by_user_id=current_user.id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {"report_id": report.id, "movements_count": len(movements)}
