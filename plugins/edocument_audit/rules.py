from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd


TOLERANCE = 0.01


@dataclass
class Issue:
    issue_id: str
    invoice_id: str
    severity: str
    rule: str
    details: str
    suggested_fix: str | None = None


@dataclass
class FixRecommendation:
    invoice_id: str
    field: str
    suggested_value: float
    reason: str


def find_duplicate_invoices(df: pd.DataFrame) -> List[Issue]:
    issues: List[Issue] = []
    duplicates = df[df.duplicated(subset=["invoice_id"], keep=False)]
    if duplicates.empty:
        return issues
    for invoice_id in duplicates["invoice_id"].unique():
        issues.append(
            Issue(
                issue_id=f"dup-{invoice_id}",
                invoice_id=str(invoice_id),
                severity="high",
                rule="DUPLICATE_INVOICE",
                details=f"Mükerrer invoice_id tespit edildi: {invoice_id}",
            )
        )
    return issues


def find_total_mismatch(df: pd.DataFrame) -> Tuple[List[Issue], List[FixRecommendation]]:
    issues: List[Issue] = []
    fixes: List[FixRecommendation] = []
    for _, row in df.iterrows():
        invoice_id = str(row.get("invoice_id"))
        subtotal = float(row.get("subtotal", 0) or 0)
        vat_amount = float(row.get("vat_amount", 0) or 0)
        total = float(row.get("total", 0) or 0)
        expected_total = round(subtotal + vat_amount, 2)
        if abs(total - expected_total) > TOLERANCE:
            details = f"toplam={total} beklenen={expected_total}"
            issues.append(
                Issue(
                    issue_id=f"total-{invoice_id}",
                    invoice_id=invoice_id,
                    severity="medium",
                    rule="TOTAL_MISMATCH",
                    details=details,
                    suggested_fix=f"Toplamı {expected_total} olarak düzelt",
                )
            )
            fixes.append(
                FixRecommendation(
                    invoice_id=invoice_id,
                    field="total",
                    suggested_value=expected_total,
                    reason="subtotal + vat_amount",
                )
            )
    return issues, fixes


def find_vat_mismatch(df: pd.DataFrame) -> Tuple[List[Issue], List[FixRecommendation]]:
    issues: List[Issue] = []
    fixes: List[FixRecommendation] = []
    for _, row in df.iterrows():
        invoice_id = str(row.get("invoice_id"))
        subtotal = float(row.get("subtotal", 0) or 0)
        vat_rate = float(row.get("vat_rate", 0) or 0)
        vat_amount = float(row.get("vat_amount", 0) or 0)
        expected_vat = round(subtotal * vat_rate, 2)
        if abs(vat_amount - expected_vat) > TOLERANCE:
            details = f"kdv_tutarı={vat_amount} beklenen={expected_vat}"
            issues.append(
                Issue(
                    issue_id=f"vat-{invoice_id}",
                    invoice_id=invoice_id,
                    severity="medium",
                    rule="VAT_MISMATCH",
                    details=details,
                    suggested_fix=f"KDV tutarını {expected_vat} olarak düzelt",
                )
            )
            fixes.append(
                FixRecommendation(
                    invoice_id=invoice_id,
                    field="vat_amount",
                    suggested_value=expected_vat,
                    reason="subtotal * vat_rate",
                )
            )
    return issues, fixes


