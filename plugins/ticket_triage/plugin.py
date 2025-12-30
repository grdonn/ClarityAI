from __future__ import annotations

import time
from pathlib import Path
from typing import Dict, List

import pandas as pd
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors

from core.models import ArtifactRecord, StepRecord
from core import storage
from core import schema
from core.settings import load_settings
from plugins.base import AnalysisResult, BasePlugin
from plugins.ticket_triage import rules


class TicketTriagePlugin(BasePlugin):
    name = "ticket_triage"
    description = "Analyze support tickets for category, missing info, and priority."
    expected_inputs = ["tickets"]

    def analyze(self, inputs: Dict[str, Path], llm, run_id: str) -> AnalysisResult:
        if "tickets" not in inputs:
            raise ValueError("tickets girdisi gerekli")

        run_dir = storage.ensure_run_dir(run_id)
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)

        steps: List[StepRecord] = []
        recommendations: List[dict] = []

        start = time.monotonic()
        mapping = schema.load_mapping(run_id).get("tickets")
        settings = load_settings()
        df = schema.load_csv_with_schema(
            inputs["tickets"],
            schema.get_input_schema("ticket", "tickets"),
            mapping,
            settings,
        )
        steps.append(
            StepRecord(
                title="Kayıtlar yüklendi",
                action="LOAD_TICKETS",
                severity="info",
                evidence=[f"rows={len(df)}"],
                decision="Kayıtlar başarıyla yüklendi",
                requires_approval=False,
                status="done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        start = time.monotonic()
        predicted_count = 0
        categories: List[str] = []
        for _, row in df.iterrows():
            current = row.get("category")
            text = str(row.get("customer_text") or "")
            if pd.isna(current) or current == "":
                predicted = rules.categorize_text(text, llm)
                predicted_count += 1
                categories.append(predicted)
            else:
                categories.append(str(current))
        df["predicted_category"] = categories
        steps.append(
            StepRecord(
                title="Kategori tahmini",
                action="CATEGORIZE",
                severity="info",
                evidence=[f"predicted_missing={predicted_count}"],
                decision="Kategori önerileri eklendi",
                requires_approval=False,
                status="done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        start = time.monotonic()
        missing_evidence: List[str] = []
        for _, row in df.iterrows():
            missing = rules.missing_fields(row)
            if missing:
                ticket_id = row.get("ticket_id", "unknown")
                missing_evidence.append(
                    f"ticket_id={ticket_id} missing={','.join(missing)}"
                )
                question = "Lütfen eksik bilgileri paylaşın: " + ", ".join(missing)
                recommendations.append(
                    {"ticket_id": ticket_id, "question": question}
                )
        if missing_evidence:
            decision = "Eksik bilgi tespit edildi"
            severity = "medium"
        else:
            decision = "Eksik bilgi bulunamadı"
            severity = "info"
        steps.append(
            StepRecord(
                title="Eksik bilgi kontrolü",
                action="MISSING_INFO",
                severity=severity,
                evidence=missing_evidence,
                decision=decision,
                requires_approval=False,
                status="done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        start = time.monotonic()
        severity_counts = {"high": 0, "medium": 0, "low": 0}
        high_priority_ids: List[str] = []
        for _, row in df.iterrows():
            amount = row.get("amount")
            score, severity = rules.priority_score(str(row.get("customer_text") or ""), amount)
            severity_counts[severity] += 1
            if severity == "high":
                high_priority_ids.append(str(row.get("ticket_id", "unknown")))
        decision = (
            f"High={severity_counts['high']} Medium={severity_counts['medium']} Low={severity_counts['low']}"
        )
        steps.append(
            StepRecord(
                title="Öncelik skoru",
                action="PRIORITY_SCORE",
                severity="low" if severity_counts["high"] == 0 else "medium",
                evidence=[f"high_priority={','.join(high_priority_ids)}"]
                if high_priority_ids
                else [],
                decision=decision,
                requires_approval=False,
                status="done",
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        )

        summary = (
            f"İncelenen kayıt: {len(df)}. Eksik bilgi: {len(missing_evidence)}. "
            f"Yüksek öncelik: {severity_counts['high']}."
        )

        report_path = run_dir / "report.pdf"
        self._write_report(report_path, summary, severity_counts, missing_evidence, len(df))

        email_path = artifacts_dir / "reply_email.txt"
        self._write_email(email_path, df, recommendations, llm)

        artifacts = [
            ArtifactRecord(type="pdf", path=str(report_path)),
            ArtifactRecord(type="email", path=str(email_path)),
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
        return []

    def _write_report(
        self,
        path: Path,
        summary: str,
        severity_counts: Dict[str, int],
        missing_evidence: List[str],
        total_records: int,
    ) -> None:
        styles = getSampleStyleSheet()
        doc = SimpleDocTemplate(str(path), pagesize=letter)
        elements = [
            Paragraph("ClarityAI Talep İnceleme Raporu", styles["Title"]),
            Spacer(1, 12),
            Paragraph("Yönetici Özeti", styles["Heading2"]),
            Paragraph(f"Toplam kayıt: {total_records}", styles["Normal"]),
            Paragraph(
                f"Bulgu dağılımı: Yüksek={severity_counts['high']} "
                f"Orta={severity_counts['medium']} Düşük={severity_counts['low']}",
                styles["Normal"],
            ),
            Spacer(1, 8),
            Paragraph(summary, styles["Normal"]),
            Spacer(1, 12),
        ]
        table_data = [
            ["Önem", "Sayı"],
            ["Yüksek", str(severity_counts["high"])],
            ["Orta", str(severity_counts["medium"])],
            ["Düşük", str(severity_counts["low"])],
        ]
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
        if missing_evidence:
            elements.append(Spacer(1, 12))
            elements.append(Paragraph("Eksik Bilgi", styles["Heading2"]))
            for item in missing_evidence[:20]:
                elements.append(Paragraph(item, styles["Normal"]))
        doc.build(elements)

    def _write_email(
        self,
        path: Path,
        df: pd.DataFrame,
        recommendations: List[dict],
        llm,
    ) -> None:
        lines = [
            "Merhaba,",
            "",
            "Talebinizi inceledik ve birkaç ek bilgiye ihtiyacımız var:",
        ]
        for rec in recommendations[:5]:
            lines.append(f"- Talep {rec['ticket_id']}: {rec['question']}")
        lines.append("")
        lines.append("Teşekkürler,")
        lines.append("Destek Ekibi")
        draft = "\n".join(lines)
        improved = llm.improve_email(draft) if llm else draft
        path.write_text(improved, encoding="utf-8")
