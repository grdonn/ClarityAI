from __future__ import annotations

from pathlib import Path
import sys

_app_dir = Path(__file__).resolve()
while _app_dir.name != "app" and _app_dir.parent != _app_dir:
    _app_dir = _app_dir.parent
if str(_app_dir) not in sys.path:
    sys.path.insert(0, str(_app_dir))

from boot import ensure_project_root_on_path

ensure_project_root_on_path()

import streamlit as st

from core import storage
from core.audit import AuditTrailReader
from ui.bootstrap import init_app
from ui.nav import render_sidebar
from ui.style import apply_style


st.set_page_config(page_title="ClarityAI", page_icon="✅", layout="wide")
init_app()
apply_style()
render_sidebar("Geçmiş")

st.title("Geçmiş")

runs = storage.list_runs()

if not runs:
    st.info("Henüz kayıtlı çalıştırma yok.")
    st.stop()

demo_labels = {"ticket": "Talep/İade", "edoc": "e-Belge"}

def _format_run(entry: dict) -> str:
    demo_label = demo_labels.get(entry.get("demo_type"), entry.get("demo_type"))
    return f"{entry.get('run_id')} | {demo_label} | {entry.get('started_at')}"


selected = st.selectbox(
    "Çalıştırma seç",
    options=runs,
    format_func=_format_run,
)

run_id = selected.get("run_id")

if run_id:
    audit = AuditTrailReader().load_run(run_id)
    st.subheader("Kanıt Defteri")
    st.json(audit.model_dump(mode="json"))

    st.subheader("Çıktılar")
    if audit.artifacts:
        for artifact in audit.artifacts:
            path = Path(artifact.path)
            if not path.exists():
                st.warning(f"Eksik çıktı: {path}")
                continue
            with path.open("rb") as handle:
                st.download_button(
                    label=f"İndir: {path.name}",
                    data=handle.read(),
                    file_name=path.name,
                    mime="application/octet-stream",
                    key=f"history-{run_id}-{path.name}",
                )
    else:
        st.info("Bu çalıştırma için çıktı yok.")

    if st.button("Sonuçlarda Aç"):
        st.session_state["run_id"] = run_id
        st.switch_page("pages/2_Results.py")

    st.subheader("Temizlik")
    if st.button("Seçili çalıştırmayı sil"):
        st.session_state["confirm_delete_selected"] = True

    if st.session_state.get("confirm_delete_selected"):
        confirm = st.checkbox("Eminim", key="confirm-delete-selected")
        if confirm and st.button("Sil", key="delete-selected"):
            storage.delete_run(run_id)
            st.success("Çalıştırma silindi.")
            st.session_state.pop("confirm_delete_selected", None)
            st.rerun()

    if st.button("Tüm çalıştırmaları temizle"):
        st.session_state["confirm_delete_all"] = True

    if st.session_state.get("confirm_delete_all"):
        confirm_all = st.checkbox("Eminim", key="confirm-delete-all")
        if confirm_all and st.button("Tümünü Sil", key="delete-all"):
            storage.clear_runs()
            st.success("Tüm çalıştırmalar temizlendi.")
            st.session_state.pop("confirm_delete_all", None)
            st.rerun()
