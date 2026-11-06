"""SDSC6004 read-only research explorer for the authenticated 96-lane cohort.

Launch from the repository root using docs/research_explorer_96.md. The separate
historical 24-lane study remains in its frozen artifacts; it is never pooled here.
"""
from __future__ import annotations

import streamlit as st

from traffic_recovery.research_explorer96 import render

st.set_page_config(page_title="香港交通拥堵恢复 | Research Explorer", layout="wide",
                   initial_sidebar_state="collapsed")
st.markdown("""<style>
.stApp {background:#F7F7F4;color:#30363A}
.block-container{max-width:1320px;padding-top:1.4rem;padding-bottom:3rem}
h1,h2,h3{font-family:Arial,Helvetica,sans-serif;letter-spacing:-.025em;color:#30363A}
h1{font-size:2rem!important;font-weight:550!important}
h2{font-size:1.38rem!important;margin-top:1.4rem!important}
.kicker{font:600 .72rem ui-monospace,monospace;letter-spacing:.14em;color:#21867A;text-transform:uppercase}
.rule{border-top:1px solid #D5D9D8;margin:1.4rem 0}
[data-testid="stAlert"]{border-radius:3px}
</style>""", unsafe_allow_html=True)
render()
