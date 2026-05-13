from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.models import (
    EnrichedFieldValue,
    FieldKey,
    FieldSource,
    Lookup,
    LookupCost,
    LookupStatus,
    ProviderCall,
    User,
    WorkHistoryEvent,
)
from app.db.session import get_db
from app.services.enrichment.jobs import enqueue_lookup, run_lookup_job_in_thread
from app.services.enrichment.utils import canonicalize_linkedin_url, profile_hash
from app.settings import settings


router = APIRouter()


class EnrichRequest(BaseModel):
    linkedinUrl: str


class EnrichResponse(BaseModel):
    lookupId: int
    status: str


def _apify_actor_url() -> str:
    actor_id = settings.apify_actor_id.replace("~", "/")
    return f"https://apify.com/{actor_id}"


def _provider_strategy() -> dict:
    return {
        "recommendedOrder": ["apify", "lusha", "apollo", "rocketreach", "apollo_phone_webhook"],
        "providers": [
            {
                "name": "apify",
                "stage": "profile_and_timeline",
                "enabled": bool(settings.apify_token),
                "bestFor": "Fresh public profile basics, current role, and work-history timeline.",
                "costModel": "$5/month free Apify usage on Free plan, then actor pay-per-event plus platform usage.",
                "sourceUrl": _apify_actor_url(),
            },
            {
                "name": "lusha",
                "stage": "email_phone",
                "enabled": bool(settings.lusha_api_key),
                "bestFor": "Direct email and phone reveal when you have Lusha credits/API access.",
                "costModel": "API credit model: request/result credit plus email and phone reveal credits.",
                "sourceUrl": "https://info.lusha.com/en/articles/163856-all-there-is-to-know-about-lusha-s-api",
            },
            {
                "name": "apollo",
                "stage": "email_and_employment_fallback",
                "enabled": bool(settings.apollo_api_key),
                "bestFor": (
                    "Verified email, company/title fallback, employment history, and optional async phone reveal. "
                    "If People Enrichment is blocked by the Apollo plan, the app falls back to existing Apollo contacts."
                ),
                "costModel": (
                    "Plan-dependent Apollo credits for people match/enrichment and phone/email reveal; "
                    "existing contacts search is treated as a zero-credit fallback."
                ),
                "sourceUrl": "https://docs.apollo.io/docs/api-pricing",
            },
            {
                "name": "rocketreach",
                "stage": "last_resort_contact_lookup",
                "enabled": bool(settings.rocketreach_api_key),
                "bestFor": "Fallback contact lookup when cheaper/free-credit sources miss email or phone.",
                "costModel": "Lookup/subscription credit model; keep last to avoid burning higher-value lookups.",
                "sourceUrl": "https://rocketreach.co/pricing",
            },
        ],
        "logic": [
            "Reuse a completed lookup for the same LinkedIn URL before calling any provider.",
            "Run Apify first because it can use monthly free platform credits and provides the profile/timeline fields.",
            "Call contact-data providers only for fields still missing after the profile scrape.",
            "Prefer Lusha before Apollo/RocketReach when API credits are available because it can return email and phone in one contact reveal.",
            "Use Apollo for email and employment fallback; request phone by webhook only after all synchronous phone lookups miss.",
            "Use RocketReach last because it is useful coverage insurance but usually less attractive for lowest-cost first-pass enrichment.",
        ],
        "freeTierPlan": [
            "Use Apify Free credits for profile/timeline enrichment.",
            "Use Lusha free workspace credits for manual testing, but production API keys may require a paid tier.",
            "Use Apollo free/basic API access only where your workspace plan and credit balance allow it.",
            "Use RocketReach trial lookups sparingly for benchmarking coverage, not as the first waterfall step.",
        ],
        "complianceNote": (
            "Provider terms and privacy rules change. Store only needed fields, honor opt-out/deletion requests, "
            "and avoid direct LinkedIn account scraping with user credentials."
        ),
    }


