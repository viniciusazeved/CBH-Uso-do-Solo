"""Metodologia e dados: fontes, recorte, limites do mapa, mudança de coleção e downloads."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

from .. import dados, graficos, ui
from ..estilo import fmt, pct


def pagina() -> None:
    r = dados.resumo()
    st.title("Metodologia e dados")

    st.subheader("Como fizemos")
    st.markdown(
        f"Usamos os mapas anuais da Coleção 11 do MapBiomas, de 1985 a 2025, só na porção dos 19 municípios do CBH-MPS "
        f"dentro da Região Hidrográfica III ({fmt(r['area_rh3_ha'] / 1000)} mil ha). Município com parte fora da bacia "
        "entra só com a parte de dentro, e todo número do painel é \"na porção do município na RH-III\". A área de cada "
        "pixel foi calculada sobre o elipsoide WGS84 (na prática igual ao do SIRGAS 2000), sem a distorção de uma projeção plana, e os números do "
        "panorama foram recalculados por uma segunda rotina, independente da primeira: 111 checagens, sem divergência.")
    fontes = pd.DataFrame([
        ("Uso e cobertura do solo", "MapBiomas Coleção 11", "1985 a 2025, anual, pixel de 30 m"),
        ("Desmatamento e vegetação secundária", "MapBiomas Coleção 11 (versão 5)", "1987 a 2025; 2025 com eventos incompletos"),
        ("Fogo", "MapBiomas Fogo, Coleção 4", "1985 a 2024"),
        ("Rios e nascentes", "Base cartográfica contínua 1:25.000 do IBGE (BC25)", "faixa de 30 m e raio de 50 m"),
        ("Relevo", "Copernicus GLO-30", "modelo digital de elevação de 30 m"),
        ("Unidades de conservação", "Base mundial de áreas protegidas (WDPA)", "polígonos que tocam a RH-III"),
        ("Limites", "IBGE (municípios) e INEA (RH-III)", "porção de cada município na RH-III"),
    ], columns=["Tema", "Fonte", "Período e detalhe"])
    st.dataframe(fontes, hide_index=True, width="stretch")

    st.subheader("O que o mapa enxerga e o que não enxerga")
    st.markdown(
        "Na Mata Atlântica, a Coleção 11 acerta 93,2% dos pontos de conferência no nível 1 (floresta, vegetação não "
        "florestal, agropecuária, área não vegetada e água) e 87,3% no nível 2, contra 10.840 pontos independentes do "
        "Lapig/UFG ([apêndice metodológico da Mata Atlântica, Coleção 11, seção 7.1]"
        "(https://brasil.mapbiomas.org/wp-content/uploads/sites/3/2026/08/Atlantic-Forest-Appendix-ATBD-Collection-11.pdf)).")
    st.markdown(
        "Limites que valem para todo o painel: com pixel de 30 m, mancha menor que cerca de 1 ha some; eucalipto adulto "
        "pode cair como floresta no Rio de Janeiro; campo sujo e pasto se confundem; e o último ano da série é "
        "provisório.")

    st.subheader("Por que os números mudaram desde abril")
    c = r["c9_x_c11_2023"]
    st.markdown(
        f"Mesmo ano, mesmo satélite, mapa revisado. O painel anterior usava a Coleção 9; para 2023, o mosaico de usos "
        f"caiu de {pct(c['Mosaico de usos']['c9_pct'])} para {pct(c['Mosaico de usos']['c11_pct'])} da bacia e a "
        f"pastagem subiu de {pct(c['Pastagem']['c9_pct'])} para {pct(c['Pastagem']['c11_pct'])}; a floresta foi de "
        f"{pct(c['Formação florestal']['c9_pct'])} para {pct(c['Formação florestal']['c11_pct'])}. A direção não mudou: "
        "nas duas coleções a floresta cresce de 1985 para cá. Números de coleções diferentes não se comparam.")
    ui.grafico(graficos.c9_c11(dados.tabela("c9_x_c11.csv")), "Fonte: MapBiomas Coleções 9 e 11, porção dos 19 municípios "
               "na RH-III. Elaboração: GT SIGA, CBH-MPS.")

    st.subheader("Quanto de cada município está na RH-III")
    mun = dados.municipios()
    tab = mun[["municipio", "area_na_rh3_ha", "pct_territorio_na_rh3", "pct_urbano_na_rh3"]].copy()
    tab[["pct_territorio_na_rh3", "pct_urbano_na_rh3"]] = tab[["pct_territorio_na_rh3", "pct_urbano_na_rh3"]].clip(upper=100)
    tab.columns = ["Município", "Área na RH-III (ha)", "Território na RH-III (%)", "Área urbana de 2025 na RH-III (%)"]
    ui.tabela(tab, {"Área na RH-III (ha)": 0, "Território na RH-III (%)": 1, "Área urbana de 2025 na RH-III (%)": 1},
              altura=35 * (len(tab) + 1) + 3)
    ui.nota("Engenheiro Paulo de Frontin e Petrópolis tocam a RH-III só por erro de borda dos limites (94 ha e 8 ha) e "
            "ficam fora, como na lista oficial do comitê.")

    st.subheader("Dados")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for arq in sorted((dados.DIR / "panorama").glob("*")):
            z.write(arq, arq.name)
    st.download_button("Baixar todas as tabelas do panorama (zip)", buf.getvalue(), file_name="panorama_rh3_1985_2025.zip",
                       mime="application/zip", icon=":material/download:")
    st.caption("CSV com separador vírgula e ponto decimal; código 0 é a RH-III inteira. Elaboração: GT SIGA do Comitê "
               "de Bacias Hidrográficas do Médio Paraíba do Sul. Dados: MapBiomas, IBGE, INEA, Copernicus e WDPA.")
