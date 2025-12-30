import streamlit as st


def apply_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1100px;
            padding-top: 2.5rem;
            padding-bottom: 3rem;
        }
        body {
            background: radial-gradient(circle at 20% 20%, #f8fafc, #f1f5f9 60%);
        }
        div.card-host + div[data-testid="stContainer"] {
            background: #ffffff;
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            box-shadow: 0 6px 16px rgba(15, 23, 42, 0.08);
            padding: 20px;
        }
        .card-host {
            display: none;
        }
        .muted {
            color: #64748b;
        }
        .stButton > button {
            border-radius: 10px;
            padding: 0.6rem 1.1rem;
            font-weight: 600;
        }
        .stDataFrame, .stTable {
            border: 1px solid #e5e7eb;
            border-radius: 10px;
            padding: 6px;
            background: #ffffff;
        }
        div[data-testid="stSidebarNav"] {
            display: none;
        }
        .section-title {
            font-weight: 700;
            font-size: 1.1rem;
            margin-top: 1.5rem;
            margin-bottom: 0.6rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
