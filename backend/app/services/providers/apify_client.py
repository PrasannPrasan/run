from __future__ import annotations

from urllib.parse import quote

from app.services.providers.http import client
from app.services.providers.types import ProviderResult
from app.settings import settings


def _first_text(*values: object) -> str | None:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _split_date_range(value: object) -> tuple[str | None, str | None, bool]:
    if not isinstance(value, str) or not value.strip():
        return None, None, False
    text = value.strip()
    for sep in [" - ", " – ", " — ", "-", "–", "—"]:
        if sep in text:
            left, right = text.split(sep, 1)
            end = right.strip() or None
            return left.strip() or None, end, bool(end and end.lower() == "present")
    return text, None, False


class ApifyProviderClient:
    provider_name = "apify"

    def __init__(self) -> None:
        if not settings.apify_token:
            raise RuntimeError("APIFY_TOKEN is not configured")
        self.actor_id = quote(settings.apify_actor_id.replace("/", "~"), safe="")

    def enrich(self, linkedin_url: str) -> ProviderResult:
        # Runs an actor and waits for finish. Uses actor id like `anchor~linkedin-profile-enrichment`.
        # Apify API: POST /v2/acts/{actorId}/runs?waitForFinish=...
        with client(timeout_s=120.0) as c:
            run_resp = c.post(
                f"https://api.apify.com/v2/acts/{self.actor_id}/runs",
                params={"token": settings.apify_token, "waitForFinish": 120},
                json={
                    "startUrls": [{"url": linkedin_url}],
                    # Kept for compatibility with other configured LinkedIn profile actors.
                    "profileUrls": [linkedin_url],
                },
            )
            run_resp.raise_for_status()
            run = run_resp.json().get("data") or {}

            dataset_id = run.get("defaultDatasetId")
            run_id = run.get("id")
            usage_usd = run.get("usageTotalUsd") or run.get("usageUsd")

            items: list[dict] = []
            if dataset_id:
                items_resp = c.get(
                    f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                    params={"token": settings.apify_token, "clean": "true", "format": "json"},
                )
                items_resp.raise_for_status()
                items = items_resp.json() or []

        item = items[0] if items else {}

        full_name = _first_text(item.get("fullName"), item.get("full_name"), item.get("name"))
        current_company = _first_text(
            item.get("currentCompany"),
            item.get("currentCompanyName"),
            item.get("companyName"),
            item.get("company"),
        )
        current_designation = _first_text(
            item.get("currentTitle"),
            item.get("currentJobTitle"),
            item.get("currentDesignation"),
            item.get("jobTitle"),
            item.get("title"),
        )

        # Common shapes across actors
        headline = item.get("headline") or item.get("subtitle")
        if isinstance(headline, str) and " at " in headline:
            current_designation, current_company = headline.split(" at ", 1)

        emails = []
        for v in [item.get("email"), item.get("emails"), item.get("emailAddress")]:
            if isinstance(v, str) and v:
                emails.append(v)
            elif isinstance(v, list):
                emails.extend([x for x in v if isinstance(x, str)])

        work_history = None
        exp = item.get("experience") or item.get("experiences") or item.get("positions")
        if isinstance(exp, list):
            work_history = []
            for e in exp:
                if not isinstance(e, dict):
                    continue
                company = _first_text(e.get("companyName"), e.get("company"), e.get("organization"))
                title = _first_text(e.get("title"), e.get("position"), e.get("role"))
                start = _first_text(e.get("startDate"), e.get("start"), e.get("start_date"))
                end = _first_text(e.get("endDate"), e.get("end"), e.get("end_date"))
                range_start, range_end, range_current = _split_date_range(
                    e.get("dateRange") or e.get("date_range") or e.get("period")
                )
                start = start or range_start
                end = end or range_end
                is_current = bool(e.get("isCurrent") or e.get("current") or range_current)
                if is_current:
                    current_company = current_company or company
                    current_designation = current_designation or title
                work_history.append(
                    {
                        "company": company,
                        "title": title,
                        "start": start,
                        "end": None if end and end.lower() == "present" else end,
                        "is_current": is_current,
                    }
                )

        return ProviderResult(
            provider=self.provider_name,
            provider_ref=run_id,
            full_name=full_name,
            current_company=current_company,
            current_designation=current_designation,
            emails=sorted({e.strip() for e in emails if isinstance(e, str) and e.strip()}) or None,
            phones=None,
            work_history=work_history,
            raw=item if item else None,
            cost_usd=float(usage_usd) if usage_usd is not None else None,
            cost_units=None,
            unit_name=None,
            is_estimated_cost=False,
            cost_note="Apify usageUsd from run object" if usage_usd is not None else None,
        )
