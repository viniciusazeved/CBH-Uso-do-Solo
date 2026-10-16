"""Paleta, formatação e estilo dos gráficos: os mesmos do pipeline (12_graficos.py e 14_mapas.py) e dos
slides do simpósio, para painel e apresentação mostrarem as mesmas cores.

A paleta por grupo passou no validador de daltonismo na ordem da pilha (floresta, herbácea, água,
pastagem, mosaico, urbano); herbácea e pastagem ficam abaixo de 3:1 de contraste com o fundo, por isso os
gráficos levam rótulo direto ou tabela ao lado.
"""

from __future__ import annotations

import plotly.graph_objects as go

FUNDO = "#fcfcfb"
TINTA = "#0b0b0b"
TINTA_2 = "#52514e"
TINTA_FRACA = "#898781"
GRADE = "#e1e0d9"
EIXO = "#c3c2b7"
FONTE = '"Source Sans Pro", "Source Sans 3", "Segoe UI", Arial, sans-serif'

GRUPOS = {
    "Formação florestal": ("Floresta", "#1f8d49"),
    "Vegetação herbácea e arbustiva": ("Vegetação herbácea e arbustiva", "#7cc36b"),
    "Água": ("Água", "#1e63c8"),
    "Pastagem": ("Pastagem", "#c9a227"),
    "Mosaico de usos": ("Mosaico de usos", "#8e6bbf"),
    "Área urbanizada": ("Área urbanizada", "#d84315"),
}
OUTROS = ("Outros usos", "#9e9e9e")   # silvicultura, agricultura, mineração e áreas não vegetadas (0,5% da bacia)
COR = {rot: cor for rot, cor in GRUPOS.values()} | {OUTROS[0]: OUTROS[1]}
BOM, CRITICO = "#0ca30c", "#d03b3b"           # recuperação e supressão, sempre com rótulo
AUMENTO, REDUCAO = "#2a78d6", "#e34948"
VERDE_RAMPA = ["#bfe3c9", "#93cfa5", "#5fb37c", "#2f9558", "#1f8d49", "#145c30"]
DESTAQUE, NEUTRO = "#1f8d49", "#b4b2a9"
MUDANCA_FLORESTA = {"Floresta nos dois anos": "#93cfa5", "Floresta que voltou": "#1f6fb4",
                    "Floresta que saiu": "#d03b3b", "Sem floresta nos dois anos": "#eeede8"}

FONTE_C11 = "Fonte: MapBiomas Coleção 11 (1985 a 2025), porção dos 19 municípios na RH-III. Elaboração: GT SIGA, CBH-MPS."
FONTE_DSV = ("Fonte: MapBiomas Coleção 11, desmatamento e vegetação secundária (v5), 1988 a 2024; 2025 fica fora "
             "(ano incompleto). Elaboração: GT SIGA, CBH-MPS.")
FONTE_FOGO = "Fonte: MapBiomas Fogo, Coleção 4 (1985 a 2024). Elaboração: GT SIGA, CBH-MPS."
CONFIG = {"displaylogo": False, "modeBarButtonsToRemove": ["lasso2d", "select2d", "autoScale2d"],
          "toImageButtonOptions": {"format": "png", "scale": 2}}


def fmt(v: float, casas: int = 0, sinal: bool = False) -> str:
    """Número no padrão brasileiro (ponto no milhar, vírgula no decimal)."""
    s = f"{v:+,.{casas}f}" if sinal else f"{v:,.{casas}f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def pct(v: float, casas: int = 1, sinal: bool = False) -> str:
    return fmt(v, casas, sinal) + "%"


def nome(grupo: str) -> str:
    return GRUPOS.get(grupo, OUTROS)[0]


def base(fig: go.Figure, altura: int = 420, margem: dict | None = None) -> go.Figure:
    """Layout comum: fundo e tinta do painel, vírgula decimal, legenda embaixo, sem título dentro da figura
    (o título fica no texto da página)."""
    fig.update_layout(
        height=altura, paper_bgcolor=FUNDO, plot_bgcolor=FUNDO, separators=",.",
        font={"family": FONTE, "size": 15, "color": TINTA_2},
        margin={"l": 10, "r": 20, "t": 30, "b": 10} | (margem or {}),
        legend={"orientation": "h", "yanchor": "top", "y": -0.12, "x": 0, "font": {"size": 14}},
        hoverlabel={"font": {"family": FONTE, "size": 14}},
    )
    fig.update_xaxes(showgrid=False, linecolor=EIXO, ticks="outside", tickcolor=EIXO, zeroline=False, automargin=True)
    fig.update_yaxes(gridcolor=GRADE, gridwidth=1, linecolor=EIXO, zeroline=False, automargin=True)
    return fig