def _serialize_lookup(lookup: Lookup, db: Session) -> dict:
    fields = db.query(EnrichedFieldValue).filter_by(lookup_id=lookup.id).all()
    sources_by_field: dict[str, list[dict]] = {}
    output: dict[str, dict] = {}
    for field in fields:
        sources = db.query(FieldSource).filter_by(field_value_id=field.id).all()
        sources_by_field[field.key.value] = [
            {"provider": s.provider, "providerRef": s.provider_ref, "note": s.note} for s in sources
        ]
        output[field.key.value] = {
            "value": json.loads(field.value_json),
            "confidence": field.confidence,
            "sources": sources_by_field[field.key.value],
        }

    history = db.query(WorkHistoryEvent).filter_by(lookup_id=lookup.id).order_by(WorkHistoryEvent.id.asc()).all()
    costs = db.query(LookupCost).filter_by(lookup_id=lookup.id).all()
    provider_calls = db.query(ProviderCall).filter_by(lookup_id=lookup.id).order_by(ProviderCall.id.asc()).all()

    return {
        "id": lookup.id,
        "status": lookup.status.value,
        "linkedinUrl": lookup.linkedin_url,
        "fields": output,
        "workHistory": [
            {
                "company": w.company,
                "title": w.title,
                "startDate": w.start_date,
                "endDate": w.end_date,
                "isCurrent": w.is_current,
                "confidence": w.confidence,
                "provider": w.provider,
            }
            for w in history
        ],
        "costs": [
            {
                "provider": c.provider,
                "costUsd": c.cost_usd,
                "costUnits": c.cost_units,
                "unitName": c.unit_name,
                "isEstimated": c.is_estimated,
                "note": c.note,
            }
            for c in costs
        ],
        "providerCalls": [
            {
                "provider": call.provider,
                "stage": call.stage,
                "success": call.success,
                "errorMessage": call.error_message,
                "providerRef": call.provider_ref,
            }
            for call in provider_calls
        ],
    }


def _is_meaningful_value(key: FieldKey, value: object) -> bool:
    if key == FieldKey.total_years_experience:
        return False
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_is_meaningful_value(key, item) for item in value)
    return True


def _lookup_has_data(lookup: Lookup, db: Session) -> bool:
    if db.query(WorkHistoryEvent).filter_by(lookup_id=lookup.id).first():
        return True
    fields = db.query(EnrichedFieldValue).filter_by(lookup_id=lookup.id).all()
    for field in fields:
        try:
            value = json.loads(field.value_json)
        except json.JSONDecodeError:
            value = field.value_json
        if _is_meaningful_value(field.key, value):
            return True
    return False


def _delete_lookup_results(db: Session, lookup_id: int) -> None:
    field_ids = [row.id for row in db.query(EnrichedFieldValue.id).filter_by(lookup_id=lookup_id).all()]
    if field_ids:
        db.query(FieldSource).filter(FieldSource.field_value_id.in_(field_ids)).delete(synchronize_session=False)
    db.query(EnrichedFieldValue).filter_by(lookup_id=lookup_id).delete()
    db.query(WorkHistoryEvent).filter_by(lookup_id=lookup_id).delete()
    db.query(ProviderCall).filter_by(lookup_id=lookup_id).delete()
    db.query(LookupCost).filter_by(lookup_id=lookup_id).delete()


