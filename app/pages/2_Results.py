from __future__ import annotations

import json
from pathlib import Path
from typing import List

import pandas as pd
import streamlit as st

from core.audit import AuditTrailReader, AuditTrailWriter
from core.engine import Engine
from core import storage
from ui.bootstrap import init_app
from ui.nav import render_sidebar
from ui.style import apply_style


SEVERITY_LABELS = {
    "info": "BİLGİ",
    "low": "DÜŞÜK",
    "medium": "ORTA",
    "high": "YÜKSEK",
}
STATUS_LABELS = {
    "done": "Tamamlandı",
    "needs_approval": "Onay Bekliyor",
    "applied": "Uygulandı",
    "skipped": "Atlandı",
    "failed": "Başarısız",
}

st.set_page_config(page_title="ClarityAI", page_icon="✅", layout="wide")
init_app()
apply_style()
render_sidebar("Sonuçlar")

st.title("Sonuçlar")

run_id = st.session_state.get("run_id")

if not run_id:
    st.info("Henüz bir çalıştırma seçilmedi.")
    st.stop()

reader = AuditTrailReader()
audit = reader.load_run(run_id)
run_dir = storage.ensure_run_dir(run_id)
summary_path = run_dir / "artifacts" / "summary.json"
summary_payload: dict = {}

st.write(f"Çalıştırma ID: {run_id}")
if audit.final_summary:
    st.write(audit.final_summary)

reference_enabled = any(
    record.name in {"vendors", "allowed_vat_rates"} for record in audit.input_files
)
reference_label = "Referans Dosyası" if reference_enabled else "Kapalı"
st.caption(f"Doğrulama Kaynağı: {reference_label}")

severity_counts = {"high": 0, "medium": 0, "low": 0, "info": 0}
if summary_path.exists():
    try:
        with summary_path.open("r", encoding="utf-8") as handle:
            summary_payload = json.load(handle)
        counts = summary_payload.get("counts_by_severity", {})
        for key, value in counts.items():
            if key in severity_counts:
                severity_counts[key] = int(value)
    except (json.JSONDecodeError, ValueError):
        pass
else:
    for step in audit.steps:
        if step.severity in severity_counts:
            severity_counts[step.severity] += 1

metric_cols = st.columns(3)
metric_cols[0].metric("Yüksek", severity_counts["high"])
metric_cols[1].metric("Orta", severity_counts["medium"])
metric_cols[2].metric("Düşük", severity_counts["low"])

st.markdown("<div class='section-title'>Önem Dağılımı</div>", unsafe_allow_html=True)
chart_data = pd.DataFrame(
    {
        "Sayım": [
            severity_counts["high"],
            severity_counts["medium"],
            severity_counts["low"],
            severity_counts["info"],
        ]
    },
    index=["YÜKSEK", "ORTA", "DÜŞÜK", "BİLGİ"],
)
st.bar_chart(chart_data, height=200)

st.subheader("İşlem Günlüğü")

severity_options = ["info", "low", "medium", "high"]
selected = st.multiselect(
    "Önem filtresi",
    severity_options,
    default=severity_options,
    format_func=lambda value: SEVERITY_LABELS[value],
)

rows = []
for step in audit.steps:
    if step.severity not in selected:
        continue
    rows.append(
        {
            "Başlık": step.title,
            "İşlem": step.action,
            "Önem": SEVERITY_LABELS.get(step.severity, step.severity),
            "Karar": step.decision,
            "Durum": STATUS_LABELS.get(step.status, step.status),
        }
    )

if rows:
    st.dataframe(pd.DataFrame(rows), use_container_width=True)
else:
    st.info("Seçilen önem filtresine uygun adım yok.")

needs_approval = any(
    step.requires_approval and step.status == "needs_approval" for step in audit.steps
)

st.subheader("Çıktılar")

st.markdown("<div class='card-host'></div>", unsafe_allow_html=True)
with st.container():
    if audit.artifacts:
        for artifact in audit.artifacts:
            path = Path(artifact.path)
            label = f"İndir: {path.name}"
            if not path.exists():
                st.warning(f"Eksik çıktı: {path}")
                continue
            with path.open("rb") as handle:
                st.download_button(
                    label=label,
                    data=handle.read(),
                    file_name=path.name,
                    mime="application/octet-stream",
                    key=f"download-{run_id}-{path.name}",
                )
    else:
        st.info("Henüz çıktı yok.")

st.subheader("En kritik 5 bulgu")
st.markdown("<div class='card-host'></div>", unsafe_allow_html=True)
with st.container():
    top_issues = summary_payload.get("top_issues", [])
    if top_issues:
        for issue in top_issues:
            issue_id = issue.get("issue_id", "-")
            details = issue.get("details", "")
            st.markdown(f"- {issue_id}: {details}")
    else:
        st.info("Kritik bulgu bulunamadı.")

if needs_approval:
    st.warning("Onay bekleyen düzeltme var. İstersen \"Onayla ve Uygula\".")
    if st.button("Onayla ve Uygula", type="primary"):
        engine = Engine()
        plugin = engine.registry.get(audit.demo_type)
        if plugin is None:
            st.error("Bu demo tipi için eklenti bulunamadı.")
            st.stop()

        inputs = {record.name: Path(record.path) for record in audit.input_files}
        rec_path = storage.ensure_run_dir(run_id) / "recommendations.json"
        recommendations: List[dict] = []
        if rec_path.exists():
            with rec_path.open("r", encoding="utf-8") as handle:
                recommendations = json.load(handle)

        new_artifacts = plugin.apply(inputs, recommendations, run_id)
        writer = AuditTrailWriter()
        writer.mark_applied(run_id)
        refreshed = reader.load_run(run_id)
        combined = refreshed.artifacts + new_artifacts
        summary = refreshed.final_summary or "Düzeltmeler uygulandı."
        writer.finalize_run(run_id, summary, combined)
        st.success("Düzeltmeler uygulandı.")
        st.rerun()

if "show_audit" not in st.session_state:
    st.session_state["show_audit"] = False

if st.button("Kanıt Defteri"):
    st.session_state["show_audit"] = not st.session_state["show_audit"]

if st.session_state["show_audit"]:
    st.subheader("Kanıt Defteri")
    for step in audit.steps:
        header = (
            f"{step.title} • {SEVERITY_LABELS.get(step.severity, step.severity)} • "
            f"{STATUS_LABELS.get(step.status, step.status)}"
        )
        with st.expander(header):
            st.write(f"İşlem: {step.action}")
            st.write(f"Karar: {step.decision}")
            st.write(f"Onay gerekir: {'Evet' if step.requires_approval else 'Hayır'}")
            if step.evidence:
                st.markdown("**Kanıtlar**")
                for item in step.evidence:
                    st.write(f"- {item}")
