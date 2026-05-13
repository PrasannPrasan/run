from __future__ import annotations

from dataclasses import dataclass

from app.services.providers.apollo_client import ApolloProviderClient
from app.services.providers.lusha_client import LushaProviderClient
from app.services.providers.rocketreach_client import RocketReachProviderClient


@dataclass
class UsageSnapshot:
    provider: str
    units: float | None
    usd: float | None
    raw: dict


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


class CostTracker:
    def snapshot_lusha(self) -> UsageSnapshot | None:
        try:
            raw = LushaProviderClient().get_account_usage()
        except Exception:
            return None
        units = _to_float(raw.get("remainingCredits") or raw.get("creditsRemaining") or raw.get("remaining"))
        return UsageSnapshot(provider="lusha", units=units, usd=None, raw=raw)

    def snapshot_apollo(self) -> UsageSnapshot | None:
        try:
            raw = ApolloProviderClient().usage_stats()
        except Exception:
            return None
        # No single standard field for credits; keep raw and aggregate any "consumed" if present.
        units = _to_float(raw.get("consumed") or raw.get("credits_consumed"))
        return UsageSnapshot(provider="apollo", units=units, usd=None, raw=raw)

    def snapshot_rocketreach(self) -> UsageSnapshot | None:
        try:
            raw = RocketReachProviderClient().account()
        except Exception:
            return None
        units = _to_float(raw.get("credits") or raw.get("remaining_credits") or raw.get("remainingCredits"))
        return UsageSnapshot(provider="rocketreach", units=units, usd=None, raw=raw)

    def compute_unit_delta(self, before: UsageSnapshot | None, after: UsageSnapshot | None) -> float | None:
        if not before or not after:
            return None
        if before.units is None or after.units is None:
            return None
        # Remaining credits style: positive delta means usage.
        return round(before.units - after.units, 4)

