from __future__ import annotations

from app.services.providers.http import client
from app.services.providers.types import ProviderResult
from app.settings import settings


class ApolloProviderClient:
    provider_name = "apollo"
    base_url = "https://api.apollo.io/api/v1"

    def __init__(self) -> None:
        if not settings.apollo_api_key:
            raise RuntimeError("APOLLO_API_KEY is not configured")

    def usage_stats(self) -> dict:
        # Apollo usage stats endpoint (rate limits/quota per endpoint)
        with client() as c:
            r = c.get(
                f"{self.base_url}/usage_stats/api_usage_stats",
                headers={"X-Api-Key": settings.apollo_api_key},
            )
            r.raise_for_status()
            return r.json()

    def enrich_person(self, linkedin_url: str, *, reveal_emails: bool = True) -> ProviderResult:
        with client(timeout_s=30.0) as c:
            r = c.post(
                f"{self.base_url}/people/match",
                params={
                    "linkedin_url": linkedin_url,
                    "reveal_personal_emails": bool(reveal_emails),
                    "reveal_phone_number": False,
                },
                headers={"Cache-Control": "no-cache", "X-Api-Key": settings.apollo_api_key},
            )
            r.raise_for_status()
            data = r.json() or {}

        person = data.get("person") or {}
        full_name = person.get("name")
        current_company = (person.get("organization") or {}).get("name")
        current_designation = person.get("title")

        emails: list[str] = []
        if isinstance(person.get("email"), str):
            emails.append(person["email"])
        for e in person.get("personal_emails") or []:
            if isinstance(e, str):
                emails.append(e)

        phones: list[str] = []
        for p in person.get("phone_numbers") or person.get("phones") or []:
            if isinstance(p, dict):
                v = p.get("sanitized_number") or p.get("raw_number") or p.get("number")
            else:
                v = p
            if isinstance(v, str):
                phones.append(v)

        work_history = None
        employment_history = person.get("employment_history")
        if isinstance(employment_history, list):
            work_history = []
            for item in employment_history:
                if not isinstance(item, dict):
                    continue
                work_history.append(
                    {
                        "company": item.get("organization_name"),
                        "title": item.get("title"),
                        "start": item.get("start_date"),
                        "end": item.get("end_date"),
                        "is_current": bool(item.get("current")),
                    }
                )

        try:
            credits_consumed = float(data["credits_consumed"]) if data.get("credits_consumed") is not None else None
        except (TypeError, ValueError):
            credits_consumed = None

        return ProviderResult(
            provider=self.provider_name,
            provider_ref=person.get("id"),
            full_name=full_name,
            current_company=current_company,
            current_designation=current_designation,
            emails=sorted({e.strip() for e in emails if e.strip()}) or None,
            phones=sorted({p.strip() for p in phones if p.strip()}) or None,
            work_history=work_history,
            raw=data,
            cost_usd=None,
            cost_units=credits_consumed,
            unit_name="credits",
            is_estimated_cost=True,
            cost_note="Apollo credit usage is plan-dependent; tracked via usage stats snapshots",
        )

    def request_phone_webhook(self, linkedin_url: str, *, webhook_url: str) -> ProviderResult:
        # Phone reveal is async and requires webhook_url.
        with client(timeout_s=30.0) as c:
            r = c.post(
                f"{self.base_url}/people/match",
                params={
                    "linkedin_url": linkedin_url,
                    "reveal_phone_number": True,
                    "webhook_url": webhook_url,
                },
                headers={"Cache-Control": "no-cache", "X-Api-Key": settings.apollo_api_key},
            )
            r.raise_for_status()
            data = r.json() or {}
        person = data.get("person") or {}
        return ProviderResult(
            provider=self.provider_name,
            provider_ref=person.get("id"),
            raw=data,
            cost_usd=None,
            cost_units=None,
            unit_name="credits",
            is_estimated_cost=True,
            cost_note="Apollo phone delivered asynchronously via webhook",
        )
