from __future__ import annotations

from app.services.providers.http import client
from app.services.providers.types import ProviderResult
from app.settings import settings


class LushaProviderClient:
    provider_name = "lusha"

    def __init__(self) -> None:
        if not settings.lusha_api_key:
            raise RuntimeError("LUSHA_API_KEY is not configured")

    def get_account_usage(self) -> dict:
        with client() as c:
            r = c.get(
                "https://api.lusha.com/account/usage",
                headers={"api_key": settings.lusha_api_key},
            )
            r.raise_for_status()
            return r.json()

    def enrich(self, linkedin_url: str) -> ProviderResult:
        with client(timeout_s=30.0) as c:
            r = c.get(
                "https://api.lusha.com/v2/person",
                params={"linkedinUrl": linkedin_url},
                headers={"api_key": settings.lusha_api_key},
            )
            r.raise_for_status()
            data = r.json() or {}

        contact = (data.get("data") or {}).get("contact") or data.get("contact") or {}

        full_name = contact.get("fullName") or contact.get("name")
        current_company = None
        current_designation = None
        employment = contact.get("employment") or {}
        if isinstance(employment, dict):
            current_company = employment.get("company") or employment.get("companyName")
            current_designation = employment.get("title") or employment.get("jobTitle")

        emails: list[str] = []
        for e in contact.get("emails") or []:
            if isinstance(e, dict):
                v = e.get("email")
            else:
                v = e
            if isinstance(v, str):
                emails.append(v)

        phones: list[str] = []
        for p in contact.get("phones") or []:
            if isinstance(p, dict):
                v = p.get("phone")
            else:
                v = p
            if isinstance(v, str):
                phones.append(v)

        # Lusha exposes if a credit was charged, but not exact cost per call in response.
        is_credit_charged = bool(contact.get("isCreditCharged")) if isinstance(contact, dict) else False

        return ProviderResult(
            provider=self.provider_name,
            provider_ref=None,
            full_name=full_name,
            current_company=current_company,
            current_designation=current_designation,
            emails=sorted({e.strip() for e in emails if e.strip()}) or None,
            phones=sorted({p.strip() for p in phones if p.strip()}) or None,
            work_history=None,
            raw=data,
            cost_usd=None,
            cost_units=1.0 if is_credit_charged else 0.0,
            unit_name="credits_contact_request",
            is_estimated_cost=True,
            cost_note="Lusha response indicates isCreditCharged; exact credit breakdown depends on returned datapoints",
        )

