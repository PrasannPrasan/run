import datetime as dt
import enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class LookupStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    complete = "complete"
    failed = "failed"
    partial = "partial"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.UTC))

    lookups: Mapped[list["Lookup"]] = relationship(back_populates="user")


class Lookup(Base):
    __tablename__ = "lookups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)

    linkedin_url: Mapped[str] = mapped_column(Text, nullable=False)
    profile_hash: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    status: Mapped[LookupStatus] = mapped_column(Enum(LookupStatus), default=LookupStatus.queued, index=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.UTC), index=True)
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.UTC), onupdate=lambda: dt.datetime.now(dt.UTC)
    )

    user: Mapped["User"] = relationship(back_populates="lookups")
    field_values: Mapped[list["EnrichedFieldValue"]] = relationship(back_populates="lookup", cascade="all, delete-orphan")
    work_history: Mapped[list["WorkHistoryEvent"]] = relationship(back_populates="lookup", cascade="all, delete-orphan")
    provider_calls: Mapped[list["ProviderCall"]] = relationship(back_populates="lookup", cascade="all, delete-orphan")
    costs: Mapped[list["LookupCost"]] = relationship(back_populates="lookup", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("user_id", "profile_hash", name="uq_user_profile_hash"),)


class FieldKey(str, enum.Enum):
    full_name = "full_name"
    current_company = "current_company"
    current_designation = "current_designation"
    total_years_experience = "total_years_experience"
    emails = "emails"
    phones = "phones"


class EnrichedFieldValue(Base):
    __tablename__ = "enriched_field_values"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lookup_id: Mapped[int] = mapped_column(ForeignKey("lookups.id"), index=True, nullable=False)

    key: Mapped[FieldKey] = mapped_column(Enum(FieldKey), index=True, nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)  # JSON string of value(s)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, default=lambda: dt.datetime.now(dt.UTC), onupdate=lambda: dt.datetime.now(dt.UTC)
    )

    lookup: Mapped["Lookup"] = relationship(back_populates="field_values")
    sources: Mapped[list["FieldSource"]] = relationship(back_populates="field_value", cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("lookup_id", "key", name="uq_lookup_field_key"),)


class FieldSource(Base):
    __tablename__ = "field_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    field_value_id: Mapped[int] = mapped_column(ForeignKey("enriched_field_values.id"), index=True, nullable=False)

    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)  # runId/requestId/etc
    raw_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.UTC))

    field_value: Mapped["EnrichedFieldValue"] = relationship(back_populates="sources")


class WorkHistoryEvent(Base):
    __tablename__ = "work_history_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lookup_id: Mapped[int] = mapped_column(ForeignKey("lookups.id"), index=True, nullable=False)

    company: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(32), nullable=True)  # keep flexible (YYYY-MM etc)
    end_date: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.UTC))

    lookup: Mapped["Lookup"] = relationship(back_populates="work_history")


class ProviderCall(Base):
    __tablename__ = "provider_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lookup_id: Mapped[int] = mapped_column(ForeignKey("lookups.id"), index=True, nullable=False)

    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    stage: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    request_meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_meta_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    provider_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    started_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.UTC))
    finished_at: Mapped[dt.datetime | None] = mapped_column(DateTime, nullable=True)

    lookup: Mapped["Lookup"] = relationship(back_populates="provider_calls")


class LookupCost(Base):
    __tablename__ = "lookup_costs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    lookup_id: Mapped[int] = mapped_column(ForeignKey("lookups.id"), index=True, nullable=False)

    provider: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_units: Mapped[float | None] = mapped_column(Float, nullable=True)  # credits, CUs, etc.
    unit_name: Mapped[str | None] = mapped_column(String(32), nullable=True)  # "credits", "CUs"
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[dt.datetime] = mapped_column(DateTime, default=lambda: dt.datetime.now(dt.UTC))

    lookup: Mapped["Lookup"] = relationship(back_populates="costs")

    __table_args__ = (UniqueConstraint("lookup_id", "provider", name="uq_lookup_provider_cost"),)

