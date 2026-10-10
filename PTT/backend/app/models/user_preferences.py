from sqlalchemy import CheckConstraint, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.session import Base


class UserPreferences(Base):
    __tablename__ = "user_preferences"
    __table_args__ = (
        CheckConstraint("report_default_period IN ('week', 'month')", name="ck_user_preferences_report_period"),
        CheckConstraint("alert_status_filter IN ('all', 'activa', 'resuelta')", name="ck_user_preferences_alert_status"),
        CheckConstraint(
            "alert_type_filter IN ('all', 'salida_no_autorizada', 'falla_dispositivo', 'manipulacion_sensor')",
            name="ck_user_preferences_alert_type",
        ),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    report_default_period: Mapped[str] = mapped_column(String(10), default="week", nullable=False)
    alert_status_filter: Mapped[str] = mapped_column(String(20), default="all", nullable=False)
    alert_type_filter: Mapped[str] = mapped_column(String(40), default="all", nullable=False)