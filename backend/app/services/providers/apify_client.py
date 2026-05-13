from __future__ import annotations

import time
from urllib.parse import quote

from app.services.providers.http import client
from app.services.providers.types import ProviderResult
from app.settings import settings


def _text(value: object) -> str | None:
    if isinstance(value, str) and value.strip():
        return value.strip()
    if isinstance(value, dict):
        for key in ("name", "title", "text", "value"):
            text = _text(value.get(key))
            if text:
                return text
    return None


def _first_text(*values: object) -> str | None:
    for value in values:
        text = _text(value)
        if text:
            return text
    return None


def _first_list(*values: object) -> list[dict]:
    for value in values:
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
    return []


def _profiles(item: dict) -> list[dict]:
    profiles = [item]
    for key in ("profile", "data", "result", "person"):
        nested = item.get(key)
        if isinstance(nested, dict):
            profiles.append(nested)
    return profiles


def _from_profiles(profiles: list[dict], *keys: str) -> str | None:
    for profile in profiles:
        for key in keys:
            text = _text(profile.get(key))
            if text:
                return text
    return None


def _split_date_range(value: object) -> tuple[str | None, str | None, bool]:
    text = _text(value)
    if not text:
        return None, None, False
    for sep in (" - ", " -", "- ", "-"):
        if sep in text:
            left, right = text.split(sep, 1)
            end = right.strip() or None
            return left.strip() or None, end, bool(end and end.lower() == "present")
    return text, None, False


def _collect_contact_strings(*values: object) -> list[str]:
    output: list[str] = []
    for value in values:
        text = _text(value)
        if text:
            output.append(text)
            continue
        if isinstance(value, list):
            for item in value:
                text = _text(item)
                if text:
                    output.append(text)
                elif isinstance(item, dict):
                    for key in ("email", "address", "value", "number", "phone"):
                        nested_text = _text(item.get(key))
                        if nested_text:
                            output.append(nested_text)
                            break
    return output


class ApifyProviderClient:
    provider_name = "apify"

    def __init__(self) -> None:
        if not settings.apify_token:
            raise RuntimeError("APIFY_TOKEN is not configured")
        self.actor_id = quote(settings.apify_actor_id.replace("/", "~"), safe="")

    def enrich(self, linkedin_url: str) -> ProviderResult:
        # Runs an actor and waits for finish. Uses actor id like `scrapemint~linkedin-profile-scraper`.
        with client(timeout_s=180.0) as c:
            run_resp = c.post(
                f"https://api.apify.com/v2/acts/{self.actor_id}/runs",
                params={"token": settings.apify_token, "waitForFinish": 120},
                json={
                    "profileUrls": [linkedin_url],
                    "startUrls": [{"url": linkedin_url}],
                    "includeExperience": True,
                    "includeEducation": True,
                    "includeSkills": True,
                },
            )
            run_resp.raise_for_status()
            run = run_resp.json().get("data") or {}

            run_id = run.get("id")
            usage_usd = run.get("usageTotalUsd") or run.get("usageUsd")
            dataset_id = run.get("defaultDatasetId")

            for _ in range(12):
                if run.get("status") in {"SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"}:
                    break
                if not run_id:
                    break
                time.sleep(5)
                run_state = c.get(
                    f"https://api.apify.com/v2/actor-runs/{run_id}",
                    params={"token": settings.apify_token},
                )
                run_state.raise_for_status()
                run = run_state.json().get("data") or run
                dataset_id = run.get("defaultDatasetId") or dataset_id
                usage_usd = run.get("usageTotalUsd") or run.get("usageUsd") or usage_usd

            items: list[dict] = []
            if dataset_id:
                items_resp = c.get(
                    f"https://api.apify.com/v2/datasets/{dataset_id}/items",
                    params={"token": settings.apify_token, "clean": "true", "format": "json"},
                )
                items_resp.raise_for_status()
                data = items_resp.json() or []
                items = [item for item in data if isinstance(item, dict)]

        item = items[0] if items else {}
        profiles = _profiles(item)

        full_name = _from_profiles(
            profiles,
            "fullName",
            "full_name",
            "profileName",
            "profile_name",
            "name",
            "publicIdentifier",
        )
        if not full_name:
            first = _from_profiles(profiles, "firstName", "first_name")
            last = _from_profiles(profiles, "lastName", "last_name")
            full_name = f"{first} {last}".strip() if first or last else None

        current_company = _from_profiles(
            profiles,
            "currentCompany",
            "currentCompanyName",
            "current_company",
            "companyName",
            "company_name",
            "company",
        )
        current_designation = _from_profiles(
            profiles,
            "currentTitle",
            "currentJobTitle",
            "currentDesignation",
            "current_title",
            "current_job_title",
            "jobTitle",
            "job_title",
            "title",
        )

        headline = _from_profiles(profiles, "headline", "subtitle", "occupation")
        if headline and " at " in headline:
            current_designation, current_company = headline.split(" at ", 1)

        emails = _collect_contact_strings(
            *[profile.get("email") for profile in profiles],
            *[profile.get("emails") for profile in profiles],
            *[profile.get("emailAddress") for profile in profiles],
        )
        phones = _collect_contact_strings(
            *[profile.get("phone") for profile in profiles],
            *[profile.get("phones") for profile in profiles],
            *[profile.get("phoneNumbers") for profile in profiles],
        )

        work_history = None
        exp: list[dict] = []
        for profile in profiles:
            exp = _first_list(
                profile.get("experience"),
                profile.get("experiences"),
                profile.get("positions"),
                profile.get("topExperience"),
                profile.get("top_experience"),
            )
            if exp:
                break

        if exp:
            work_history = []
            for entry in exp:
                company = _first_text(entry.get("companyName"), entry.get("company"), entry.get("organization"))
                title = _first_text(entry.get("title"), entry.get("position"), entry.get("role"))
                start = _first_text(entry.get("startDate"), entry.get("start"), entry.get("start_date"))
                end = _first_text(entry.get("endDate"), entry.get("end"), entry.get("end_date"))
                range_start, range_end, range_current = _split_date_range(
                    entry.get("dateRange") or entry.get("date_range") or entry.get("period") or entry.get("duration")
                )
                start = start or range_start
                end = end or range_end
                is_current = bool(entry.get("isCurrent") or entry.get("current") or range_current)
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
            emails=sorted({email.strip() for email in emails if email.strip()}) or None,
            phones=sorted({phone.strip() for phone in phones if phone.strip()}) or None,
            work_history=work_history,
            raw=item if item else None,
            cost_usd=float(usage_usd) if usage_usd is not None else None,
            cost_units=None,
            unit_name=None,
            is_estimated_cost=False,
            cost_note="Apify usageUsd from run object" if usage_usd is not None else None,
        )
