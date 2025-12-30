from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, List

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from core import io as io_utils
from core import storage
from core.models import ArtifactRecord, StepRecord
from core import schema
from core.settings import load_settings
from plugins.base import AnalysisResult, BasePlugin
from plugins.edocument_audit import rules


class EDocumentAuditPlugin(BasePlugin):
    name = "edocument_audit"
    description = "Audit e-Documents with rule checks and 3-way match."
    expected_inputs = ["invoices", "purchase_orders", "delivery_notes"]

    def analyze(self, inputs: Dict[str, Path], llm, run_id: str) -> AnalysisResult:
        for required in self.expected_inputs:
            if required not in inputs:
                raise ValueError(f"Eksik girdi: {required}")

        run_dir = storage.ensure_run_dir(run_id)
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        steps: List[StepRecord] = []
        issues: List[rules.Issue] = []
        recommendations: List[dict] = []

        settings = load_settings()
        start = time.monotonic()
        mapping = schema.load_mapping(run_id)
        invoices = schema.load_csv_with_schema(
            inputs["invoices"],
            schema.get_input_schema("edoc", "invoices"),
            mapping.get("invoices"),
            settings,
        )
        purchase_orders = schema.load_csv_with_schema(
            inputs["purchase_orders"],
            schema.get_input_schema("edoc", "purchase_orders"),
            mapping.get("purchase_orders"),
            settings,
        )
        delivery_notes = schema.load_csv_with_schema(
            inputs["delivery_notes"],
            schema.get_input_schema("edoc", "delivery_notes"),
            mapping.get("delivery_notes"),
            settings,
        )
        steps.append(
            StepRecord(
                title="Girdiler yüklendi",
                action="LOAD_INPUTS",
                severity="info",
                evidence=[
                    f"invoices={len(invoices)}",
                    f"purchase_orders={len(purchase_orders)}",
                    f"delivery_notes={len(delivery_notes)}",
                ],
                decision="Girdiler başarıyla yüklendi",
                requires_approval=False,
                status="done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        start = time.monotonic()
        if settings.chunk_size:
            duplicate_ids = self._find_duplicates_chunked(
                inputs["invoices"], mapping.get("invoices"), settings
            )
            duplicate_issues = [
                rules.Issue(
                    issue_id=f"dup-{invoice_id}",
                    invoice_id=str(invoice_id),
                    severity="high",
                    rule="DUPLICATE_INVOICE",
                    details=f"Mükerrer invoice_id tespit edildi: {invoice_id}",
                )
                for invoice_id in duplicate_ids
            ]
        else:
            duplicate_issues = rules.find_duplicate_invoices(invoices)
        issues.extend(duplicate_issues)
        steps.append(
            StepRecord(
                title="Mükerrer fatura kontrolü",
                action="DUPLICATE_CHECK",
                severity="high" if duplicate_issues else "info",
                evidence=[i.details for i in duplicate_issues],
                decision=("Mükerrer kayıt bulundu" if duplicate_issues else "Mükerrer kayıt yok"),
                requires_approval=False,
                status="done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        start = time.monotonic()
        total_issues, total_fixes = rules.find_total_mismatch(invoices)
        issues.extend(total_issues)
        for fix in total_fixes:
            recommendations.append(
                {
                    "invoice_id": fix.invoice_id,
                    "field": fix.field,
                    "suggested_value": fix.suggested_value,
                    "reason": fix.reason,
                }
            )
        steps.append(
            StepRecord(
                title="Toplam hesap kontrolü",
                action="TOTAL_CHECK",
                severity="medium" if total_issues else "info",
                evidence=[i.details for i in total_issues],
                decision=(
                    "Toplam uyuşmazlığı bulundu" if total_issues else "Toplamlar doğru"
                ),
                requires_approval=bool(total_fixes),
                status="needs_approval" if total_fixes else "done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        start = time.monotonic()
        vat_issues, vat_fixes = rules.find_vat_mismatch(invoices)
        issues.extend(vat_issues)
        for fix in vat_fixes:
            recommendations.append(
                {
                    "invoice_id": fix.invoice_id,
                    "field": fix.field,
                    "suggested_value": fix.suggested_value,
                    "reason": fix.reason,
                }
            )
        steps.append(
            StepRecord(
                title="KDV hesap kontrolü",
                action="VAT_CHECK",
                severity="medium" if vat_issues else "info",
                evidence=[i.details for i in vat_issues],
                decision=("KDV uyuşmazlığı bulundu" if vat_issues else "KDV doğru"),
                requires_approval=bool(vat_fixes),
                status="needs_approval" if vat_fixes else "done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        start = time.monotonic()
        missing_links = rules.find_missing_po_dn(
            invoices, purchase_orders, delivery_notes
        )
        issues.extend(missing_links)
        steps.append(
            StepRecord(
                title="PO/DN varlık kontrolü",
                action="LINK_CHECK",
                severity="high" if missing_links else "info",
                evidence=[i.details for i in missing_links],
                decision=("Eksik referans bulundu" if missing_links else "Referanslar tamam"),
                requires_approval=False,
                status="done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        start = time.monotonic()
        three_way_issues = rules.find_three_way_mismatch(
            invoices, purchase_orders, delivery_notes
        )
        issues.extend(three_way_issues)
        steps.append(
            StepRecord(
                title="3 taraflı mutabakat",
                action="THREE_WAY_MATCH",
                severity="medium" if three_way_issues else "info",
                evidence=[i.details for i in three_way_issues],
                decision=(
                    "3 taraflı uyuşmazlık bulundu" if three_way_issues else "3 taraflı mutabakat tamam"
                ),
                requires_approval=False,
                status="done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        allowed_vendors = self._load_vendors(inputs.get("vendors"))
        if allowed_vendors is not None:
            start = time.monotonic()
            vendor_issues = rules.find_unapproved_vendors(invoices, allowed_vendors)
            issues.extend(vendor_issues)
            steps.append(
                StepRecord(
                    title="Tedarikçi doğrulama",
                    action="VENDOR_CHECK",
                    severity="high" if vendor_issues else "info",
                    evidence=[i.details for i in vendor_issues],
                    decision=(
                        "İzinsiz tedarikçi bulundu"
                        if vendor_issues
                        else "Tedarikçiler doğrulandı"
                    ),
                    requires_approval=False,
                    status="done",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            )

        allowed_rates = self._load_allowed_rates(inputs.get("allowed_vat_rates"))
        if allowed_rates is not None:
            start = time.monotonic()
            rate_issues = rules.find_disallowed_vat_rates(invoices, allowed_rates)
            issues.extend(rate_issues)
            steps.append(
                StepRecord(
                    title="KDV oranı doğrulama",
                    action="VAT_RATE_CHECK",
                    severity="medium" if rate_issues else "info",
                    evidence=[i.details for i in rate_issues],
                    decision=(
                        "İzinli olmayan KDV oranı bulundu"
                        if rate_issues
                        else "KDV oranları doğrulandı"
                    ),
                    requires_approval=False,
                    status="done",
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
            )

        issues_df = pd.DataFrame([issue.__dict__ for issue in issues])
        issues_path = artifacts_dir / "issues.csv"
        issues_df.to_csv(issues_path, index=False)

        summary_payload = self._build_summary(issues_df)
        summary_path = artifacts_dir / "summary.json"
        summary_path.write_text(
            json.dumps(summary_payload, indent=2, ensure_ascii=True), encoding="utf-8"
        )

        summary = f"Fatura sayısı: {len(invoices)}. Bulgu sayısı: {len(issues_df)}."
        report_path = run_dir / "report.pdf"
        self._write_report(report_path, summary, issues_df, None, len(invoices))

        artifacts = [
            ArtifactRecord(type="pdf", path=str(report_path)),
            ArtifactRecord(type="csv", path=str(issues_path)),
            ArtifactRecord(type="json", path=str(summary_path)),
            ArtifactRecord(type="json", path=str(run_dir / "recommendations.json")),
        ]

        return AnalysisResult(
            steps=steps,
            final_summary=summary,
            artifacts=artifacts,
            recommendations=recommendations,
        )

    def apply(
        self, inputs: Dict[str, Path], recommendations: List[dict], run_id: str
    ) -> List[ArtifactRecord]:
        run_dir = storage.ensure_run_dir(run_id)
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        settings = load_settings()
        mapping = schema.load_mapping(run_id)
        invoices = schema.load_csv_with_schema(
            inputs["invoices"],
            schema.get_input_schema("edoc", "invoices"),
            mapping.get("invoices"),
            settings,
        )
        if not recommendations:
            return []

        applied_notes = []
        for rec in recommendations:
            invoice_id = rec.get("invoice_id")
            field = rec.get("field")
            value = rec.get("suggested_value")
            if field not in {"total", "vat_amount"}:
                continue
            invoices.loc[invoices["invoice_id"].astype(str) == str(invoice_id), field] = value
            applied_notes.append(f"{invoice_id} -> {field}={value}")

        corrected_path = artifacts_dir / "corrected_invoices.csv"
        invoices.to_csv(corrected_path, index=False)

        issues_path = artifacts_dir / "issues.csv"
        if issues_path.exists():
            issues_df = pd.read_csv(issues_path)
            report_path = run_dir / "report.pdf"
            summary = f"Fatura sayısı: {len(invoices)}. Bulgu sayısı: {len(issues_df)}."
            self._write_report(report_path, summary, issues_df, applied_notes, len(invoices))

        return [ArtifactRecord(type="csv", path=str(corrected_path))]

    def _build_summary(self, issues_df: pd.DataFrame) -> dict:
        counts = (
            issues_df["severity"].value_counts().to_dict()
            if not issues_df.empty
            else {}
        )
        top = []
        for _, row in issues_df.head(5).iterrows():
            top.append(
                {
                    "issue_id": row.get("issue_id"),
                    "details": row.get("details"),
                }
            )
        return {"counts_by_severity": counts, "top_issues": top}

    def _find_duplicates_chunked(
        self,
        path: Path,
        mapping: Dict[str, str] | None,
        settings,
    ) -> List[str]:
        invoice_col = mapping.get("invoice_id") if mapping else "invoice_id"
        seen = set()
        duplicates = set()
        for chunk in io_utils.iter_csv_chunks(
            path,
            usecols=[invoice_col],
            dtype={invoice_col: "string"},
            nrows=settings.max_rows,
            chunksize=settings.chunk_size,
        ):
            if invoice_col not in chunk.columns:
                continue
            for value in chunk[invoice_col].dropna().astype(str):
                if value in seen:
                    duplicates.add(value)
                else:
                    seen.add(value)
        return sorted(duplicates)

    def _load_vendors(self, path: Path | None) -> List[str] | None:
        if path is None:
            return None
        df = pd.read_csv(path)
        if df.empty:
            return []
        for column in ["vendor", "name", "tedarikci", "firma"]:
            if column in df.columns:
                return [str(value).strip() for value in df[column].dropna().tolist()]
        return [str(value).strip() for value in df.iloc[:, 0].dropna().tolist()]

    def _load_allowed_rates(self, path: Path | None) -> List[float] | None:
        if path is None:
            return None
        if path.suffix.lower() == ".json":
            with path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, dict):
                payload = (
                    payload.get("allowed_vat_rates")
                    or payload.get("rates")
                    or payload.get("vat_rates")
                )
            if isinstance(payload, list):
                return [value for value in payload]
            return []
        df = pd.read_csv(path)
        if df.empty:
            return []
        for column in ["vat_rate", "rate", "kdv", "kdv_orani"]:
            if column in df.columns:
                return [value for value in df[column].dropna().tolist()]
        return [value for value in df.iloc[:, 0].dropna().tolist()]

    def _write_report(
        self,
        path: Path,
        summary: str,
        issues_df: pd.DataFrame,
        applied_fixes: List[str] | None,
        total_records: int,
    ) -> None:
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(path), pagesize=letter)
        elements = [
            Paragraph("ClarityAI e-Belge Denetim Raporu", styles["Title"]),
            Spacer(1, 12),
            Paragraph("Yönetici Özeti", styles["Heading2"]),
            Paragraph(f"Toplam kayıt: {total_records}", styles["Normal"]),
            Paragraph(f"Toplam bulgu: {len(issues_df)}", styles["Normal"]),
        ]

        if not issues_df.empty:
            counts = issues_df["severity"].value_counts().to_dict()
            severity_labels = {
                "info": "BİLGİ",
                "low": "DÜŞÜK",
                "medium": "ORTA",
                "high": "YÜKSEK",
            }
            counts_text = " ".join(
                f"{severity_labels.get(severity, severity)}={count}"
                for severity, count in counts.items()
            )
            elements.append(Paragraph(f"Önem dağılımı: {counts_text}", styles["Normal"]))
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("En kritik 5 bulgu", styles["Heading3"]))
            for _, row in issues_df.head(5).iterrows():
                elements.append(
                    Paragraph(
                        f"{row.get('issue_id')}: {row.get('details')}",
                        styles["Normal"],
                    )
                )

        if applied_fixes:
            elements.append(Spacer(1, 8))
            elements.append(Paragraph("Uygulanan düzeltmeler", styles["Heading3"]))
            for note in applied_fixes[:10]:
                elements.append(Paragraph(note, styles["Normal"]))

        elements.extend(
            [
                Spacer(1, 12),
                Paragraph(summary, styles["Normal"]),
                Spacer(1, 12),
            ]
        )

        table_data = [["Bulgu ID", "Fatura", "Önem", "Kural"]]
        for _, row in issues_df.head(20).iterrows():
            table_data.append(
                [
                    str(row.get("issue_id")),
                    str(row.get("invoice_id")),
                    str(row.get("severity")),
                    str(row.get("rule")),
                ]
            )
        table = Table(table_data)
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ]
            )
        )
        elements.append(table)
        doc.build(elements)
