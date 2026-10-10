from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class ReportPeriodSummary(BaseModel):
    label: str
    period_start: datetime
    period_end: datetime
    checkouts: int
    returns: int
    incidents: int
    average_usage_seconds: int | None
    most_used_item: str | None


class ReportSummary(BaseModel):
    period: Literal["week", "month"]
    periods: list[ReportPeriodSummary]