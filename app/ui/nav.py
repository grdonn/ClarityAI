import streamlit as st

from core import storage
from core.settings import load_settings


def render_sidebar(active: str) -> None:
    settings = load_settings()
    if settings.ttl_days:
        storage.cleanup_old_runs(settings.ttl_days)
    pages = ["Ana Sayfa", "Yeni Çalıştırma", "Sonuçlar", "Geçmiş", "Ayarlar"]
    page_map = {
        "Ana Sayfa": "Home.py",
        "Yeni Çalıştırma": "pages/1_Run.py",
        "Sonuçlar": "pages/2_Results.py",
        "Geçmiş": "pages/3_History.py",
        "Ayarlar": "pages/4_Settings.py",
    }
    index = pages.index(active) if active in pages else 0
    st.sidebar.title("Menü")
    selection = st.sidebar.radio("Sayfalar", pages, index=index)
    if selection != active:
        st.switch_page(page_map[selection])
