from __future__ import annotations

from app.services.providers.http import client
from app.services.providers.types import ProviderResult
from app.settings import settings


class RocketReachProviderClient:
    provider_name = "rocketreach"

    def __init__(self) -> None:
        if not settings.rocketreach_api_key:
            raise RuntimeError("ROCKETREACH_API_KEY is not configured")
        self.base_url = settings.rocketreach_base_url.rstrip("/")

    def account(self) -> dict:
        with client() as c:
            r = c.get(
                f"{self.base_url}/account",
                headers={"Api-Key": settings.rocketreach_api_key},
            )
            r.raise_for_status()
            return r.json()

    def lookup(self, linkedin_url: str) -> ProviderResult:
        with client(timeout_s=30.0) as c:
            headers = {"Api-Key": settings.rocketreach_api_key}
            params = {"linkedin_url": linkedin_url}
            r = c.get(f"{self.base_url}/person/lookup", params=params, headers=headers)
            if r.status_code == 404:
                r = c.get(f"{self.base_url}/profile-company/lookup", params=params, headers=headers)
            r.raise_for_status()
            data = r.json() or {}

        person = data.get("person") or data
        full_name = person.get("name")
        current_company = person.get("current_company") or person.get("current_company_name")
        current_designation = person.get("current_title")

        current_employer = person.get("current_employer") or {}
        if isinstance(current_employer, dict):
            current_company = current_company or current_employer.get("name")
        elif isinstance(current_employer, str):
            current_company = current_company or current_employer.strip() or None

        emails: list[str] = []
        for e in (person.get("emails") or []):
            if isinstance(e, dict):
                v = e.get("email")
            else:
                v = e
            if isinstance(v, str):
                emails.append(v)

        phones: list[str] = []
        for p in (person.get("phones") or []):
            if isinstance(p, dict):
                v = p.get("number") or p.get("phone")
            else:
                v = p
            if isinstance(v, str):
                phones.append(v)

        work_history = None
        jobs = person.get("current_positions") or person.get("employment_history") or person.get("job_history")
        if isinstance(jobs, list):
            work_history = []
            for j in jobs:
                if not isinstance(j, dict):
                    continue
                work_history.append(
                    {
                        "company": (
                            (j.get("organization") or {}).get("name")
                            if isinstance(j.get("organization"), dict)
                            else j.get("organization")
                        )
                        or j.get("company_name")
                        or j.get("company"),
                        "title": j.get("title"),
                        "start": j.get("start_date") or j.get("start"),
                        "end": j.get("end_date") or j.get("end"),
                        "is_current": bool(j.get("is_current")),
                    }
                )

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
            cost_units=None,
            unit_name="credits",
            is_estimated_cost=True,
            cost_note="RocketReach per-call credit usage is inferred; use /v2/account snapshots for deltas",
        )
