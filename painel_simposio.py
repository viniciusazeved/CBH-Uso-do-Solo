"""Painel do XI Simpósio Água Boa (30/10/2026): uso e cobertura do solo na RH-III, 1985 a 2025, e Ranking
Ambiental CBH-MPS 2026. Produto do GT SIGA do CBH-MPS.

Dados em painel_dados/ (pipeline/24_dados_painel.py). A página do ranking só mostra resultado quando
painel_dados/ranking/ existe.

Rodar: PYTHONUTF8=1 .venv/Scripts/python -m streamlit run painel_simposio.py
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

st.set_page_config(page_title="Uso do solo na RH-III, 1985 a 2025 | CBH-MPS", page_icon="🌳", layout="wide",
                   initial_sidebar_state="auto")

from painel2026.paginas import (cidade_fogo, comparar, floresta, metodologia, municipio, panorama,  # noqa: E402
                                ranking, rios)

LOGO = Path(__file__).parent / "logo" / "LOGO - CBH MPS_colorida.png"

paginas = {
    "Panorama da RH-III": [
        st.Page(panorama.pagina, title="O que mudou em 40 anos", icon=":material/landscape:", url_path="panorama", default=True),
        st.Page(floresta.pagina, title="Floresta", icon=":material/forest:", url_path="floresta"),
        st.Page(rios.pagina, title="Rios e nascentes", icon=":material/water:", url_path="rios"),
        st.Page(cidade_fogo.pagina, title="Cidade e fogo", icon=":material/local_fire_department:", url_path="cidade-e-fogo"),
    ],
    "Municípios": [
        st.Page(municipio.pagina, title="Perfil do município", icon=":material/location_city:", url_path="municipio"),
        st.Page(comparar.pagina, title="Comparar municípios", icon=":material/compare_arrows:", url_path="comparar"),
    ],
    "Ranking Ambiental 2026": [
        st.Page(ranking.pagina, title="Resultado e método", icon=":material/emoji_events:", url_path="ranking"),
    ],
    "Sobre": [
        st.Page(metodologia.pagina, title="Metodologia e dados", icon=":material/menu_book:", url_path="metodologia"),
    ],
}

navegacao = st.navigation(paginas)
with st.sidebar:
    st.image(str(LOGO), width=180)
    st.caption("Produto do GT SIGA do Comitê de Bacias Hidrográficas do Médio Paraíba do Sul (CBH-MPS). "
               "XI Simpósio Água Boa, 30 de outubro de 2026.")
navegacao.run()
