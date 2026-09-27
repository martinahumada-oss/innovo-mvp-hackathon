"""Entrada del MVP INNOVO USACH."""
import streamlit as st
from mvp_ui import main

st.set_page_config(page_title="INNOVO · Gestión e informes", page_icon=":material/description:", layout="wide", initial_sidebar_state="collapsed")

if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, KeyError) as error:
        st.error(f"No se completó la operación: {error}")
