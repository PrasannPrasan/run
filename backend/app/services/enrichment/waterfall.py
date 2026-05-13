from __future__ import annotations

import datetime as dt
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass, field

from redis import Redis
from sqlalchemy.orm import Session

from app.db.models import (
    EnrichedFieldValue,
    FieldKey,
    FieldSource,
    Lookup,
    LookupCost,
    LookupStatus,
    ProviderCall,
    WorkHistoryEvent,
)
from app.services.confidence.scorer import score_value
from app.services.cost.tracker import CostTracker
from app.services.enrichment.utils import canonicalize_linkedin_url
from app.services.providers.apify_client import ApifyProviderClient
from app.services.providers.apollo_client import ApolloProviderClient
from app.services.providers.lusha_client import LushaProviderClient
from app.services.providers.rocketreach_client import RocketReachProviderClient
from app.services.providers.types import ProviderResult
from app.settings import settings


@dataclass
class Aggregate:
    full_name: str | None = None
    current_company: str | None = None
    current_designation: str | None = None
    emails: list[str] = field(default_factory=list)
    phones: list[str] = field(default_factory=list)
    work_history: list[dict] = field(default_factory=list)
    sources: dict[str, list[dict]] = field(default_factory=dict)

    def merge(self, r: ProviderResult) -> None:
        def save(field: str, value: object):
            if value is None:
                return
            self.sources.setdefault(field, []).append(
                {"provider": r.provider, "provider_ref": r.provider_ref, "note": f"from {r.provider}"}
            )

        if r.full_name and not self.full_name:
            self.full_name = r.full_name
            save("full_name", r.full_name)
        if r.current_company and not self.current_company:
            self.current_company = r.current_company
            save("current_company", r.current_company)
        if r.current_designation and not self.current_designation:
            self.current_designation = r.current_designation
            save("current_designation", r.current_designation)

        if r.emails:
            for email in r.emails:
                if email not in self.emails:
                    self.emails.append(email)
                    save("emails", email)
        if r.phones:
            for phone in r.phones:
                if phone not in self.phones:
                    self.phones.append(phone)
                    save("phones", phone)
        if r.work_history:
            existing = {(x.get("company"), x.get("title"), x.get("start"), x.get("end")) for x in self.work_history}
            for item in r.work_history:
                key = (item.get("company"), item.get("title"), item.get("start"), item.get("end"))
                if key not in existing:
                    self.work_history.append(item)
                    save("work_history", key)
                    existing.add(key)


