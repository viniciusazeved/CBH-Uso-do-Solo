"""Entrada do app publicado em cbh-uso-do-solo-ranking.streamlit.app: o painel do XI Simpósio Água Boa
(painel_simposio.py). O app anterior (Score v2, Coleção 9, maio de 2026) está no histórico do git, no commit b761d77.
"""

import runpy
from pathlib import Path

runpy.run_path(str(Path(__file__).with_name("painel_simposio.py")), run_name="__main__")
