"""quote() - money the draft is allowed to use. Amounts formatted like '$1,234.00'."""

from __future__ import annotations

from datetime import date
from functools import lru_cache

import yaml
from pydantic import BaseModel

from app.settings import settings


@lru_cache(maxsize=1)
def _cfg() -> dict:
    return yaml.safe_load((settings.config_dir / "pricing.yaml").read_text())


def money(amount: float) -> str:
    return f"${amount:,.2f}"


def is_holiday(arrival: date) -> str | None:
    for h in _cfg().get("holidays", []):
        if date.fromisoformat(str(h["start"])) <= arrival <= date.fromisoformat(str(h["end"])):
            return h["name"]
    return None


class Quote(BaseModel):
    item: str
    unit_rate: str | None = None
    nights: int | None = None
    total: str | None = None
    deposit: str | None = None
    holiday_min_nights: int | None = None
    notes: list[str] = []


def quote(
    item: str,
    *,
    nights: int | None = None,
    length_ft: float | None = None,
    arrival: date | None = None,
) -> Quote:
    rates = _cfg()["rates"]
    notes: list[str] = []

    if item == "transient_slip":
        r = rates["transient_slip"]
        billable_ft = max(length_ft or 0, r["min_ft"])
        if length_ft and length_ft < r["min_ft"]:
            notes.append(f"charged at the {r['min_ft']}-ft minimum")
        nightly = billable_ft * r["per_ft_night"]
        hmin = _cfg()["holiday_min_nights"] if arrival and is_holiday(arrival) else None
        eff_nights = max(nights or 1, hmin or 0) if hmin else (nights or 1)
        return Quote(
            item=item,
            unit_rate=f"{money(nightly)}/night",
            nights=eff_nights,
            total=money(nightly * eff_nights),
            deposit=money(nightly),
            holiday_min_nights=hmin,
            notes=notes,
        )

    if item == "seasonal_slip":
        r = rates["seasonal_slip"]
        season = (length_ft or 0) * r["per_ft_season"]
        return Quote(
            item=item,
            unit_rate=f"{money(r['per_ft_season'])}/ft for the season",
            total=money(season),
            deposit=money(season * 0.25),
            notes=["25% deposit at signing (P3)"],
        )

    if item in {"campsite_rv_full", "campsite_rv_we", "campsite_tent"}:
        nightly = rates[item]["per_night"]
        n = nights or 1
        return Quote(
            item=item,
            unit_rate=f"{money(nightly)}/night",
            nights=n,
            total=money(nightly * n),
            deposit=money(nightly),
        )

    if item == "haul_out":
        per_ft = rates["haul_out"]["per_ft"]
        return Quote(
            item=item,
            unit_rate=f"{money(per_ft)}/ft",
            total=money(per_ft * (length_ft or 0)),
            notes=["winterization and storage are quoted by the boatyard (P12)"],
        )

    if item == "launch_ramp":
        return Quote(item=item, unit_rate=f"{money(rates['launch_ramp']['per_day'])}/day")

    if item == "trailer_parking":
        return Quote(item=item, unit_rate=f"{money(rates['trailer_parking']['per_day'])}/day")

    raise ValueError(f"unknown quote item: {item}")