def _copy_lookup_results(source: Lookup, target: Lookup, db: Session) -> None:
    _delete_lookup_results(db, target.id)
    field_id_map: dict[int, EnrichedFieldValue] = {}
    for field in db.query(EnrichedFieldValue).filter_by(lookup_id=source.id).all():
        copied = EnrichedFieldValue(
            lookup_id=target.id,
            key=field.key,
            value_json=field.value_json,
            confidence=field.confidence,
        )
        db.add(copied)
        db.flush()
        field_id_map[field.id] = copied

    if field_id_map:
        sources = (
            db.query(FieldSource)
            .filter(FieldSource.field_value_id.in_(list(field_id_map.keys())))
            .all()
        )
        for source_entry in sources:
            db.add(
                FieldSource(
                    field_value_id=field_id_map[source_entry.field_value_id].id,
                    provider=source_entry.provider,
                    provider_ref=source_entry.provider_ref,
                    raw_path=source_entry.raw_path,
                    note=source_entry.note,
                )
            )

    for item in db.query(WorkHistoryEvent).filter_by(lookup_id=source.id).all():
        db.add(
            WorkHistoryEvent(
                lookup_id=target.id,
                company=item.company,
                title=item.title,
                start_date=item.start_date,
                end_date=item.end_date,
                is_current=item.is_current,
                confidence=item.confidence,
                provider=item.provider,
                provider_ref=item.provider_ref,
            )
        )

    db.add(
        LookupCost(
            lookup_id=target.id,
            provider="cache",
            cost_usd=0.0,
            cost_units=0.0,
            unit_name="lookup",
            is_estimated=False,
            note=f"Reused local enriched profile from lookup {source.id}",
        )
    )
    db.add(
        ProviderCall(
            lookup_id=target.id,
            provider="cache",
            stage="reuse",
            request_meta_json=json.dumps({"sourceLookupId": source.id}),
            response_meta_json=json.dumps({"status": "reused", "sourceLookupId": source.id}),
            provider_ref=str(source.id),
            success=True,
            finished_at=dt.datetime.now(dt.UTC),
        )
    )
    target.status = source.status
    target.error_message = None
    db.add(target)
    db.commit()


@router.post("", response_model=EnrichResponse)
def enrich(
    body: EnrichRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    normalized = canonicalize_linkedin_url(body.linkedinUrl)
    p_hash = profile_hash(normalized)

    existing_for_user = (
        db.query(Lookup)
        .filter(Lookup.user_id == user.id, Lookup.profile_hash == p_hash)
        .order_by(Lookup.id.desc())
        .first()
    )
    if existing_for_user and existing_for_user.status in {LookupStatus.complete, LookupStatus.partial}:
        if _lookup_has_data(existing_for_user, db):
            return EnrichResponse(lookupId=existing_for_user.id, status=existing_for_user.status.value)

    cached = (
        db.query(Lookup)
        .filter(
            Lookup.profile_hash == p_hash,
            Lookup.id != (existing_for_user.id if existing_for_user else 0),
            Lookup.status.in_([LookupStatus.complete, LookupStatus.partial]),
        )
        .order_by(Lookup.updated_at.desc(), Lookup.id.desc())
        .all()
    )
    cached_with_data = next((lookup for lookup in cached if _lookup_has_data(lookup, db)), None)
    if cached_with_data:
        target = existing_for_user
        if not target:
            target = Lookup(user_id=user.id, linkedin_url=normalized, profile_hash=p_hash, status=LookupStatus.queued)
            db.add(target)
            db.commit()
            db.refresh(target)
        _copy_lookup_results(cached_with_data, target, db)
        return EnrichResponse(lookupId=target.id, status=target.status.value)

    if existing_for_user:
        lookup = existing_for_user
        _delete_lookup_results(db, lookup.id)
        lookup.status = LookupStatus.queued
        lookup.error_message = None
        db.add(lookup)
        db.commit()
    else:
        lookup = Lookup(user_id=user.id, linkedin_url=normalized, profile_hash=p_hash, status=LookupStatus.queued)
        db.add(lookup)
        db.commit()
        db.refresh(lookup)

    queued = enqueue_lookup(lookup.id)
    if not queued:
        # Fallback to an in-process worker when Redis is unavailable.
        # This keeps hosted/tunneled HTTP requests short while the UI polls.
        run_lookup_job_in_thread(lookup.id)

    return EnrichResponse(lookupId=lookup.id, status=lookup.status.value)


@router.get("/strategy")
def strategy(user: User = Depends(get_current_user)):
    return _provider_strategy()


@router.get("/lookups/{lookup_id}")
def get_lookup(lookup_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    lookup = db.query(Lookup).filter(Lookup.id == lookup_id, Lookup.user_id == user.id).one_or_none()
    if not lookup:
        raise HTTPException(status_code=404, detail="Lookup not found")
    return _serialize_lookup(lookup, db)


@router.get("/lookups")
def list_lookups(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    items = (
        db.query(Lookup)
        .filter(Lookup.user_id == user.id)
        .order_by(Lookup.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return {"items": [_serialize_lookup(i, db) for i in items]}