def find_missing_po_dn(
    invoices: pd.DataFrame, purchase_orders: pd.DataFrame, delivery_notes: pd.DataFrame
) -> List[Issue]:
    issues: List[Issue] = []
    po_ids = set(purchase_orders["po_id"].astype(str))
    dn_ids = set(delivery_notes["dn_id"].astype(str))
    for _, row in invoices.iterrows():
        invoice_id = str(row.get("invoice_id"))
        po_id = str(row.get("po_id"))
        dn_id = str(row.get("dn_id"))
        if po_id and po_id not in po_ids:
            issues.append(
                Issue(
                    issue_id=f"po-{invoice_id}",
                    invoice_id=invoice_id,
                    severity="high",
                    rule="MISSING_PO",
                    details=f"po_id {po_id} satınalma listesinde bulunamadı",
                )
            )
        if dn_id and dn_id not in dn_ids:
            issues.append(
                Issue(
                    issue_id=f"dn-{invoice_id}",
                    invoice_id=invoice_id,
                    severity="high",
                    rule="MISSING_DN",
                    details=f"dn_id {dn_id} irsaliye listesinde bulunamadı",
                )
            )
    return issues


def find_three_way_mismatch(
    invoices: pd.DataFrame, purchase_orders: pd.DataFrame, delivery_notes: pd.DataFrame
) -> List[Issue]:
    issues: List[Issue] = []
    po_lookup: Dict[str, float] = {}
    for _, row in purchase_orders.iterrows():
        po_lookup[str(row.get("po_id"))] = float(row.get("item_count", 0) or 0)
    dn_lookup: Dict[str, float] = {}
    for _, row in delivery_notes.iterrows():
        dn_lookup[str(row.get("dn_id"))] = float(
            row.get("delivered_item_count", 0) or 0
        )

    for _, row in invoices.iterrows():
        invoice_id = str(row.get("invoice_id"))
        po_id = str(row.get("po_id"))
        dn_id = str(row.get("dn_id"))
        if po_id in po_lookup and dn_id in dn_lookup:
            po_count = po_lookup[po_id]
            dn_count = dn_lookup[dn_id]
            if abs(po_count - dn_count) > 0:
                issues.append(
                    Issue(
                        issue_id=f"3way-{invoice_id}",
                        invoice_id=invoice_id,
                        severity="medium",
                        rule="THREE_WAY_MISMATCH",
                        details=f"po_kalem={po_count} dn_kalem={dn_count}",
                    )
                )
    return issues


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


def normalize_rate(value) -> float | None:
    parsed = safe_float(value)
    if parsed is None:
        return None
    if parsed > 1 and parsed <= 100:
        return round(parsed / 100, 4)
    return round(parsed, 4)


def find_unapproved_vendors(
    invoices: pd.DataFrame, allowed_vendors: List[str] | None
) -> List[Issue]:
    if not allowed_vendors:
        return []
    allowed = {vendor.strip().lower() for vendor in allowed_vendors if vendor}
    issues: List[Issue] = []
    for _, row in invoices.iterrows():
        invoice_id = str(row.get("invoice_id"))
        vendor = str(row.get("vendor") or "").strip()
        if not vendor:
            continue
        if vendor.lower() not in allowed:
            issues.append(
                Issue(
                    issue_id=f"vendor-{invoice_id}",
                    invoice_id=invoice_id,
                    severity="high",
                    rule="VENDOR_NOT_ALLOWED",
                    details=f"Tedarikçi izinli listede değil: {vendor}",
                )
            )
    return issues


def find_disallowed_vat_rates(
    invoices: pd.DataFrame, allowed_rates: List[float] | None
) -> List[Issue]:
    if not allowed_rates:
        return []
    normalized_rates = {normalize_rate(rate) for rate in allowed_rates}
    normalized_rates.discard(None)
    if not normalized_rates:
        return []
    issues: List[Issue] = []
    for _, row in invoices.iterrows():
        invoice_id = str(row.get("invoice_id"))
        vat_rate = normalize_rate(row.get("vat_rate"))
        if vat_rate is None:
            continue
        if vat_rate not in normalized_rates:
            issues.append(
                Issue(
                    issue_id=f"vat-rate-{invoice_id}",
                    invoice_id=invoice_id,
                    severity="medium",
                    rule="VAT_RATE_NOT_ALLOWED",
                    details=f"KDV oranı izinli listede değil: {vat_rate}",
                )
            )
    return issues
