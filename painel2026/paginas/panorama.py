"""Panorama da RH-III: o que mudou de 1985 a 2025."""

from __future__ import annotations

import streamlit as st

from .. import dados, graficos, ui
from ..estilo import FONTE_C11, fmt, pct


def pagina() -> None:
    comp = dados.tabela("composicao_anual.csv")
    rip = dados.tabela("ripario_anual.csv")
    r = dados.resumo()
    c = comp[comp["cod_ibge"] == dados.RH3].pivot_table(index="ano", columns="grupo", values="area_ha")
    p = comp[comp["cod_ibge"] == dados.RH3].pivot_table(index="ano", columns="grupo", values="pct")
    rr = rip[rip["cod_ibge"] == dados.RH3].set_index("ano")
    flo, pas, urb, mos = "Formação florestal", "Pastagem", "Área urbanizada", "Mosaico de usos"

    st.title("Uso e cobertura do solo na RH-III, 1985 a 2025")
    st.markdown(
        f"O território que abastece: a porção dos 19 municípios do CBH-MPS na Região Hidrográfica III, "
        f"{fmt(r['area_rh3_ha'] / 1000)} mil hectares, em 41 mapas anuais do MapBiomas (Coleção 11). Mata, pasto e "
        "cidade mudam a infiltração, a erosão e a qualidade da água que segue para o Médio Paraíba e, pela "
        "transposição em Santa Cecília, para o sistema Guandu.")

    k = st.columns(4)
    k[0].metric("Floresta em 2025", pct(p.loc[2025, flo]), f"{fmt(p.loc[2025, flo] - p.loc[1985, flo], 1, sinal=True)} p.p. desde 1985")
    k[1].metric("Pastagem em 2025", pct(p.loc[2025, pas]), f"{fmt(p.loc[2025, pas] - p.loc[1985, pas], 1, sinal=True)} p.p. desde 1985",
                delta_color="off")
    k[2].metric("Área urbanizada em 2025", pct(p.loc[2025, urb]),
                f"de {fmt(c.loc[1985, urb] / 1000, 1)} mil para {fmt(c.loc[2025, urb] / 1000, 1)} mil ha", delta_color="off",
                delta_arrow="off")
    k[3].metric("Vegetação nativa na beira dos rios", pct(rr.loc[2025, "nativa_zona_pct"]),
                f"{fmt(rr.loc[2025, 'nativa_zona_pct'] - rr.loc[1985, 'nativa_zona_pct'], 1, sinal=True)} p.p. desde 1985",
                help="Floresta e área úmida na faixa de 30 m dos rios e no entorno de 50 m das nascentes.")

    st.subheader("O mapa da bacia em quatro momentos")
    ui.mapa_uso("panorama")

    st.subheader("Quarenta anos em um gráfico")
    pico = r[pas]["pico"]
    st.markdown(
        f"A floresta passou de {pct(p.loc[1985, flo])} para {pct(p.loc[2025, flo])} da bacia "
        f"({fmt((c.loc[2025, flo] - c.loc[1985, flo]) / 1000, 1, sinal=True)} mil ha). A pastagem ficou entre "
        f"{fmt(p[pas].min(), 0)}% e {fmt(p[pas].max(), 0)}% da bacia em todo o período, com pico em {pico['ano']}; o "
        f"mosaico de usos caiu de {pct(p.loc[1985, mos])} para {pct(p.loc[2025, mos])}, e a área urbana dobrou, de "
        f"{pct(p.loc[1985, urb])} para {pct(p.loc[2025, urb])}. É uma bacia de pasto, com a floresta voltando devagar.")
    ui.grafico(graficos.composicao(comp), None)
    ui.legenda_classes()
    st.caption(FONTE_C11)

    st.subheader("O que ganhou e o que perdeu")
    st.caption("Área em 2025 menos área em 1985, por classe")
    ui.grafico(graficos.mudanca_liquida(comp, altura=320), None)
    st.subheader("De onde veio a floresta que voltou")
    ganho = r["floresta_ganho_por_origem_ha"]
    perda = r["floresta_perda_por_destino_ha"]
    st.markdown(
        f"Entre 1985 e 2025, {fmt(sum(ganho.values()) / 1000, 1)} mil ha viraram floresta, quase todos sobre pasto "
        f"({fmt(ganho['Pastagem'] / 1000, 1)} mil) e mosaico de usos ({fmt(ganho['Mosaico de usos'] / 1000, 1)} mil). "
        f"No sentido contrário, {fmt(sum(perda.values()) / 1000, 1)} mil ha de floresta deram lugar a outro uso, a "
        f"maior parte a pasto ({fmt(perda['Pastagem'] / 1000, 1)} mil, "
        f"{pct(100 * perda['Pastagem'] / sum(perda.values()), 0)}). O saldo é o ganho de "
        f"{fmt((c.loc[2025, flo] - c.loc[1985, flo]) / 1000, 1)} mil ha.")
    st.caption("Trocas entre classes de 1985 para 2025 (sem a área que ficou igual); fluxos de 300 ha ou mais")
    ui.grafico(graficos.sankey(dados.tabela("transicoes_periodos.csv")), FONTE_C11)