class WaterfallOrchestrator:
    def __init__(self, db: Session):
        self.db = db
        self.cost = CostTracker()

    @contextmanager
    def _provider_lock(self, provider: str):
        lock = None
        redis_conn = None
        try:
            redis_conn = Redis.from_url(settings.redis_url)
            lock = redis_conn.lock(f"provider-lock:{provider}", timeout=120, blocking_timeout=20)
            lock.acquire()
        except Exception:
            lock = None
        try:
            yield
        finally:
            if lock:
                try:
                    lock.release()
                except Exception:
                    pass

    def _log_provider_call(
        self,
        *,
        lookup_id: int,
        provider: str,
        stage: str,
        req: dict | None,
        result: ProviderResult | None = None,
        err: Exception | None = None,
    ) -> None:
        call = ProviderCall(
            lookup_id=lookup_id,
            provider=provider,
            stage=stage,
            request_meta_json=json.dumps(req or {}),
            response_meta_json=json.dumps(result.raw) if result and result.raw else None,
            provider_ref=result.provider_ref if result else None,
            success=err is None,
            error_message=str(err) if err else None,
            finished_at=dt.datetime.now(dt.UTC),
        )
        self.db.add(call)
        self.db.commit()

    def _save_cost(self, lookup: Lookup, result: ProviderResult) -> None:
        if result.cost_usd is None and result.cost_units is None:
            return
        item = self.db.query(LookupCost).filter_by(lookup_id=lookup.id, provider=result.provider).one_or_none()
        if not item:
            item = LookupCost(lookup_id=lookup.id, provider=result.provider)
        item.cost_usd = result.cost_usd
        item.cost_units = result.cost_units
        item.unit_name = result.unit_name
        item.is_estimated = result.is_estimated_cost
        item.note = result.cost_note
        self.db.add(item)
        self.db.commit()

    def _upsert_field(self, lookup: Lookup, key: FieldKey, value_obj: object, source_entries: list[dict], derived: bool = False) -> None:
        fv = self.db.query(EnrichedFieldValue).filter_by(lookup_id=lookup.id, key=key).one_or_none()
        if not fv:
            fv = EnrichedFieldValue(lookup_id=lookup.id, key=key, value_json="")
        fv.value_json = json.dumps(value_obj)
        fv.confidence = score_value(value_obj, source_count=max(1, len(source_entries)), derived=derived)
        self.db.add(fv)
        self.db.commit()
        self.db.refresh(fv)

        self.db.query(FieldSource).filter_by(field_value_id=fv.id).delete()
        for s in source_entries:
            self.db.add(
                FieldSource(
                    field_value_id=fv.id,
                    provider=s.get("provider", "unknown"),
                    provider_ref=s.get("provider_ref"),
                    note=s.get("note"),
                )
            )
        self.db.commit()

    def _total_years(self, work_history: list[dict]) -> float:
        # Approximation if start/end are parseable years.
        years = 0.0
        for w in work_history:
            start = str(w.get("start") or "")
            end = str(w.get("end") or "")
            start_match = re.search(r"(19|20)\d{2}", start)
            if not start_match:
                continue
            sy = int(start_match.group(0))
            end_match = re.search(r"(19|20)\d{2}", end)
            ey = int(end_match.group(0)) if end_match else dt.datetime.now(dt.UTC).year
            years += max(0, ey - sy)
        return round(years, 1)

    def _persist_aggregate(self, lookup: Lookup, agg: Aggregate) -> None:
        self._upsert_field(lookup, FieldKey.full_name, agg.full_name, agg.sources.get("full_name", []))
        self._upsert_field(lookup, FieldKey.current_company, agg.current_company, agg.sources.get("current_company", []))
        self._upsert_field(
            lookup, FieldKey.current_designation, agg.current_designation, agg.sources.get("current_designation", [])
        )
        self._upsert_field(lookup, FieldKey.emails, agg.emails, agg.sources.get("emails", []))
        self._upsert_field(lookup, FieldKey.phones, agg.phones, agg.sources.get("phones", []))

        years = self._total_years(agg.work_history)
        self._upsert_field(
            lookup,
            FieldKey.total_years_experience,
            years,
            agg.sources.get("work_history", []),
            derived=True,
        )

        self.db.query(WorkHistoryEvent).filter_by(lookup_id=lookup.id).delete()
        for item in agg.work_history:
            self.db.add(
                WorkHistoryEvent(
                    lookup_id=lookup.id,
                    company=item.get("company"),
                    title=item.get("title"),
                    start_date=item.get("start"),
                    end_date=item.get("end"),
                    is_current=bool(item.get("is_current")),
                    confidence=score_value(item, source_count=1),
                    provider="aggregated",
                    provider_ref=None,
                )
            )
        self.db.commit()

    def run(self, lookup: Lookup) -> None:
        lookup.status = LookupStatus.running
        lookup.linkedin_url = canonicalize_linkedin_url(lookup.linkedin_url)
        self.db.add(lookup)
        self.db.commit()

        agg = Aggregate()

        # Pre-snapshots for credit-delta estimation
        before_lusha = self.cost.snapshot_lusha()
        before_apollo = self.cost.snapshot_apollo()
        before_rr = self.cost.snapshot_rocketreach()

        # Stage 1: apify
        try:
            with self._provider_lock("apify"):
                r = ApifyProviderClient().enrich(lookup.linkedin_url)
            agg.merge(r)
            self._save_cost(lookup, r)
            self._log_provider_call(lookup_id=lookup.id, provider="apify", stage="scrape", req={"url": lookup.linkedin_url}, result=r)
        except Exception as e:
            self._log_provider_call(lookup_id=lookup.id, provider="apify", stage="scrape", req={"url": lookup.linkedin_url}, err=e)

        # Stage 2: email/phone waterfall
        if not agg.emails or not agg.phones:
            try:
                with self._provider_lock("lusha"):
                    r = LushaProviderClient().enrich(lookup.linkedin_url)
                agg.merge(r)
                self._save_cost(lookup, r)
                self._log_provider_call(lookup_id=lookup.id, provider="lusha", stage="contact", req={"url": lookup.linkedin_url}, result=r)
            except Exception as e:
                self._log_provider_call(lookup_id=lookup.id, provider="lusha", stage="contact", req={"url": lookup.linkedin_url}, err=e)

        if not agg.emails:
            try:
                with self._provider_lock("apollo"):
                    r = ApolloProviderClient().enrich_person(lookup.linkedin_url, reveal_emails=True)
                agg.merge(r)
                self._save_cost(lookup, r)
                self._log_provider_call(lookup_id=lookup.id, provider="apollo", stage="email", req={"url": lookup.linkedin_url}, result=r)
            except Exception as e:
                self._log_provider_call(lookup_id=lookup.id, provider="apollo", stage="email", req={"url": lookup.linkedin_url}, err=e)

        # RocketReach is kept late in the waterfall and only used for missing contact data.
        if not agg.emails or not agg.phones:
            try:
                with self._provider_lock("rocketreach"):
                    r = RocketReachProviderClient().lookup(lookup.linkedin_url)
                agg.merge(r)
                self._save_cost(lookup, r)
                self._log_provider_call(
                    lookup_id=lookup.id,
                    provider="rocketreach",
                    stage="phone_or_timeline",
                    req={"url": lookup.linkedin_url},
                    result=r,
                )
            except Exception as e:
                self._log_provider_call(
                    lookup_id=lookup.id,
                    provider="rocketreach",
                    stage="phone_or_timeline",
                    req={"url": lookup.linkedin_url},
                    err=e,
                )

        # Apollo async phone webhook request
        if (not agg.phones) and settings.public_webhook_base_url:
            try:
                webhook_url = f"{settings.public_webhook_base_url.rstrip('/')}/api/webhooks/apollo-phone"
                with self._provider_lock("apollo"):
                    r = ApolloProviderClient().request_phone_webhook(lookup.linkedin_url, webhook_url=webhook_url)
                self._log_provider_call(
                    lookup_id=lookup.id,
                    provider="apollo",
                    stage="phone_webhook_request",
                    req={"url": lookup.linkedin_url, "webhook_url": webhook_url},
                    result=r,
                )
            except Exception as e:
                self._log_provider_call(
                    lookup_id=lookup.id,
                    provider="apollo",
                    stage="phone_webhook_request",
                    req={"url": lookup.linkedin_url},
                    err=e,
                )

        self._persist_aggregate(lookup, agg)

        # Post snapshots + delta approximation
        after_lusha = self.cost.snapshot_lusha()
        after_apollo = self.cost.snapshot_apollo()
        after_rr = self.cost.snapshot_rocketreach()
        for provider, before, after in [
            ("lusha", before_lusha, after_lusha),
            ("apollo", before_apollo, after_apollo),
            ("rocketreach", before_rr, after_rr),
        ]:
            delta = self.cost.compute_unit_delta(before, after)
            if delta is None:
                continue
            item = self.db.query(LookupCost).filter_by(lookup_id=lookup.id, provider=provider).one_or_none()
            if not item:
                item = LookupCost(lookup_id=lookup.id, provider=provider)
            item.cost_units = delta
            item.unit_name = "credits_delta"
            item.is_estimated = True
            item.note = "Estimated from before/after account usage snapshots"
            self.db.add(item)
        self.db.commit()

        lookup.status = LookupStatus.complete if (agg.emails or agg.phones) else LookupStatus.partial
        self.db.add(lookup)
        self.db.commit()
