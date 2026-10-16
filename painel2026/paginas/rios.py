"""Rios e nascentes: vegetação na faixa ripária e onde a restauração mais ajuda a água."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from .. import dados, graficos, ui
from ..estilo import COR, FONTE_C11, GRADE, TINTA, base, fmt, nome, pct

NOTA_FAIXA = ("A faixa ripária foi traçada com a hidrografia 1:25.000 do IBGE (BC25): 30 m de cada lado dos rios e raio "
              "de 50 m nas nascentes, fora da superfície dos rios largos e lagos. É uma aproximação da APP hídrica "
              "mínima do Código Florestal, não a delimitação legal da APP de cada imóvel. Vegetação nativa, aqui, é "
              "floresta e área úmida; o campo fica de fora porque o mapa o confunde com pasto (o mesmo critério do "
              "Ranking Ambiental).")


def uso_faixa(uso, cod: int, altura: int = 300) -> go.Figure:
    u = uso[(uso["cod_ibge"] == cod) & (uso["ano"] == 2025)].copy()
    u["g"] = u["grupo"].map(nome)
    u = u.groupby("g")["pct_zona"].sum().sort_values()
    fig = go.Figure(go.Bar(x=u.values, y=u.index, orientation="h", marker={"color": [COR[g] for g in u.index]},
                           text=[pct(v) for v in u.values], textposition="outside", cliponaxis=False,
                           textfont={"size": 14, "color": TINTA}, hovertemplate="%{y}: %{x:.1f}% da faixa<extra></extra>"))
    fig.update_xaxes(ticksuffix="%", range=[0, max(u.max() * 1.2, 10)], showgrid=True, gridcolor=GRADE)
    fig.update_layout(showlegend=False, bargap=0.35)
    return base(fig, altura)


def pagina() -> None:
    rip = dados.tabela("ripario_anual.csv")
    rr = rip[rip["cod_ibge"] == dados.RH3].set_index("ano")
    uso = dados.tabela("ripario_uso.csv")
    u25 = uso[(uso["cod_ibge"] == dados.RH3) & (uso["ano"] == 2025)]
    pasto = u25[u25["grupo"] == "Pastagem"].iloc[0]
    prio = dados.resumo()["restauracao_indicativa_ha"]

    st.title("Rios e nascentes")
    st.markdown("A beira do rio é onde a vegetação mais protege a água: segura o solo, filtra o escoamento e sombreia "
                "o leito. É também onde a bacia está mais aberta.")

    st.subheader("A beira dos rios ganhou mata, mas continua quase dois terços aberta")
    st.markdown(f"A vegetação nativa na faixa de 30 m dos rios e no entorno de 50 m das nascentes passou de "
                f"{pct(rr.loc[1985, 'nativa_zona_pct'])} em 1985 para {pct(rr.loc[2025, 'nativa_zona_pct'])} em 2025. "
                f"A pastagem ainda ocupa {pct(pasto['pct_zona'])} da faixa, {fmt(pasto['area_ha'] / 1000, 1)} mil ha.")
    ui.grafico(graficos.ripario(rip), FONTE_C11)
    st.markdown("**O que ocupa a faixa ripária em 2025**")
    ui.grafico(uso_faixa(uso, dados.RH3), None)
    ui.nota(NOTA_FAIXA)

    st.subheader("Onde a restauração mais ajuda a água")
    st.markdown(f"Pasto na faixa ripária ou em encosta de 25° ou mais soma {fmt(prio['pasto_prioritario_ha'] / 1000)} mil ha "
                f"na bacia. Desses, {fmt(prio['pasto_prioritario_ate_100m_de_fragmento_100ha_ha'] / 1000)} mil ha ficam a até "
                "100 m de um fragmento de mata de 100 ha ou mais, onde a regeneração tende a ser mais rápida e barata.")
    ui.grafico(graficos.restauracao(dados.tabela("restauracao_indicativa.csv")), "Pasto em 2025 na faixa ripária ou em "
               "encosta de 25° ou mais, por município, em mil ha. " + FONTE_C11)
    ui.nota("Indicativo: não é mapa oficial de áreas prioritárias e não substitui o diagnóstico de cada imóvel.")
