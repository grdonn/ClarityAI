import os

import streamlit as st

from core.settings import Settings, load_settings, save_settings
from ui.bootstrap import init_app
from ui.nav import render_sidebar
from ui.style import apply_style

st.set_page_config(page_title="ClarityAI", page_icon="✅", layout="wide")
init_app()
apply_style()
render_sidebar("Ayarlar")

st.title("Ayarlar")

api_key_present = bool(os.getenv("OPENAI_API_KEY"))
st.write("OpenAI API Anahtarı: " + ("Var" if api_key_present else "Yok"))
st.write("Harici doğrulama: KAPALI")

settings = load_settings()

st.subheader("Büyük dosya modu")
row_limit = st.number_input(
    "Satır limiti (0 = sınırsız)",
    min_value=0,
    value=settings.max_rows or 0,
    step=1000,
)
chunk_enabled = st.checkbox(
    "Chunk okuma",
    value=settings.chunk_size is not None,
)
chunk_size = settings.chunk_size or 5000
if chunk_enabled:
    chunk_size = st.number_input(
        "Chunk boyutu",
        min_value=500,
        value=chunk_size,
        step=500,
    )

st.subheader("Temizlik")
ttl_days = st.number_input(
    "Otomatik temizlik (TTL gün, 0 = kapalı)",
    min_value=0,
    value=settings.ttl_days or 0,
    step=1,
)

st.subheader("OpenAI")
use_openai = st.checkbox("OpenAI kullan", value=settings.use_openai)
if use_openai:
    st.warning("Hassas veri yüklemeyin.")
    if not api_key_present:
        st.warning("API anahtarı bulunamadı. Offline mod kullanılacak.")

if st.button("Ayarları Kaydet", type="primary"):
    new_settings = Settings(
        max_rows=row_limit if row_limit > 0 else None,
        chunk_size=chunk_size if chunk_enabled else None,
        ttl_days=ttl_days if ttl_days > 0 else None,
        use_openai=use_openai,
    )
    save_settings(new_settings)
    st.success("Ayarlar kaydedildi.")
