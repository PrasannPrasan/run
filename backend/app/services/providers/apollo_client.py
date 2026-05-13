from __future__ import annotations

import re
from typing import Any

import httpx

from app.services.providers.http import client
from app.services.providers.types import ProviderResult
from app.settings import settings


class ApolloProviderClient:
    provider_name = "apollo"
    base_url = "https://api.apollo.io/api/v1"

    def __init__(self) -> None:
        if not settings.apollo_api_key:
            raise RuntimeError("APOLLO_API_KEY is not configured")

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Cache-Control": "no-cache",
            "Content-Type": "application/json",
            "X-Api-Key": settings.apollo_api_key or "",
        }

    def usage_stats(self) -> dict:
        # Apollo documents this as POST and some accounts reject GET.
        with client() as c:
            r = c.post(
                f"{self.base_url}/usage_stats/api_usage_stats",
                headers=self._headers(),
            )
            self._raise_for_status(r)
            return r.json()

    def enrich_person(self, linkedin_url: str, *, reveal_emails: bool = True) -> ProviderResult:
        with client(timeout_s=30.0) as c:
            r = c.post(
                f"{self.base_url}/people/match",
                json={
                    "linkedin_url": linkedin_url,
                    "reveal_personal_emails": bool(reveal_emails),
                    "reveal_phone_number": False,
                },
                headers=self._headers(),
            )
            if self._is_plan_blocked(r):
                return self._search_existing_contact(c, linkedin_url, plan_error=self._error_message(r))
            self._raise_for_status(r)
            data = r.json() or {}

        return self._result_from_person_match(data)

    def request_phone_webhook(self, linkedin_url: str, *, webhook_url: str) -> ProviderResult:
        # Phone reveal is async and requires webhook_url.
        with client(timeout_s=30.0) as c:
            r = c.post(
                f"{self.base_url}/people/match",
                json={
                    "linkedin_url": linkedin_url,
                    "reveal_phone_number": True,
                    "webhook_url": webhook_url,
                },
                headers=self._headers(),
            )
            if self._is_plan_blocked(r):
                return ProviderResult(
                    provider=self.provider_name,
                    provider_ref=None,
                    raw={
                        "status": "skipped_plan_blocked",
                        "apollo_error": self._error_message(r),
                    },
                    cost_usd=0.0,
                    cost_units=0.0,
                    unit_name="credits",
                    is_estimated_cost=True,
                    cost_note="Apollo phone reveal skipped: people/match is blocked by this Apollo plan",
                )
            self._raise_for_status(r)
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

    def _result_from_person_match(self, data: dict[str, Any], *, cost_note: str | None = None) -> ProviderResult:
        person = data.get("person") or {}
        return self._result_from_record(
            person,
            raw=data,
            provider_ref=person.get("id"),
            credits_consumed=data.get("credits_consumed"),
            cost_note=cost_note or "Apollo credit usage is plan-dependent; tracked via usage stats snapshots",
        )

    def _result_from_record(
        self,
        record: dict[str, Any],
        *,
        raw: dict[str, Any],
        provider_ref: str | None,
        credits_consumed: object = None,
        cost_note: str,
    ) -> ProviderResult:
        full_name = self._full_name(record)
        current_company = (
            record.get("organization_name")
            or record.get("company")
            or (record.get("account") or {}).get("name")
            or (record.get("organization") or {}).get("name")
        )
        current_designation = record.get("title") or record.get("headline")

        try:
            cost_units = float(credits_consumed) if credits_consumed is not None else None
        except (TypeError, ValueError):
            cost_units = None

        return ProviderResult(
            provider=self.provider_name,
            provider_ref=provider_ref,
            full_name=full_name,
            current_company=current_company,
            current_designation=current_designation,
            emails=self._emails(record),
            phones=self._phones(record),
            work_history=self._work_history(record),
            raw=raw,
            cost_usd=None,
            cost_units=cost_units,
            unit_name="credits",
            is_estimated_cost=True,
            cost_note=cost_note,
        )

    def _search_existing_contact(
        self,
        c: httpx.Client,
        linkedin_url: str,
        *,
        plan_error: str,
    ) -> ProviderResult:
        # Free Apollo plans can authenticate but still block net-new People Enrichment.
        # Contacts search is available on that key and can return data already saved in the Apollo workspace.
        latest_raw: dict[str, Any] = {}
        for query in self._contact_search_queries(linkedin_url):
            r = c.post(
                f"{self.base_url}/contacts/search",
                json={"q_keywords": query, "page": 1, "per_page": 5},
                headers=self._headers(),
            )
            self._raise_for_status(r)
            latest_raw = r.json() or {}
            contacts = latest_raw.get("contacts") or []
            if not isinstance(contacts, list) or not contacts:
                continue
            contact = self._best_contact_match(contacts, linkedin_url)
            raw = {
                "status": "people_match_plan_blocked_contacts_search_match",
                "apollo_error": plan_error,
                "fallback_query": query,
                "fallback": latest_raw,
            }
            return self._result_from_record(
                contact,
                raw=raw,
                provider_ref=contact.get("id"),
                credits_consumed=0.0,
                cost_note="Apollo people/match is blocked by this Apollo plan; used existing contacts/search fallback",
            )

        return ProviderResult(
            provider=self.provider_name,
            provider_ref=None,
            raw={
                "status": "people_match_plan_blocked_contacts_search_no_match",
                "apollo_error": plan_error,
                "fallback": latest_raw,
            },
            cost_usd=0.0,
            cost_units=0.0,
            unit_name="credits",
            is_estimated_cost=True,
            cost_note=(
                "Apollo people/match is blocked by this Apollo plan; existing contacts/search fallback found no match"
            ),
        )

    def _contact_search_queries(self, linkedin_url: str) -> list[str]:
        public_id = self._linkedin_public_id(linkedin_url)
        queries = [linkedin_url.rstrip("/")]
        if public_id:
            queries.append(public_id)
            queries.append(public_id.replace("-", " "))
        unique: list[str] = []
        for query in queries:
            if query and query not in unique:
                unique.append(query)
        return unique

    def _best_contact_match(self, contacts: list[dict[str, Any]], linkedin_url: str) -> dict[str, Any]:
        wanted = linkedin_url.rstrip("/").lower()
        for contact in contacts:
            contact_url = str(contact.get("linkedin_url") or contact.get("linkedin_url_raw") or "").rstrip("/").lower()
            if contact_url and contact_url == wanted:
                return contact
        return contacts[0]

    def _linkedin_public_id(self, linkedin_url: str) -> str | None:
        match = re.search(r"linkedin\.com/in/([^/?#]+)/?", linkedin_url, flags=re.IGNORECASE)
        return match.group(1) if match else None

    def _full_name(self, record: dict[str, Any]) -> str | None:
        if isinstance(record.get("name"), str):
            return record["name"]
        parts = [record.get("first_name"), record.get("last_name")]
        name = " ".join(str(part).strip() for part in parts if part)
        return name or None

    def _emails(self, record: dict[str, Any]) -> list[str] | None:
        values: list[str] = []
        for key in ("email", "personal_email", "work_email"):
            if isinstance(record.get(key), str):
                values.append(record[key])
        for key in ("personal_emails", "emails"):
            for email in record.get(key) or []:
                if isinstance(email, str):
                    values.append(email)
                elif isinstance(email, dict) and isinstance(email.get("email"), str):
                    values.append(email["email"])
        return sorted({email.strip() for email in values if email.strip()}) or None

    def _phones(self, record: dict[str, Any]) -> list[str] | None:
        values: list[str] = []
        for key in ("direct_phone", "corporate_phone", "mobile_phone", "home_phone", "other_phone", "phone"):
            if isinstance(record.get(key), str):
                values.append(record[key])
        for phone in record.get("phone_numbers") or record.get("phones") or []:
            if isinstance(phone, dict):
                value = phone.get("sanitized_number") or phone.get("raw_number") or phone.get("number")
            else:
                value = phone
            if isinstance(value, str):
                values.append(value)
        return sorted({phone.strip() for phone in values if phone.strip()}) or None

    def _work_history(self, record: dict[str, Any]) -> list[dict] | None:
        employment_history = record.get("employment_history")
        if not isinstance(employment_history, list):
            return None

        work_history = []
        for item in employment_history:
            if not isinstance(item, dict):
                continue
            work_history.append(
                {
                    "company": item.get("organization_name") or (item.get("organization") or {}).get("name"),
                    "title": item.get("title"),
                    "start": item.get("start_date"),
                    "end": item.get("end_date"),
                    "is_current": bool(item.get("current")),
                }
            )
        return work_history or None

    def _json_error(self, response: httpx.Response) -> dict[str, Any]:
        try:
            data = response.json()
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def _is_plan_blocked(self, response: httpx.Response) -> bool:
        data = self._json_error(response)
        return response.status_code == 403 and data.get("error_code") == "API_INACCESSIBLE"

    def _error_message(self, response: httpx.Response) -> str:
        data = self._json_error(response)
        message = data.get("error") or data.get("message") or response.text or response.reason_phrase
        code = data.get("error_code")
        if code:
            return f"Apollo {response.status_code} {code}: {message}"
        return f"Apollo {response.status_code}: {message}"

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return
        raise RuntimeError(self._error_message(response))
