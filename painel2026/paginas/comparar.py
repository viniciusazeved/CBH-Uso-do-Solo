"""Comparar municípios: mapa e barras de um indicador do panorama, e a tabela completa."""

from __future__ import annotations

import plotly.graph_objects as go
import streamlit as st

from .. import dados, graficos, ui
from ..estilo import AUMENTO, FONTE_C11, GRADE, NEUTRO, REDUCAO, TINTA, VERDE_RAMPA, base, fmt

# rótulo: (coluna do municipios_resumo, sufixo, casas, divergente, explicação)
INDICADORES = {
    "Floresta em 2025": ("floresta_2025_pct", "%", 1, False, "% da porção do município na RH-III"),
    "Variação da floresta, 1985 a 2025": ("floresta_var_pp", " p.p.", 1, True, "pontos percentuais da porção na RH-III"),
    "Saldo anual de floresta, 2015 a 2024": ("saldo_floresta_dsv_2015_2024_ha_ano", " ha", 0, True,
                                              "recuperação menos supressão, média em ha por ano (desmatamento e vegetação secundária)"),
    "Floresta jovem (até 20 anos) em 2025": ("floresta_2025_ate_20_anos_pct", "%", 1, False, "% da floresta de 2025"),
    "Vegetação nativa na beira dos rios em 2025": ("ripario_nativa_2025_pct", "%", 1, False,
                                                   "% da faixa de 30 m dos rios e 50 m das nascentes"),
    "Pastagem em 2025": ("pastagem_2025_pct", "%", 1, False, "% da porção do município na RH-III"),
    "Pasto em encosta de 25° ou mais": ("pasto_encosta_25graus_2025_pct_da_encosta", "%", 1, False,
                                        "% das encostas de 25° ou mais ocupadas por pasto em 2025"),
    "Área urbanizada em 2025": ("urbano_2025_pct", "%", 1, False, "% da porção do município na RH-III"),
    "Área que queimou ao menos uma vez, 1985 a 2024": ("queimou_ao_menos_1_vez_1985_2024_pct", "%", 1, False,
                                                       "% da porção do município na RH-III"),
}


def barras(df, coluna: str, sufixo: str, casas: int, divergente: bool, destacar: str | None) -> go.Figure:
    d = df.sort_values(coluna)
    if divergente:
        cores = [AUMENTO if v > 0 else REDUCAO for v in d[coluna]]
    else:
        cores = [VERDE_RAMPA[4]] * len(d)
    cores = [c if m != destacar else TINTA for c, m in zip(cores, d["municipio"])]
    fig = go.Figure(go.Bar(x=d[coluna], y=d["municipio"], orientation="h", marker={"color": cores},
                           text=[fmt(v, casas, sinal=divergente) + sufixo for v in d[coluna]], textposition="outside",
                           cliponaxis=False, textfont={"size": 13, "color": TINTA},
                           hovertemplate="%{y}: %{x:,." + str(casas) + "f}" + sufixo + "<extra></extra>"))
    lo, hi = min(d[coluna].min(), 0), max(d[coluna].max(), 0)
    fig.update_xaxes(range=[lo - 0.18 * (hi - lo) if lo < 0 else 0, hi + 0.18 * (hi - lo)], showgrid=True, gridcolor=GRADE,
                     zeroline=divergente, zerolinecolor=NEUTRO, ticksuffix="%" if sufixo == "%" else "")
    fig.update_yaxes(showgrid=False, tickfont={"size": 13},
                     ticktext=[f"<b>{m}</b>" if m == destacar else m for m in d["municipio"]], tickvals=d["municipio"])
    fig.update_layout(showlegend=False, bargap=0.3)
    return base(fig, 600)


def pagina() -> None:
    st.title("Comparar municípios")
    st.markdown("Todos os valores são da porção de cada município na RH-III. Rio Claro, Miguel Pereira e Mendes têm porção "
                "pequena na bacia (menos de 5.000 ha), e uma única propriedade pesa muito nas taxas deles.")
    res = dados.tabela("municipios_resumo.csv")
    res = res[res["cod_ibge"] != dados.RH3]
    e, d = st.columns([3, 1])
    rotulo = e.selectbox("Indicador", list(INDICADORES))
    destaque = d.selectbox("Destacar", ["nenhum"] + sorted(res["municipio"], key=dados.ordem_alfabetica), index=0)
    destaque = None if destaque == "nenhum" else destaque
    coluna, sufixo, casas, divergente, explica = INDICADORES[rotulo]
    st.caption(f"{rotulo}: {explica}.")
    ui.grafico(graficos.mapa_coropletico(res, coluna, rotulo.split(",")[0], sufixo.strip() if sufixo == "%" else "",
                                         casas, dados.geojson("municipios"), dados.geojson("rh3"), dados.caixa(),
                                         divergente=divergente, altura=520, largura=340 if dados.celular() else 950), None)
    ui.grafico(barras(res, coluna, sufixo, casas, divergente, destaque), FONTE_C11)

    st.subheader("Floresta por município, 1985 e 2025")
    ui.grafico(graficos.halteres(res, "floresta_1985_pct", "floresta_2025_pct", "%", 1, "#93cfa5", "#1f8d49", "1985", "2025",
                                 destacar=destaque), "Percentual da porção do município na RH-III. " + FONTE_C11)

    st.subheader("Tabela completa")
    cols = {"municipio": "Município", "area_na_rh3_ha": "Área na RH-III (ha)"}
    cols |= {v[0]: k for k, v in INDICADORES.items()}
    tab = res[list(cols)].sort_values("municipio", key=lambda s: s.map(dados.ordem_alfabetica)).rename(columns=cols)
    casas_col = {"Área na RH-III (ha)": 0} | {k: v[2] for k, v in INDICADORES.items()}
    ui.tabela(tab, casas_col, altura=35 * (len(tab) + 1) + 3,
              column_config={"Município": st.column_config.TextColumn(pinned=True)})
    st.download_button("Baixar a tabela completa (CSV)", res.to_csv(index=False).encode("utf-8"),
                       file_name="municipios_resumo_rh3.csv", mime="text/csv", icon=":material/download:")
