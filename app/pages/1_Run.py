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

import json
import shutil
from uuid import uuid4

import pandas as pd
import streamlit as st

from core import schema
from core.engine import Engine
from core import storage
from core.schema import SchemaValidationError
from ui.bootstrap import init_app
from ui.nav import render_sidebar
from ui.style import apply_style


st.set_page_config(page_title="ClarityAI", page_icon="✅", layout="wide")
init_app()
apply_style()
render_sidebar("Yeni Çalıştırma")

st.title("Yeni Çalıştırma")

options = ["ticket", "edoc"]
labels = {"ticket": "Talep/İade Demo", "edoc": "e-Belge Demo"}

current = st.session_state.get("demo_type", "ticket")
index = options.index(current) if current in options else 0

demo_type = st.radio(
    "Demo seçimi",
    options,
    format_func=lambda value: labels[value],
    index=index,
    horizontal=True,
)

st.session_state["demo_type"] = demo_type


def _columns_from_uploaded(uploaded, sample_path: Path, use_sample: bool) -> list[str]:
    if uploaded is not None:
        try:
            uploaded.seek(0)
            cols = list(pd.read_csv(uploaded, nrows=1).columns)
            uploaded.seek(0)
            return cols
        except Exception:
            return []
    if use_sample and sample_path.exists():
        return list(pd.read_csv(sample_path, nrows=1).columns)
    return []


def _render_mapping_section(
    title: str,
    input_key: str,
    expected: list[str],
    required: set[str],
    columns: list[str],
) -> None:
    if not columns:
        return
    st.markdown(f"#### {title}")
    synonyms = schema.get_synonyms("ticket" if input_key == "tickets" else "edoc", input_key)
    if st.button("Otomatik eşleştir", key=f"auto-map-{input_key}"):
        mapping, scores = schema.auto_map_columns_scored(
            expected, columns, synonyms
        )
        st.session_state[f"mapping_{input_key}"] = mapping
        st.session_state[f"mapping_scores_{input_key}"] = scores
        matched_count = sum(1 for value in mapping.values() if value)
        st.success(f"{matched_count} alan eşleştirildi.")
        missing_required = [col for col in required if not mapping.get(col)]
        if missing_required:
            st.warning(
                "Şu zorunlu alanlar otomatik bulunamadı: "
                + ", ".join(missing_required)
                + ". Lütfen elle seçin."
            )
    mapping = st.session_state.get(f"mapping_{input_key}", {})
    scores = st.session_state.get(f"mapping_scores_{input_key}", {})
    updated_mapping = {}
    for col in expected:
        label = f"{col} (zorunlu)" if col in required else col
        options = ["(eşleştirme yok)"] + columns
        current = mapping.get(col)
        index = options.index(current) if current in columns else 0
        selection = st.selectbox(
            f"{label} eşleştir",
            options,
            index=index,
            key=f"map-{input_key}-{col}",
        )
        updated_mapping[col] = None if selection == "(eşleştirme yok)" else selection
    st.session_state[f"mapping_{input_key}"] = updated_mapping

    if scores:
        rows = []
        for col in expected:
            selected = updated_mapping.get(col)
            score = scores.get(col)
            if selected and (score is None or mapping.get(col) != selected):
                score = "manuel"
            rows.append(
                {
                    "Beklenen Alan": col,
                    "Seçilen Kolon": selected or "-",
                    "Skor": score or "-",
                }
            )
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


ticket_schema = schema.get_input_schema("ticket", "tickets")
edoc_invoice_schema = schema.get_input_schema("edoc", "invoices")
edoc_po_schema = schema.get_input_schema("edoc", "purchase_orders")
edoc_dn_schema = schema.get_input_schema("edoc", "delivery_notes")

