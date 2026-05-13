from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db.models import (
    EnrichedFieldValue,
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
from app.settings import settings


router = APIRouter()


def _admin_email_set() -> set[str]:
    return {email.strip().lower() for email in settings.admin_emails.split(",") if email.strip()}


def get_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.email.lower() not in _admin_email_set():
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


def _provider_enabled() -> dict[str, bool]:
    return {
        "apify": bool(settings.apify_token),
        "lusha": bool(settings.lusha_api_key),
        "apollo": bool(settings.apollo_api_key),
        "rocketreach": bool(settings.rocketreach_api_key),
    }


def _call_summary(calls: list[ProviderCall]) -> list[dict]:
    return [
        {
            "provider": call.provider,
            "stage": call.stage,
            "success": call.success,
            "errorMessage": call.error_message,
            "providerRef": call.provider_ref,
        }
        for call in calls
    ]


def _cost_summary(costs: list[LookupCost]) -> list[dict]:
    return [
        {
            "provider": cost.provider,
            "costUsd": cost.cost_usd,
            "costUnits": cost.cost_units,
            "unitName": cost.unit_name,
            "isEstimated": cost.is_estimated,
            "note": cost.note,
        }
        for cost in costs
    ]


def _lookup_summary(lookup: Lookup, db: Session) -> dict:
    user = db.query(User).filter(User.id == lookup.user_id).one_or_none()
    calls = db.query(ProviderCall).filter_by(lookup_id=lookup.id).order_by(ProviderCall.id.asc()).all()
    costs = db.query(LookupCost).filter_by(lookup_id=lookup.id).all()
    total_cost = sum(cost.cost_usd or 0 for cost in costs)
    return {
        "id": lookup.id,
        "userEmail": user.email if user else None,
        "linkedinUrl": lookup.linkedin_url,
        "status": lookup.status.value,
        "errorMessage": lookup.error_message,
        "createdAt": lookup.created_at.isoformat() if lookup.created_at else None,
        "updatedAt": lookup.updated_at.isoformat() if lookup.updated_at else None,
        "totalCostUsd": total_cost,
        "costs": _cost_summary(costs),
        "providerCalls": _call_summary(calls),
    }


def _delete_lookup_children(db: Session, lookup_id: int) -> None:
    field_ids = [row.id for row in db.query(EnrichedFieldValue.id).filter_by(lookup_id=lookup_id).all()]
    if field_ids:
        db.query(FieldSource).filter(FieldSource.field_value_id.in_(field_ids)).delete(synchronize_session=False)
    db.query(EnrichedFieldValue).filter_by(lookup_id=lookup_id).delete()
    db.query(WorkHistoryEvent).filter_by(lookup_id=lookup_id).delete()
    db.query(ProviderCall).filter_by(lookup_id=lookup_id).delete()
    db.query(LookupCost).filter_by(lookup_id=lookup_id).delete()


@router.get("/overview")
def overview(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    users = db.query(User).order_by(User.id.desc()).limit(200).all()
    lookups = db.query(Lookup).order_by(Lookup.id.desc()).limit(limit).all()
    lookup_counts: dict[int, int] = defaultdict(int)
    for user_id, count in db.query(Lookup.user_id, Lookup.id).all():
        lookup_counts[user_id] += 1

    calls = db.query(ProviderCall).order_by(ProviderCall.id.desc()).limit(500).all()
    provider_stats: dict[str, dict] = {}
    for provider, enabled in _provider_enabled().items():
        provider_stats[provider] = {
            "provider": provider,
            "enabled": enabled,
            "successes": 0,
            "failures": 0,
            "latestError": None,
        }
    for call in calls:
        stats = provider_stats.setdefault(
            call.provider,
            {"provider": call.provider, "enabled": False, "successes": 0, "failures": 0, "latestError": None},
        )
        if call.success:
            stats["successes"] += 1
        else:
            stats["failures"] += 1
            if not stats["latestError"] and call.error_message:
                stats["latestError"] = call.error_message

    return {
        "admin": {"id": admin.id, "email": admin.email},
        "users": [
            {
                "id": user.id,
                "email": user.email,
                "createdAt": user.created_at.isoformat() if user.created_at else None,
                "lookupCount": lookup_counts[user.id],
            }
            for user in users
        ],
        "lookups": [_lookup_summary(lookup, db) for lookup in lookups],
        "providerStatus": list(provider_stats.values()),
    }


@router.delete("/lookups/{lookup_id}")
def delete_lookup(
    lookup_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    lookup = db.query(Lookup).filter(Lookup.id == lookup_id).one_or_none()
    if not lookup:
        raise HTTPException(status_code=404, detail="Lookup not found")
    _delete_lookup_children(db, lookup_id)
    db.delete(lookup)
    db.commit()
    return {"ok": True}


@router.post("/lookups/{lookup_id}/reset")
def reset_lookup(
    lookup_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    lookup = db.query(Lookup).filter(Lookup.id == lookup_id).one_or_none()
    if not lookup:
        raise HTTPException(status_code=404, detail="Lookup not found")
    _delete_lookup_children(db, lookup_id)
    lookup.status = LookupStatus.queued
    lookup.error_message = None
    db.add(lookup)
    db.commit()

    queued = enqueue_lookup(lookup.id)
    if not queued:
        run_lookup_job_in_thread(lookup.id)

    return {"lookupId": lookup.id, "status": lookup.status.value}
