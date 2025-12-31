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

from ui.bootstrap import init_app
from ui.nav import render_sidebar
from ui.style import apply_style

st.set_page_config(page_title="ClarityAI", page_icon="✅", layout="wide")
init_app()
apply_style()
render_sidebar("Ana Sayfa")

st.title("Ana Sayfa")
st.markdown(
    "Denetim odaklı dosya inceleme ve onay akışı. Demosunu seçip denetimleri başlatın."
)

st.markdown(
    "<div class='section-title'>1 dakikada dene</div>", unsafe_allow_html=True
)
st.markdown(
    "Demo seç → Örnek veri → Kontrolleri çalıştır → Rapor indir"
)

col1, col2 = st.columns(2)

with col1:
    st.markdown("<div class='card-host'></div>", unsafe_allow_html=True)
    with st.container():
        st.markdown("### 🎫 Demo 1: Talep / İade / İstek İncelemesi")
        st.markdown(
            "Müşteri taleplerini analiz eder, eksik bilgileri tespit eder ve yanıt taslağı oluşturur."
        )
        if st.button("Talep/İade Demosunu Başlat", use_container_width=True):
            st.session_state["demo_type"] = "ticket"
            st.switch_page("pages/1_Run.py")

with col2:
    st.markdown("<div class='card-host'></div>", unsafe_allow_html=True)
    with st.container():
        st.markdown("### 🧾 Demo 2: e-Belge Denetimi")
        st.markdown(
            "e-Fatura ve benzeri belgelerde hesap ve uyum kontrollerini yapar."
        )
        if st.button("e-Belge Demosunu Başlat", use_container_width=True):
            st.session_state["demo_type"] = "edoc"
            st.switch_page("pages/1_Run.py")

st.markdown("<div class='section-title'>Neden Kanıt Defteri?</div>", unsafe_allow_html=True)
st.markdown(
    "- Her adımda kanıt ve gerekçeyi kaydeder.\n"
    "- Onay gerektiren düzeltmeleri kontrol altında tutar.\n"
    "- Denetim izlerini raporlar ve paylaşılır hale getirir."
)
