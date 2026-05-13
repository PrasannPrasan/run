from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ProviderResult:
    provider: str
    provider_ref: str | None

    full_name: str | None = None
    current_company: str | None = None
    current_designation: str | None = None

    emails: list[str] | None = None
    phones: list[str] | None = None

    work_history: list[dict] | None = None  # flexible: {company,title,start,end,is_current}

    raw: dict | None = None

    # Cost tracking hints
    cost_usd: float | None = None
    cost_units: float | None = None
    unit_name: str | None = None
    is_estimated_cost: bool = False
    cost_note: str | None = None