if demo_type == "ticket":
    st.subheader("Talep/İade CSV")
    st.caption(
        "Bu dosya müşteri taleplerini içerir. Örnek veri kullanarak hemen deneyebilirsin."
    )
    st.caption("Zorunlu alanlar: ticket_id, created_at, channel, customer_text")
    uploaded_tickets = st.file_uploader(
        "Talep kayıt dosyası (tickets.csv)", type=["csv"], key="tickets"
    )

    if "use_sample_ticket" not in st.session_state:
        st.session_state["use_sample_ticket"] = False

    if st.button("Örnek veriyi kullan", key="sample-ticket"):
        st.session_state["use_sample_ticket"] = True

    if uploaded_tickets is not None:
        st.session_state["use_sample_ticket"] = False

    if st.session_state.get("use_sample_ticket"):
        sample_path = Path("plugins/ticket_triage/sample_inputs/tickets.csv")
        if sample_path.exists():
            st.info(f"Örnek dosya kullanılıyor: {sample_path}")
        else:
            st.error("Örnek tickets.csv bulunamadı.")

    ticket_columns = _columns_from_uploaded(
        uploaded_tickets,
        Path("plugins/ticket_triage/sample_inputs/tickets.csv"),
        st.session_state.get("use_sample_ticket", False),
    )

    if ticket_columns:
        st.markdown("<div class='section-title'>Kolon Eşleştirme</div>", unsafe_allow_html=True)
        st.caption(
            "Bu demo çalışması için en az: ticket_id, created_at, channel, customer_text "
            "alanlarını eşleştirmeniz gerekir."
        )
        expected = list(ticket_schema.required.keys()) + list(ticket_schema.optional.keys())
        required = set(ticket_schema.required.keys())
        _render_mapping_section(
            "Talep Kolonları",
            "tickets",
            expected,
            required,
            ticket_columns,
        )

if demo_type == "edoc":
    st.subheader("e-Belge CSV Girdileri")
    uploaded_invoices = st.file_uploader(
        "Fatura kayıtları (invoices.csv)", type=["csv"], key="invoices"
    )
    st.caption("Fatura satırları ve toplam/KDV alanları.")
    uploaded_purchase_orders = st.file_uploader(
        "Satınalma siparişleri (purchase_orders.csv)", type=["csv"], key="purchase_orders"
    )
    st.caption("Sipariş toplamı ve kalem sayısı.")
    uploaded_delivery_notes = st.file_uploader(
        "İrsaliye/teslim kayıtları (delivery_notes.csv)", type=["csv"], key="delivery_notes"
    )
    st.caption("Teslim edilen kalem sayısı.")
    st.caption(
        "Hepsini yükleyebilir veya 'Örnek veriyi kullan' ile otomatik deneyebilirsin."
    )

    st.markdown("<div class='section-title'>Referans Dosyaları (Opsiyonel)</div>", unsafe_allow_html=True)
    uploaded_vendors = st.file_uploader(
        "İzinli tedarikçiler (vendors.csv)", type=["csv"], key="vendors_ref"
    )
    st.caption("Tedarikçi adlarının yer aldığı liste.")
    uploaded_vat_rates = st.file_uploader(
        "İzinli KDV oranları (allowed_vat_rates.json/csv)",
        type=["json", "csv"],
        key="vat_rates_ref",
    )
    st.caption("Örn: [0.18, 0.08] veya tek kolonlu CSV.")

    if "use_sample_edoc" not in st.session_state:
        st.session_state["use_sample_edoc"] = False

    if st.button("Örnek veriyi kullan", key="sample-edoc"):
        st.session_state["use_sample_edoc"] = True

    if any(
        uploader is not None
        for uploader in [
            uploaded_invoices,
            uploaded_purchase_orders,
            uploaded_delivery_notes,
        ]
    ):
        st.session_state["use_sample_edoc"] = False

    if st.session_state.get("use_sample_edoc"):
        sample_dir = Path("plugins/edocument_audit/sample_inputs")
        if sample_dir.exists():
            st.info(f"Örnek veri kullanılıyor: {sample_dir}")
        else:
            st.error("Örnek e-Belge verisi bulunamadı.")

    invoices_cols = _columns_from_uploaded(
        uploaded_invoices,
        Path("plugins/edocument_audit/sample_inputs/invoices.csv"),
        st.session_state.get("use_sample_edoc", False),
    )
    po_cols = _columns_from_uploaded(
        uploaded_purchase_orders,
        Path("plugins/edocument_audit/sample_inputs/purchase_orders.csv"),
        st.session_state.get("use_sample_edoc", False),
    )
    dn_cols = _columns_from_uploaded(
        uploaded_delivery_notes,
        Path("plugins/edocument_audit/sample_inputs/delivery_notes.csv"),
        st.session_state.get("use_sample_edoc", False),
    )

    if invoices_cols or po_cols or dn_cols:
        st.markdown("<div class='section-title'>Kolon Eşleştirme</div>", unsafe_allow_html=True)

    if invoices_cols:
        _render_mapping_section(
            "Fatura Kolonları",
            "invoices",
            list(edoc_invoice_schema.required.keys()),
            set(edoc_invoice_schema.required.keys()),
            invoices_cols,
        )

    if po_cols:
        _render_mapping_section(
            "Satınalma Kolonları",
            "purchase_orders",
            list(edoc_po_schema.required.keys()),
            set(edoc_po_schema.required.keys()),
            po_cols,
        )

    if dn_cols:
        _render_mapping_section(
            "İrsaliye Kolonları",
            "delivery_notes",
            list(edoc_dn_schema.required.keys()),
            set(edoc_dn_schema.required.keys()),
            dn_cols,
        )

