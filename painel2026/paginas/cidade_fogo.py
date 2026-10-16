"""Cidade e fogo: expansão urbana e área queimada."""

from __future__ import annotations

import streamlit as st

from .. import dados, graficos, ui
from ..estilo import FONTE_C11, FONTE_FOGO, fmt, pct


def pagina() -> None:
    r = dados.resumo()
    comp = dados.tabela("composicao_anual.csv")
    c = comp[(comp["cod_ibge"] == dados.RH3) & (comp["grupo"] == "Área urbanizada")].set_index("ano")["area_ha"]
    orig = r["urbano_origem_ha"]
    mun = dados.tabela("municipios_resumo.csv")
    mun = mun[mun["cod_ibge"] != dados.RH3]
    rip_uso = dados.tabela("ripario_uso.csv")
    urb_rip = rip_uso[(rip_uso["cod_ibge"] == dados.RH3) & (rip_uso["ano"] == 2025)
                      & (rip_uso["grupo"] == "Área urbanizada")]["area_ha"].sum()

    st.title("Cidade e fogo")
    st.subheader("A cidade dobrou")
    st.markdown(f"A área urbanizada foi de {fmt(c.loc[1985] / 1000, 1)} mil para {fmt(c.loc[2025] / 1000, 1)} mil ha de "
                f"1985 a 2025, sobre pasto ({fmt(orig['Pastagem'] / 1000, 1)} mil ha) e mosaico de usos "
                f"({fmt(orig['Mosaico de usos'] / 1000, 1)} mil ha); só {fmt(orig['Formação florestal'])} ha vieram de "
                f"floresta. Dentro da faixa ripária há cerca de {fmt(urb_rip / 1000, 1)} mil ha urbanizados em 2025.")
    ui.grafico(graficos.halteres(mun.assign(u85=mun["urbano_1985_ha"] / 1000, u25=mun["urbano_2025_ha"] / 1000), "u85", "u25",
                                 "", 1, "#f4a582", "#d84315", "1985", "2025"),
               "Área urbanizada por município, em mil ha, na porção do município na RH-III. " + FONTE_C11)

    st.subheader("Fogo: sobretudo no pasto")
    fg = r["fogo"]
    queimou = 100 - fg["frequencia_pct_area"]["nunca"]
    fogo = dados.tabela("fogo_anual.csv")
    f0 = fogo[(fogo["cod_ibge"] == dados.RH3) & (fogo["grupo_queimado"] == "Formação florestal")].set_index("ano")["area_ha"]
    st.markdown(f"A bacia queimou em média {fmt(fg['media_1985_2024_ha_ano'] / 1000, 1)} mil ha por ano de 1985 a 2024; "
                f"de 2015 a 2024, {pct(fg['por_grupo_2015_2024_pct']['Pastagem'], 0)} da área queimada era pasto. "
                f"{pct(queimou, 0)} da bacia queimou ao menos uma vez no período. Em {int(f0.idxmax())}, a floresta "
                f"queimada chegou a {fmt(f0.max())} ha, a maior área da série: é um alerta, ainda não uma tendência.")
    ui.grafico(graficos.fogo(fogo), FONTE_FOGO)
