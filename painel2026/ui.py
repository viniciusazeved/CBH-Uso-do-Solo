"""Peças de página: gráfico com fonte, legenda de cores, tabela no padrão brasileiro, seletor de município e o
mapa do uso do solo."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from . import dados, graficos
from .estilo import CONFIG, GRUPOS, MUDANCA_FLORESTA, OUTROS

CAMADAS = {"1985": "uso_1985", "2000": "uso_2000", "2015": "uso_2015", "2025": "uso_2025",
           "Floresta, 1985 a 2025": "floresta_mudanca_1985_2025"}
CLASSES = {rot: cor for rot, cor in GRUPOS.values()} | {OUTROS[0]: OUTROS[1]}


def grafico(fig, fonte: str | None = None, chave: str | None = None) -> None:
    st.plotly_chart(fig, width="stretch", theme=None, config=CONFIG, key=chave)
    if fonte:
        st.caption(fonte)


def legenda(itens: dict[str, str]) -> None:
    """Legenda em linha: quadrado colorido + nome em tinta de texto (a cor nunca vai no texto)."""
    partes = [f'<span style="white-space:nowrap;margin-right:14px"><span style="display:inline-block;width:12px;'
              f'height:12px;background:{cor};border-radius:2px;margin-right:5px;vertical-align:-1px"></span>{nome}</span>'
              for nome, cor in itens.items()]
    st.markdown(f'<div style="font-size:0.92rem;line-height:1.9">{"".join(partes)}</div>', unsafe_allow_html=True)


def legenda_classes() -> None:
    legenda(CLASSES)


def tabela(df: pd.DataFrame, casas: dict[str, int], altura: int | None = None, **kwargs) -> None:
    """Tabela com números no padrão brasileiro (vírgula decimal, ponto no milhar), qualquer que seja o idioma do
    navegador; a ordenação continua numérica."""
    estilo = df.style
    for col, n in casas.items():
        estilo = estilo.format(precision=n, decimal=",", thousands=".", subset=[col], na_rep="")
    if altura:
        kwargs["height"] = altura
    st.dataframe(estilo, hide_index=True, width="stretch", **kwargs)


def escolher_municipio(chave: str = "municipio", rotulo: str = "Município") -> tuple[int, str]:
    """Seletor que guarda a escolha entre as páginas."""
    mun = dados.municipios()
    nomes = mun["municipio"].tolist()
    atual = st.session_state.get(chave, "Barra Mansa")
    escolha = st.selectbox(rotulo, nomes, index=nomes.index(atual) if atual in nomes else 0, key=f"_sel_{chave}")
    st.session_state[chave] = escolha
    return int(mun.loc[mun["municipio"] == escolha, "cod_ibge"].iloc[0]), escolha


def _manter_camada(chave: str) -> None:
    """Clicar na camada já marcada desmarca o controle; volta para a última escolhida."""
    if st.session_state.get(chave) is None:
        st.session_state[chave] = st.session_state.get(f"{chave}_ultima", "2025")
    st.session_state[f"{chave}_ultima"] = st.session_state[chave]


@st.fragment
def mapa_uso(chave: str, selecionado: int | None = None, padrao: str = "2025", altura: int = 560) -> None:
    """Mapa do uso do solo com seletor de ano; num fragmento, trocar a camada não refaz a página inteira."""
    k = f"_camada_{chave}"
    camada = st.segmented_control("Mapa", list(CAMADAS), default=padrao, key=k, label_visibility="collapsed",
                                  on_change=_manter_camada, args=(k,)) or padrao
    largura = 340 if dados.celular() else 950
    fig = graficos.mapa_imagem(dados.imagem_mapa(CAMADAS[camada]), dados.caixa(), dados.geojson("municipios"),
                               dados.geojson("rh3"), selecionado=selecionado, altura=altura, largura=largura)
    if selecionado is not None:
        feat = next(f for f in dados.geojson("municipios")["features"] if f["properties"]["cod_ibge"] == selecionado)
        fig.update_layout(map=_enquadrar(feat, altura, largura))
    st.plotly_chart(fig, width="stretch", theme=None, config=CONFIG | {"scrollZoom": True}, key=f"mapa_{chave}")
    legenda(MUDANCA_FLORESTA if camada.startswith("Floresta") else CLASSES)
    st.caption("Fonte: MapBiomas Coleção 11; limites municipais do IBGE e da RH-III do INEA. Só a porção dos 19 "
               "municípios na RH-III aparece colorida. Role a roda do mouse (ou use dois dedos) para aproximar; "
               "passe o mouse para ver o município.")


def _enquadrar(feature: dict, altura_px: int, largura_px: int) -> dict:
    xs, ys = [], []

    def coletar(c):
        if isinstance(c[0], (int, float)):
            xs.append(c[0])
            ys.append(c[1])
        else:
            for x in c:
                coletar(x)

    coletar(feature["geometry"]["coordinates"])
    centro, zoom = graficos.zoom_caixa(min(xs), max(ys), max(xs), min(ys), largura_px=largura_px,
                                       altura_px=altura_px - 40)
    return {"center": centro, "zoom": zoom - 0.2}


def nota(texto: str) -> None:
    st.markdown(f'<div style="font-size:0.92rem;color:#52514e;border-left:3px solid #c3c2b7;padding:2px 0 2px 12px;'
                f'margin:4px 0 12px 0">{texto}</div>', unsafe_allow_html=True)