if st.button("Kontrolleri Çalıştır", type="primary"):
    run_id = str(uuid4())
    run_dir = storage.ensure_run_dir(run_id)
    inputs_dir = run_dir / "inputs"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    inputs: dict[str, Path] = {}
    mapping_payload: dict[str, dict] = {}

    if demo_type == "ticket":
        use_sample = st.session_state.get("use_sample_ticket", False)
        if uploaded_tickets is None and not use_sample:
            st.error("Lütfen tickets.csv yükleyin veya örnek veri kullanın.")
            st.stop()

        if use_sample:
            src = Path("plugins/ticket_triage/sample_inputs/tickets.csv")
            if not src.exists():
                st.error("Örnek tickets.csv bulunamadı.")
                st.stop()
            dest = inputs_dir / "tickets.csv"
            shutil.copyfile(src, dest)
        else:
            dest = inputs_dir / "tickets.csv"
            dest.write_bytes(uploaded_tickets.getbuffer())

        inputs = {"tickets": dest}
        mapping_payload = {"tickets": st.session_state.get("mapping_tickets", {})}

    if demo_type == "edoc":
        use_sample = st.session_state.get("use_sample_edoc", False)
        if not use_sample:
            missing = []
            if uploaded_invoices is None:
                missing.append("invoices.csv")
            if uploaded_purchase_orders is None:
                missing.append("purchase_orders.csv")
            if uploaded_delivery_notes is None:
                missing.append("delivery_notes.csv")
            if missing:
                st.error("Lütfen şu dosyaları yükleyin: " + ", ".join(missing))
                st.stop()

        if use_sample:
            sample_dir = Path("plugins/edocument_audit/sample_inputs")
            if not sample_dir.exists():
                st.error("Örnek e-Belge verisi bulunamadı.")
                st.stop()
            src_invoices = sample_dir / "invoices.csv"
            src_pos = sample_dir / "purchase_orders.csv"
            src_dns = sample_dir / "delivery_notes.csv"
            if not src_invoices.exists() or not src_pos.exists() or not src_dns.exists():
                st.error("Örnek e-Belge verisi eksik.")
                st.stop()
            dest_invoices = inputs_dir / "invoices.csv"
            dest_pos = inputs_dir / "purchase_orders.csv"
            dest_dns = inputs_dir / "delivery_notes.csv"
            shutil.copyfile(src_invoices, dest_invoices)
            shutil.copyfile(src_pos, dest_pos)
            shutil.copyfile(src_dns, dest_dns)
        else:
            dest_invoices = inputs_dir / "invoices.csv"
            dest_pos = inputs_dir / "purchase_orders.csv"
            dest_dns = inputs_dir / "delivery_notes.csv"
            dest_invoices.write_bytes(uploaded_invoices.getbuffer())
            dest_pos.write_bytes(uploaded_purchase_orders.getbuffer())
            dest_dns.write_bytes(uploaded_delivery_notes.getbuffer())

        inputs = {
            "invoices": dest_invoices,
            "purchase_orders": dest_pos,
            "delivery_notes": dest_dns,
        }
        mapping_payload = {
            "invoices": st.session_state.get("mapping_invoices", {}),
            "purchase_orders": st.session_state.get("mapping_purchase_orders", {}),
            "delivery_notes": st.session_state.get("mapping_delivery_notes", {}),
        }

        if uploaded_vendors is not None:
            dest_vendors = inputs_dir / "vendors.csv"
            dest_vendors.write_bytes(uploaded_vendors.getbuffer())
            inputs["vendors"] = dest_vendors

        if uploaded_vat_rates is not None:
            ext = Path(uploaded_vat_rates.name).suffix or ".json"
            dest_rates = inputs_dir / f"allowed_vat_rates{ext}"
            dest_rates.write_bytes(uploaded_vat_rates.getbuffer())
            inputs["allowed_vat_rates"] = dest_rates

    mapping_path = run_dir / "mapping.json"
    mapping_path.write_text(
        json.dumps(mapping_payload, indent=2, ensure_ascii=True), encoding="utf-8"
    )

    engine = Engine()
    try:
        result = engine.run(demo_type, inputs, run_id=run_id)
    except SchemaValidationError as exc:
        for message in exc.messages:
            st.error(message)
        st.stop()
    except Exception as exc:
        st.error(f"Beklenmeyen hata: {exc}")
        st.stop()

    st.session_state["run_id"] = result.run_id
    st.switch_page("pages/2_Results.py")
