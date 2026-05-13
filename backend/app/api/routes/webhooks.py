from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import EnrichedFieldValue, FieldKey, FieldSource, Lookup, LookupStatus, ProviderCall
from app.db.session import get_db
from app.services.enrichment.utils import canonicalize_linkedin_url, profile_hash


router = APIRouter()


class ApolloPhoneWebhookPayload(BaseModel):
    linkedin_url: str | None = None
    phone_numbers: list[str] | None = None
    person: dict | None = None
    people: list[dict] | None = None
    data: dict | None = None


@router.post("/apollo-phone")
def apollo_phone_webhook(payload: ApolloPhoneWebhookPayload, db: Session = Depends(get_db)):
    linkedin_url = payload.linkedin_url
    if not linkedin_url and payload.person:
        linkedin_url = payload.person.get("linkedin_url") or payload.person.get("linkedin")
    if not linkedin_url and payload.data:
        linkedin_url = payload.data.get("linkedin_url")

    lookup = None
    if linkedin_url:
        p_hash = profile_hash(canonicalize_linkedin_url(linkedin_url))
        lookup = (
            db.query(Lookup)
            .filter(Lookup.profile_hash == p_hash, Lookup.status.in_([LookupStatus.queued, LookupStatus.running, LookupStatus.partial]))
            .order_by(Lookup.id.desc())
            .first()
        )

    if not lookup:
        provider_ref = None
        if payload.person:
            provider_ref = payload.person.get("id") or payload.person.get("person_id")
        if not provider_ref and payload.data:
            people = payload.data.get("people")
            if isinstance(people, list) and people and isinstance(people[0], dict):
                provider_ref = people[0].get("id") or people[0].get("person_id")
        if not provider_ref and payload.people:
            provider_ref = payload.people[0].get("id") or payload.people[0].get("person_id")
        if provider_ref:
            call = (
                db.query(ProviderCall)
                .filter(ProviderCall.provider == "apollo", ProviderCall.provider_ref == str(provider_ref))
                .order_by(ProviderCall.id.desc())
                .first()
            )
            lookup = call.lookup if call else None

    if not lookup:
        return {"ok": True, "matched": False}

    phones = payload.phone_numbers or []
    if not phones and payload.person:
        p_val = payload.person.get("phone_numbers") or payload.person.get("phones") or []
        if isinstance(p_val, list):
            for item in p_val:
                if isinstance(item, dict):
                    value = item.get("sanitized_number") or item.get("raw_number") or item.get("number")
                else:
                    value = item
                if value:
                    phones.append(str(value))
    if not phones and payload.data:
        people = payload.data.get("people")
        if isinstance(people, list):
            for person in people:
                if not isinstance(person, dict):
                    continue
                for item in person.get("phone_numbers") or person.get("phones") or []:
                    if isinstance(item, dict):
                        value = item.get("sanitized_number") or item.get("raw_number") or item.get("number")
                    else:
                        value = item
                    if value:
                        phones.append(str(value))
    if not phones and payload.people:
        for person in payload.people:
            for item in person.get("phone_numbers") or person.get("phones") or []:
                if isinstance(item, dict):
                    value = item.get("sanitized_number") or item.get("raw_number") or item.get("number")
                else:
                    value = item
                if value:
                    phones.append(str(value))

    fv = db.query(EnrichedFieldValue).filter_by(lookup_id=lookup.id, key=FieldKey.phones).one_or_none()
    existing: list[str] = []
    if fv:
        try:
            existing = json.loads(fv.value_json) or []
        except Exception:
            existing = []
    merged = sorted({*(existing or []), *phones})
    if not fv:
        fv = EnrichedFieldValue(lookup_id=lookup.id, key=FieldKey.phones, value_json="[]", confidence=0.8)
    fv.value_json = json.dumps(merged)
    fv.confidence = 0.85 if merged else fv.confidence
    db.add(fv)
    db.commit()
    db.refresh(fv)

    db.add(
        FieldSource(
            field_value_id=fv.id,
            provider="apollo",
            provider_ref=None,
            note="Apollo webhook phone payload",
        )
    )

    if merged:
        lookup.status = LookupStatus.complete
        db.add(lookup)
    db.commit()
    return {"ok": True, "matched": True, "lookupId": lookup.id}
