from __future__ import annotations

from typing import List, Tuple

import pandas as pd


def categorize_text(text: str, llm) -> str:
    if llm is None:
        return "general"
    return llm.categorize(text)


def safe_float(value) -> float | None:
    if value is None:
        return None
    if isinstance(value, str) and value.strip() == "":
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def missing_fields(row: pd.Series) -> List[str]:
    missing: List[str] = []
    order_id = row.get("order_id")
    amount = row.get("amount")
    if (
        order_id is None
        or (isinstance(order_id, float) and pd.isna(order_id))
        or str(order_id).strip() == ""
    ):
        missing.append("order_id")
    if (
        amount is None
        or (isinstance(amount, float) and pd.isna(amount))
        or str(amount).strip() == ""
    ):
        missing.append("amount")
    return missing


def priority_score(text: str, amount: float | None) -> Tuple[int, str]:
    lowered = (text or "").lower()
    score = 0
    if "iade" in lowered or "refund" in lowered or "return" in lowered:
        score += 2
    if "acil" in lowered or "urgent" in lowered or "hemen" in lowered:
        score += 2
    if "para" in lowered or "payment" in lowered or "charge" in lowered:
        score += 1
    amount_value = safe_float(amount)
    if amount_value is not None and amount_value > 1000:
        score += 1

    if score >= 4:
        severity = "high"
    elif score >= 2:
        severity = "medium"
    else:
        severity = "low"
    return score, severity
