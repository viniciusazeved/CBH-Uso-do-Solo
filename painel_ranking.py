"""
Painel Interativo — Ranking Ambiental RH3 Medio Paraiba do Sul
Streamlit + Plotly + Folium
"""

import streamlit as st
import pandas as pd
import geopandas as gpd
import plotly.express as px
import plotly.graph_objects as go
import folium
from streamlit_folium import st_folium
import numpy as np
import json
from pathlib import Path


def fmt_br(valor, decimais=0, sinal=False):
    """Formata numero no padrao brasileiro (ponto milhar, virgula decimal)."""
    if sinal:
        s = f"{valor:+,.{decimais}f}"
    else:
        s = f"{valor:,.{decimais}f}"
    # Troca: , -> X, . -> , , X -> .
    return s.replace(",", "X").replace(".", ",").replace("X", ".")

# =============================================================================
#  CONFIG
# =============================================================================

st.set_page_config(
    page_title="Ranking Ambiental RH3",
    page_icon=":droplet:",
    layout="wide",
    initial_sidebar_state="expanded",
)


# Cores MapBiomas
CORES_CLASSES = {
    "Floresta": "#1f8d49",
    "Vegetacao_Natural_Nao_Florestal": "#7dc975",
    "Silvicultura": "#7a5900",
    "Pastagem": "#ffd966",
    "Agricultura": "#e974ed",
    "Mosaico_Agropecuario": "#ffefc3",
    "Area_Urbana": "#d4271e",
    "Mineracao": "#9c0027",
    "Agua": "#0000ff",
    "Area_Nao_Vegetada": "#d89f5c",
    "Aquicultura": "#00bfff",
    "Nao_Observado": "#cccccc",
}

NOMES_CLASSES = {
    "Floresta": "Floresta",
    "Vegetacao_Natural_Nao_Florestal": "Veg. Natural Nao Florestal",
    "Silvicultura": "Silvicultura",
    "Pastagem": "Pastagem",
    "Agricultura": "Agricultura",
    "Mosaico_Agropecuario": "Mosaico Agropecuario",
    "Area_Urbana": "Area Urbana",
    "Mineracao": "Mineracao",
    "Agua": "Agua",
    "Area_Nao_Vegetada": "Area Nao Vegetada",
    "Aquicultura": "Aquicultura",
    "Nao_Observado": "Nao Observado",
}

INDICADORES_MAPA = {
    "ICV_2023_pct": "Cobertura Vegetal Nativa 2023 (%)",
    "persistencia_florestal_pct": "Persistencia Florestal 1985-2023 (%)",
    "estabilidade_uso_pct": "Estabilidade do Uso 1985-2023 (%)",
    "recup_florestal_2010_2023_ha": "Recuperacao Florestal 2010-2023 (ha)",
    "pasto_para_mata_recente_ha": "Regeneracao Pasto->Mata 2010-2020 (ha)",
    "variacao_veg_ha": "Saldo Liquido Veg. Nativa 1985-2023 (ha)",
    "desmatamento_recente_ha": "Desmatamento Recente 2020-2023 (ha)",
    "variacao_pressao_antropica_pp": "Variacao Pressao Antropica 1985-2023 (pp)",
    "maior_fragmento_florestal_ha": "Maior Fragmento Florestal 2023 (ha)",
    "densidade_fragmentos_por_kha": "Densidade de Fragmentos (n/1000 ha)",
    "saldo_florestal_total_ha": "Saldo Florestal Transicoes 1985-2023 (ha)",
    "pressao_antropica_2023_pct": "Pressao Antropica 2023 (%)",
    "cresc_urbano_ha": "Crescimento Urbano 1985-2023 (ha)",
    "shannon_2023": "Diversidade de Uso (Shannon)",
    "area_total_na_rh3_ha": "Area Total na RH3 (ha)",
}


# =============================================================================
#  LOAD DATA
# =============================================================================

@st.cache_data
def load_data():
    df_lulc = pd.read_csv("./output/lulc_municipios_rh3.csv")
    df_trans = pd.read_csv("./output/transicoes_municipios_rh3.csv")
    df_idx = pd.read_csv("./output/tabelas/indices_municipais_rh3.csv")

    # Carregar geometrias e reprojetar para WGS84
    gdf = gpd.read_file("./data/municipios_clipped_rh3.shp", encoding="utf-8")
    gdf = gdf.to_crs(epsg=4326)

    # Corrigir nomes com encoding quebrado — usar os nomes do df_idx como referencia
    # Fazer merge por codigo IBGE
    gdf = gdf.rename(columns={"NM_MUN": "NM_MUN_orig"})
    gdf["CD_MUN"] = gdf["CD_MUN"].astype(str)
    df_idx["cod_ibge"] = df_idx["cod_ibge"].astype(str)
    gdf = gdf.merge(df_idx, left_on="CD_MUN", right_on="cod_ibge", how="left")

    return df_lulc, df_trans, df_idx, gdf


def _normalizar(serie, inverter=False):
    min_val = serie.min()
    max_val = serie.max()
    if max_val == min_val:
        return pd.Series([50.0] * len(serie), index=serie.index)
    n = (serie - min_val) / (max_val - min_val) * 100
    return (100 - n) if inverter else n


# ============================================================================
#  SCORE COMPOSTO v2 — 10 INDICADORES EM 4 BLOCOS
#
#  Bloco 1 — Cobertura e Estabilidade (30%)
#    1. Cobertura Vegetal Nativa 2023        — 15%
#    2. Persistencia Florestal 1985-2023     — 8%
#    3. Estabilidade do Uso 1985-2023        — 7%
#  Bloco 2 — Dinamica Positiva (25%)
#    4. Recuperacao Florestal 2010-2023      — 12%
#    5. Regeneracao Pasto->Mata 2010-2020    — 8%
#    6. Saldo Liquido Veg. Nativa 1985-2023  — 5%
#  Bloco 3 — Dinamica Negativa Invertida (25%)
#    7. Desmatamento Recente 2020-2023       — 12% (invertido)
#    8. Variacao Pressao Antropica           — 13% (invertido)
#  Bloco 4 — Estrutura da Paisagem (20%)
#    9. Maior Fragmento Florestal 2023       — 12%
#   10. Densidade de Fragmentos              — 8% (invertido)
# ============================================================================

SCORE_PESOS = {
    "score_cobertura":         0.15,
    "score_persistencia":      0.08,
    "score_estabilidade":      0.07,
    "score_recuperacao":       0.12,
    "score_regeneracao":       0.08,
    "score_saldo_longo":       0.05,
    "score_desmatamento":      0.12,
    "score_pressao":           0.13,
    "score_maior_fragmento":   0.12,
    "score_densidade_frag":    0.08,
}

# Mapeamento score_col -> (coluna_origem, invertido, label_curto, bloco)
SCORE_DEF = [
    ("score_cobertura",       "ICV_2023_pct",                  False, "Cobertura Vegetal", "Cobertura e Estabilidade"),
    ("score_persistencia",    "persistencia_florestal_pct",    False, "Persistencia Florestal", "Cobertura e Estabilidade"),
    ("score_estabilidade",    "estabilidade_uso_pct",          False, "Estabilidade do Uso", "Cobertura e Estabilidade"),
    ("score_recuperacao",     "recup_florestal_2010_2023_ha",  False, "Recuperacao Florestal", "Dinamica Positiva"),
    ("score_regeneracao",     "pasto_para_mata_recente_ha",    False, "Regeneracao Pasto->Mata", "Dinamica Positiva"),
    ("score_saldo_longo",     "variacao_veg_ha",               False, "Saldo Liquido 1985-2023", "Dinamica Positiva"),
    ("score_desmatamento",    "desmatamento_recente_ha",       True,  "Desmatamento Recente", "Dinamica Negativa"),
    ("score_pressao",         "variacao_pressao_antropica_pp", True,  "Pressao Antropica", "Dinamica Negativa"),
    ("score_maior_fragmento", "maior_fragmento_florestal_ha",  False, "Maior Fragmento", "Estrutura da Paisagem"),
    ("score_densidade_frag",  "densidade_fragmentos_por_kha",  True,  "Densidade de Fragmentos", "Estrutura da Paisagem"),
]


def calcular_scores(df_idx):
    df = df_idx.copy()
    for score_col, src_col, inverter, _, _ in SCORE_DEF:
        df[score_col] = _normalizar(df[src_col], inverter=inverter)
    df["score_ambiental"] = sum(df[col] * peso for col, peso in SCORE_PESOS.items())
    return df


# =============================================================================
#  LOAD
# =============================================================================

df_lulc, df_trans, df_idx, gdf = load_data()
df_scores = calcular_scores(df_idx)
municipios_lista = sorted(df_idx["municipio"].unique())

# =============================================================================
#  SIDEBAR
# =============================================================================

st.sidebar.image("logo/LOGO - CBH MPS_colorida.png", width=180)
st.sidebar.title("Ranking Ambiental Municipal")
st.sidebar.markdown("MapBiomas Colecao 9 (1985-2023)")
st.sidebar.divider()

pagina = st.sidebar.radio(
    "Navegacao",
    ["🏆 Ranking Geral", "🏅 Rankings por Categoria", "🗺️ Mapa Interativo",
     "🛰️ Mapa LULC 1985 vs 2023", "📊 Evolucao Temporal", "🔄 Transicoes",
     "🏙️ Perfil Municipal", "📐 Metodologia"],
    index=0,
)

st.sidebar.divider()
st.sidebar.info(
    "**Versao Ranking.** Existe tambem a versao Diagnostico (sem ranking, com tipologia "
    "e mapa LULC) em [cbh-uso-do-solo-painel.streamlit.app](https://cbh-uso-do-solo-painel.streamlit.app)."
)
st.sidebar.caption("CBH Medio Paraiba do Sul · GT SIGA")
st.sidebar.caption("Dados: MapBiomas Colecao 9")


# =============================================================================
#  PAGINA 1: RANKING GERAL
# =============================================================================

if pagina == "🏆 Ranking Geral":
    st.title("🏆 Ranking Ambiental Municipal — RH3")
    st.markdown("**Medio Paraiba do Sul** | MapBiomas Colecao 9 (1985-2023)")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Municipios", f"{len(df_idx)}")
    col2.metric("Area Total RH3", f"{fmt_br(df_idx['area_total_na_rh3_ha'].sum())} ha")
    media_icv = df_idx["ICV_2023_pct"].mean()
    col3.metric("ICV Medio 2023", f"{fmt_br(media_icv, 1)}%")
    media_pressao = df_idx["pressao_antropica_2023_pct"].mean()
    col4.metric("Pressao Antropica Media", f"{fmt_br(media_pressao, 1)}%")

    st.divider()

    # Parametros avaliados
    st.subheader("Parametros Avaliados")
    st.markdown("""
O **Score Ambiental Composto** combina **10 indicadores** em **4 blocos tematicos**.
Cada indicador e normalizado de 0 a 100 (Min-Max entre os 19 municipios) e ponderado
conforme sua relevancia para a conservacao ambiental na bacia.
""")

    param_col1, param_col2 = st.columns(2)
    with param_col1:
        st.markdown("""
**Bloco 1 — Cobertura e Estabilidade (30%)**

| # | Indicador | Peso | O que mede |
|:-:|-----------|:----:|------------|
| 1 | **Cobertura Vegetal Nativa** | 15% | % de vegetacao nativa em 2023 |
| 2 | **Persistencia Florestal** | 8% | % que foi floresta em TODOS os 9 anos-marco (1985-2023) |
| 3 | **Estabilidade do Uso** | 7% | % com a MESMA classe LULC em 1985 e 2023 |

**Bloco 2 — Dinamica Positiva (25%)**

| # | Indicador | Peso | O que mede |
|:-:|-----------|:----:|------------|
| 4 | **Recuperacao Florestal** | 12% | Ganho de area florestal 2010-2023 (ha) |
| 5 | **Regeneracao Pasto -> Mata** | 8% | Pastagem convertida em floresta 2010-2020 (ha) |
| 6 | **Saldo Liquido 1985-2023** | 5% | Variacao absoluta de veg. nativa em 38 anos (ha) |
""")
    with param_col2:
        st.markdown("""
**Bloco 3 — Dinamica Negativa Invertida (25%)**

| # | Indicador | Peso | O que mede |
|:-:|-----------|:----:|------------|
| 7 | **Desmatamento Recente** | 12% | Area desmatada 2020-2023 (invertido) |
| 8 | **Pressao Antropica** | 13% | Variacao da pressao antropica 1985-2023 (invertido) |

**Bloco 4 — Estrutura da Paisagem (20%)**

| # | Indicador | Peso | O que mede |
|:-:|-----------|:----:|------------|
| 9 | **Maior Fragmento Florestal** | 12% | Tamanho do maior remanescente continuo (ha) |
| 10 | **Densidade de Fragmentos** | 8% | Numero de patches por 1000 ha (invertido) |
""")

    st.info("""
**Normalizacao:** Cada indicador e normalizado pelo metodo Min-Max (0-100) entre os 19 municipios.
Para indicadores **invertidos** (Desmatamento, Pressao e Densidade de Fragmentos), a escala e invertida:
menor valor observado = maior score. Score final = soma ponderada dos 10 indices.
""")

    st.divider()

    # Ranking principal
    st.subheader("Ranking Geral — Score Ambiental Composto")

    rank = df_scores.sort_values("score_ambiental", ascending=False).reset_index(drop=True)
    rank.index = rank.index + 1

    fig = go.Figure()
    cores_rank = px.colors.sequential.Greens_r[:len(rank)]
    if len(cores_rank) < len(rank):
        cores_rank = px.colors.sample_colorscale("Greens", np.linspace(0.3, 0.95, len(rank)))[::-1]

    fig.add_trace(go.Bar(
        y=rank["municipio"],
        x=rank["score_ambiental"],
        orientation="h",
        marker=dict(color=rank["score_ambiental"], colorscale="Greens", cmin=0, cmax=100),
        text=[fmt_br(v, 1) for v in rank["score_ambiental"]],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Score: %{x:.1f}<extra></extra>",
    ))
    fig.update_layout(
        height=max(500, len(rank) * 35),
        yaxis=dict(autorange="reversed", title=""),
        xaxis=dict(title="Score Ambiental (0-100)", range=[0, 105]),
        margin=dict(l=200, r=50, t=30, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Detalhamento dos scores
    st.subheader("Composicao do Score por Municipio")
    st.caption("Cada barra mostra a contribuicao dos 10 indices (ja ponderados) que somam o score final.")

    # Empilhado com 10 componentes (ja multiplicados pelos pesos = contribuicao real)
    rank_stack = rank.copy()
    for score_col, _, _, _, _ in SCORE_DEF:
        rank_stack[f"contrib_{score_col}"] = rank_stack[score_col] * SCORE_PESOS[score_col]

    # Paleta por bloco
    cores_bloco = {
        "Cobertura e Estabilidade": ["#1f8d49", "#2ea860", "#4cc377"],
        "Dinamica Positiva":        ["#7dc975", "#a8d96f", "#c5e09f"],
        "Dinamica Negativa":        ["#d4271e", "#e15c50"],
        "Estrutura da Paisagem":    ["#7a5900", "#a8731d"],
    }
    bloco_counter = {b: 0 for b in cores_bloco}

    fig2 = go.Figure()
    for score_col, _, _, label, bloco in SCORE_DEF:
        idx_cor = bloco_counter[bloco]
        cor = cores_bloco[bloco][idx_cor]
        bloco_counter[bloco] += 1
        fig2.add_trace(go.Bar(
            y=rank_stack["municipio"],
            x=rank_stack[f"contrib_{score_col}"],
            name=f"{label} ({int(SCORE_PESOS[score_col]*100)}%)",
            orientation="h",
            marker_color=cor,
            hovertemplate=(f"<b>%{{y}}</b><br>{label}<br>"
                           f"Score: %{{customdata:.1f}}<br>"
                           f"Contribuicao: %{{x:.1f}}<extra></extra>"),
            customdata=rank_stack[score_col],
        ))

    fig2.update_layout(
        barmode="stack",
        height=max(600, len(rank_stack) * 38),
        yaxis=dict(autorange="reversed", title=""),
        xaxis=dict(title="Contribuicao ponderada (soma = score final, max=100)", range=[0, 105]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5, font=dict(size=10)),
        margin=dict(l=200, r=50, t=80, b=40),
    )
    st.plotly_chart(fig2, use_container_width=True)

    # Tabela completa
    with st.expander("📋 Tabela completa de indices"):
        st.dataframe(
            df_idx.sort_values("ICV_2023_pct", ascending=False).reset_index(drop=True),
            use_container_width=True,
            height=500,
        )


# =============================================================================
#  PAGINA: RANKINGS POR CATEGORIA
# =============================================================================

elif pagina == "🏅 Rankings por Categoria":
    st.title("🏅 Rankings por Categoria")
    st.caption("Cada categoria classifica os 19 municipios da RH3 por um indicador especifico — sem peso composto.")

    RANKINGS = [
        # Bloco — Cobertura e Estabilidade
        {"label": "🌳 Municipio mais verde (Cobertura Vegetal Nativa 2023)",
         "coluna": "ICV_2023_pct", "unidade": "%", "ordem": "desc",
         "decimais": 1, "cor": "#1f8d49",
         "descricao": (
            "**O que mede:** percentual do territorio coberto por **vegetacao nativa em 2023** — "
            "floresta nativa (formacao florestal, savanica, mangue, restinga arborea) somada com vegetacao "
            "natural nao florestal (campo, area umida, restinga herbacea).\n\n"
            "**Como e calculado:** soma das areas das classes nativas do MapBiomas 2023 dividida pela area "
            "do municipio dentro da RH3.\n\n"
            "**Como ler:** maior = melhor. Indicador classico do quao 'verde' o municipio e hoje, "
            "independente da sua trajetoria historica."
         )},
        {"label": "🌲 Maior Persistencia Florestal (1985-2023, %)",
         "coluna": "persistencia_florestal_pct", "unidade": "%", "ordem": "desc",
         "decimais": 1, "cor": "#1f8d49",
         "descricao": (
            "**O que mede:** percentual do territorio que foi floresta em **TODOS os 9 anos-marco** "
            "do MapBiomas (1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2023). Captura conservacao "
            "historica real — area que nunca deixou de ser floresta em 38 anos.\n\n"
            "**Como e calculado:** intersecao logica (AND) das mascaras binarias de floresta dos 9 anos. "
            "Pixel persistente = foi floresta em todos os anos da serie.\n\n"
            "**Como ler:** maior = melhor. Premia quem **conservou ao longo do tempo**, nao apenas quem "
            "recuperou recentemente. Itatiaia lidera por causa do Parque Nacional e areas ingremes da Mantiqueira."
         )},
        {"label": "📌 Maior Estabilidade do Uso (1985 vs 2023, %)",
         "coluna": "estabilidade_uso_pct", "unidade": "%", "ordem": "desc",
         "decimais": 1, "cor": "#2ea860",
         "descricao": (
            "**O que mede:** percentual do territorio com **a mesma classe de uso do solo em 1985 e 2023** — "
            "qualquer classe, nao so floresta. Mede o quanto o municipio 'ficou parado' em 38 anos.\n\n"
            "**Como e calculado:** comparacao pixel-a-pixel entre o mapa de 1985 e o de 2023; conta-se os "
            "pixels onde a classe nao mudou.\n\n"
            "**Como ler:** maior = paisagem mais previsivel. **Atencao:** estabilidade alta pode significar "
            "tanto conservacao (floresta estavel) quanto antropizacao consolidada (pasto historico que se mantem)."
         )},
        # Bloco — Dinamica Positiva
        {"label": "🌱 Maior Recuperacao Florestal (2010-2023)",
         "coluna": "recup_florestal_2010_2023_ha", "unidade": "ha", "ordem": "desc",
         "decimais": 0, "cor": "#1f8d49",
         "descricao": (
            "**O que mede:** **ganho liquido de area florestal entre 2010 e 2023**, em hectares "
            "(area de floresta em 2023 menos area de floresta em 2010).\n\n"
            "**Como e calculado:** diferenca entre as areas de floresta nos dois anos.\n\n"
            "**Como ler:** maior = melhor. Captura recuperacao **recente** — o esforco dos ultimos 13 anos. "
            "Valores negativos significam perda de floresta no periodo."
         )},
        {"label": "🔄 Maior Regeneracao Pasto -> Mata (2010-2020)",
         "coluna": "pasto_para_mata_recente_ha", "unidade": "ha", "ordem": "desc",
         "decimais": 0, "cor": "#7dc975",
         "descricao": (
            "**O que mede:** **area que era pastagem em 2010 e virou floresta em 2020**, em hectares. "
            "Esforco especifico de recuperacao sobre area antropizada.\n\n"
            "**Como e calculado:** transicao no MapBiomas — pixel que era pasto (classe 15) em 2010 "
            "e virou floresta (classes 3, 4, 5, 6, 49) em 2020.\n\n"
            "**Como ler:** maior = melhor. Diferente da Recuperacao Florestal: aqui mede apenas o "
            "**esforco positivo** de tirar pasto e ganhar mata, nao conta outras conversoes."
         )},
        {"label": "📈 Maior Saldo Liquido de Vegetacao Nativa (1985-2023)",
         "coluna": "variacao_veg_ha", "unidade": "ha", "ordem": "desc",
         "decimais": 0, "cor": "#1f8d49",
         "descricao": (
            "**O que mede:** **variacao absoluta da area de vegetacao nativa em 38 anos**, em hectares "
            "(area em 2023 menos area em 1985).\n\n"
            "**Como e calculado:** diferenca simples entre os estoques de vegetacao nativa nos dois "
            "extremos do periodo.\n\n"
            "**Como ler:** maior = melhor. Janela **longa** — captura tendencia historica. "
            "Valores negativos significam perda de vegetacao em 38 anos."
         )},
        # Bloco — Dinamica Negativa (invertidos no ranking)
        {"label": "🛡️ Menor Pressao Antropica (2023)",
         "coluna": "pressao_antropica_2023_pct", "unidade": "%", "ordem": "asc",
         "decimais": 1, "cor": "#7dc975",
         "descricao": (
            "**O que mede:** percentual do territorio com **uso antropico em 2023** — pastagem, "
            "agricultura, mosaico, silvicultura, area urbana e mineracao.\n\n"
            "**Como e calculado:** soma das areas antropicas dividida pela area total do municipio.\n\n"
            "**Como ler:** **INVERTIDO — menor = melhor.** Municipio com menos pressao antropica "
            "tem mais natureza preservada. Porto Real lidera o oposto (~91%) por ser polo industrial."
         )},
        {"label": "⏳ Menor Desmatamento Recente (2020-2023)",
         "coluna": "desmatamento_recente_ha", "unidade": "ha", "ordem": "asc",
         "decimais": 0, "cor": "#7dc975",
         "descricao": (
            "**O que mede:** **area de vegetacao nativa convertida em uso antropico entre 2020 e 2023**, "
            "em hectares.\n\n"
            "**Como e calculado:** soma das transicoes de classes nativas (floresta + veg. nao florestal) "
            "para classes antropicas no periodo recente.\n\n"
            "**Como ler:** **INVERTIDO — menor = melhor.** Captura **desmatamento atual**, nao historico. "
            "Mostra o que o municipio fez nos ultimos 3 anos."
         )},
        # Bloco — Estrutura da Paisagem
        {"label": "🌲 Maior Fragmento Florestal Continuo (2023)",
         "coluna": "maior_fragmento_florestal_ha", "unidade": "ha", "ordem": "desc",
         "decimais": 0, "cor": "#1f8d49",
         "descricao": (
            "**O que mede:** **tamanho (em hectares) do maior remanescente continuo de floresta** do "
            "municipio em 2023.\n\n"
            "**Como e calculado:** algoritmo de componentes conexos (`scipy.ndimage.label` com "
            "8-conectividade) sobre a mascara binaria de floresta de 2023, em resolucao de 30 m. "
            "Mede-se a area do maior grupo encontrado.\n\n"
            "**Como ler:** maior = melhor. **1.000 ha em um bloco continuo valem muito mais que "
            "1.000 ha em cem manchas pequenas** — biodiversidade, conectividade ecologica e "
            "resiliencia climatica dependem de fragmentos grandes. Resende lidera por causa do "
            "mosaico Bocaina/Mantiqueira/Itatiaia."
         )},
        {"label": "🧩 Menor Fragmentacao (densidade de patches)",
         "coluna": "densidade_fragmentos_por_kha", "unidade": "/kha", "ordem": "asc",
         "decimais": 2, "cor": "#7dc975",
         "descricao": (
            "**O que mede:** **numero de fragmentos florestais por 1.000 hectares** de territorio. "
            "Quantifica o quanto a paisagem esta 'quebrada em pedacinhos'.\n\n"
            "**Como e calculado:** numero total de componentes conexos de floresta no municipio "
            "(mesma analise do indicador anterior) dividido pela area do municipio, multiplicado por 1.000.\n\n"
            "**Como ler:** **INVERTIDO — menor = melhor.** Poucos fragmentos por area = paisagem "
            "mais agregada, com floresta conectada. Muitos fragmentos por area = floresta picotada, "
            "mais vulneravel a efeitos de borda e mudancas climaticas."
         )},
        # Outros — diagnostico complementar
        {"label": "✅ Melhor Saldo Florestal por Transicoes (1985-2023)",
         "coluna": "saldo_florestal_total_ha", "unidade": "ha", "ordem": "desc",
         "decimais": 0, "cor": "#1f8d49",
         "descricao": (
            "**O que mede:** **diferenca entre regeneracao e desmatamento** ao longo de todo o periodo "
            "(1985-2023), considerando apenas o eixo pasto<->mata, em hectares.\n\n"
            "**Como e calculado:** total de 'Pastagem para Floresta' menos total de 'Floresta para "
            "Pastagem' no MapBiomas, em todo o periodo.\n\n"
            "**Como ler:** maior positivo = melhor. Difere do **Saldo Liquido de Veg. Nativa** porque "
            "considera apenas o eixo pasto<->mata, nao todas as conversoes."
         )},
        {"label": "🏙️ Menor Crescimento Urbano (1985-2023)",
         "coluna": "cresc_urbano_ha", "unidade": "ha", "ordem": "asc",
         "decimais": 0, "cor": "#7dc975",
         "descricao": (
            "**O que mede:** **expansao da area urbana em 38 anos**, em hectares (area urbana em "
            "2023 menos area urbana em 1985).\n\n"
            "**Como e calculado:** diferenca entre area da classe 'Area Urbana' (codigo 24) nos "
            "dois anos.\n\n"
            "**Como ler:** **INVERTIDO — menor = melhor (para fins ambientais).** Importante: "
            "municipio com pouca urbanizacao pode ser rural sem ser conservacionista; municipio "
            "com muita urbanizacao pode ser polo economico (CSN em Volta Redonda). "
            "**Leitura ambiental, nao de desenvolvimento.**"
         )},
        {"label": "🌐 Maior Diversidade de Uso (Shannon 2023)",
         "coluna": "shannon_2023", "unidade": "", "ordem": "desc",
         "decimais": 2, "cor": "#fc8114",
         "descricao": (
            "**O que mede:** **indice de Shannon aplicado as proporcoes das classes de uso do solo** "
            "em 2023. Quantifica o quanto a paisagem e 'misturada' (heterogenea) vs. 'monotona' (homogenea).\n\n"
            "**Como e calculado:** H = -Σ (pᵢ × ln(pᵢ)), onde pᵢ e a fracao da classe i no municipio. "
            "Vai de 0 (uma unica classe domina) ate ln(n) (paisagem perfeitamente equilibrada).\n\n"
            "**Como ler:** maior = paisagem mais heterogenea. **ATENCAO:** alta diversidade NAO e "
            "necessariamente melhor ambientalmente — pode significar mosaico saudavel (varias formacoes "
            "naturais) ou antropizacao variada (pasto + agricultura + urbano). Indicador **descritivo**, "
            "nao normativo."
         )},
        {"label": "♻️ Maior Eficiencia de Regeneracao",
         "coluna": "eficiencia_regeneracao", "unidade": "", "ordem": "desc",
         "decimais": 2, "cor": "#1f8d49",
         "descricao": (
            "**O que mede:** **razao entre area que regenerou (pasto -> mata) e area que foi desmatada "
            "(mata -> pasto)** ao longo de 1985-2023. Mostra quantos hectares de mata foram recuperados "
            "para cada hectare perdido.\n\n"
            "**Como e calculado:** total de 'Pasto -> Floresta' dividido por total de 'Floresta -> Pasto' "
            "(adimensional).\n\n"
            "**Como ler:** maior = melhor.\n"
            "- **Valor = 1,00:** empate (recupera tanto quanto perde)\n"
            "- **Valor = 2,00:** recupera o dobro do que perde\n"
            "- **Valor = 0,50:** so recupera metade do que perde\n"
            "- **Valor 'infinito':** quando nao houve desmatamento (raro)"
         )},
    ]

    rk_labels = [r["label"] for r in RANKINGS]
    cat_idx = st.selectbox("Categoria:", range(len(rk_labels)),
                           format_func=lambda i: rk_labels[i], key="rk_cat")
    rk = RANKINGS[cat_idx]
    asc = (rk["ordem"] == "asc")

    # Caixa didatica explicando o indicador
    if "descricao" in rk:
        st.info(rk["descricao"])

    df_rk = df_idx[["municipio", rk["coluna"], "area_total_na_rh3_ha"]].dropna()
    df_rk = df_rk.sort_values(rk["coluna"], ascending=asc).reset_index(drop=True)
    df_rk["posicao"] = df_rk.index + 1

    # Podio Top 3
    st.subheader("🏆 Pódio")
    medalhas = ["🥇", "🥈", "🥉"]
    estilos = ["#FFD700", "#C0C0C0", "#CD7F32"]
    podio_cols = st.columns(3)
    for i in range(min(3, len(df_rk))):
        with podio_cols[i]:
            mun = df_rk.iloc[i]["municipio"]
            valor = df_rk.iloc[i][rk["coluna"]]
            unidade = rk["unidade"]
            valor_fmt = fmt_br(valor, rk["decimais"])
            st.markdown(
                f"<div style='border:2px solid {estilos[i]};border-radius:8px;"
                f"padding:14px;text-align:center;background:rgba({int(estilos[i][1:3],16)},"
                f"{int(estilos[i][3:5],16)},{int(estilos[i][5:7],16)},0.08)'>"
                f"<div style='font-size:32px'>{medalhas[i]}</div>"
                f"<div style='font-size:18px;font-weight:bold;margin:4px 0'>{mun}</div>"
                f"<div style='font-size:22px;color:{rk['cor']};font-weight:bold'>"
                f"{valor_fmt} {unidade}</div></div>",
                unsafe_allow_html=True,
            )

    st.divider()

    # Barra horizontal completa
    st.subheader(f"Classificacao Completa — {rk['label']}")

    df_plot = df_rk.copy()
    fig = go.Figure(go.Bar(
        y=df_plot["municipio"],
        x=df_plot[rk["coluna"]],
        orientation="h",
        marker=dict(color=df_plot[rk["coluna"]],
                    colorscale="Greens" if not asc else "Greens_r",
                    showscale=False),
        text=[f"{fmt_br(v, rk['decimais'])} {rk['unidade']}".strip()
              for v in df_plot[rk["coluna"]]],
        textposition="outside",
        hovertemplate=f"<b>%{{y}}</b><br>{rk['label']}: %{{x:,.{rk['decimais']}f}} {rk['unidade']}<extra></extra>",
    ))
    direcao = "asc" if asc else "desc"
    fig.update_layout(
        height=max(500, len(df_plot) * 32),
        yaxis=dict(autorange="reversed", title=""),
        xaxis=dict(title=f"{rk['label']} ({rk['unidade']})" if rk["unidade"] else rk["label"]),
        margin=dict(l=200, r=80, t=30, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Tabela completa
    with st.expander("Tabela completa desta categoria"):
        df_show = df_rk[["posicao", "municipio", rk["coluna"], "area_total_na_rh3_ha"]].copy()
        df_show.columns = ["Posicao", "Municipio", rk["label"], "Area na RH3 (ha)"]
        st.dataframe(df_show, use_container_width=True, hide_index=True, height=400)

    st.info(
        "**Como ler:** cada categoria responde a uma pergunta diferente. Um municipio pode "
        "estar bem em uma e mal em outra. O ranking geral (primeira pagina) combina seis "
        "delas em uma pontuacao composta — esta pagina permite olhar critério a critério."
    )


# =============================================================================
#  PAGINA 2: MAPA INTERATIVO
# =============================================================================

elif pagina == "🗺️ Mapa Interativo":
    st.title("🗺️ Mapa Interativo — Indicadores Municipais")

    indicador = st.selectbox("Selecione o indicador:", list(INDICADORES_MAPA.keys()),
                             format_func=lambda x: INDICADORES_MAPA[x])

    # Definir paleta e escala
    inv_paletas = {"pressao_antropica_2023_pct", "desmatamento_recente_ha", "cresc_urbano_ha"}
    if indicador in inv_paletas:
        cmap = "YlOrRd"
    else:
        cmap = "YlGn"

    # Merge indicador ao gdf
    gdf_plot = gdf.copy()
    vals = gdf_plot[indicador]

    # Centroide para centralizar mapa
    bounds = gdf_plot.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    # Plotly choropleth
    gdf_plot_json = json.loads(gdf_plot.to_json())

    # Adicionar id para plotly
    for i, feat in enumerate(gdf_plot_json["features"]):
        feat["id"] = str(i)
    gdf_plot["_id"] = [str(i) for i in range(len(gdf_plot))]

    fig = px.choropleth_mapbox(
        gdf_plot,
        geojson=gdf_plot_json,
        locations="_id",
        color=indicador,
        hover_name="municipio",
        hover_data={indicador: ":.1f", "area_total_na_rh3_ha": ":.0f", "_id": False},
        color_continuous_scale=cmap,
        mapbox_style="carto-positron",
        center={"lat": center_lat, "lon": center_lon},
        zoom=8.5,
        opacity=0.7,
        labels={indicador: INDICADORES_MAPA[indicador], "area_total_na_rh3_ha": "Area RH3 (ha)"},
    )
    fig.update_layout(
        height=600,
        margin=dict(l=0, r=0, t=30, b=0),
        coloraxis_colorbar=dict(title=dict(text=INDICADORES_MAPA[indicador], font=dict(size=11))),
    )
    st.plotly_chart(fig, use_container_width=True)

    # Mini ranking ao lado
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Top 5 — Maiores valores")
        top5 = df_idx.nlargest(5, indicador)[["municipio", indicador]].reset_index(drop=True)
        top5.index = top5.index + 1
        st.dataframe(top5, use_container_width=True)

    with col2:
        st.subheader("Top 5 — Menores valores")
        bot5 = df_idx.nsmallest(5, indicador)[["municipio", indicador]].reset_index(drop=True)
        bot5.index = bot5.index + 1
        st.dataframe(bot5, use_container_width=True)


# =============================================================================
#  PAGINA: MAPA LULC 1985 vs 2023 (raster MapBiomas)
# =============================================================================

elif pagina == "🛰️ Mapa LULC 1985 vs 2023":
    st.title("🛰️ Mapa LULC 1985 vs 2023")
    st.caption(
        "Classificacao MapBiomas Colecao 9 clipada pela RH3. "
        "Imagens pre-renderizadas (resolucao ~30 m, exportadas via Google Earth Engine)."
    )

    bbox_path = Path("output/mapas/bbox.json")
    img_1985 = Path("output/mapas/lulc_1985.png")
    img_2023 = Path("output/mapas/lulc_2023.png")

    if not (bbox_path.exists() and img_1985.exists() and img_2023.exists()):
        st.error(
            "Arquivos de mapa nao encontrados em output/mapas/. "
            "Execute `python gerar_mapas_lulc.py` para gera-los (requer auth GEE)."
        )
    else:
        bbox = json.loads(bbox_path.read_text())
        bounds_folium = [[bbox["south"], bbox["west"]], [bbox["north"], bbox["east"]]]
        center_lat = (bbox["south"] + bbox["north"]) / 2
        center_lon = (bbox["west"] + bbox["east"]) / 2

        # Legenda HTML compacta com as classes mais relevantes da bacia
        LEGENDA_CLASSES = [
            ("Floresta", "#1f8d49"),
            ("Veg. Nao Florestal", "#d6bc74"),
            ("Silvicultura", "#7a5900"),
            ("Pastagem", "#edde8e"),
            ("Agricultura", "#e974ed"),
            ("Mosaico Agropecuario", "#ffefc3"),
            ("Area Urbana", "#d4271e"),
            ("Mineracao", "#9c0027"),
            ("Agua", "#0000ff"),
        ]
        itens_legenda = "".join(
            f"<div style='display:flex;align-items:center;margin:2px 0'>"
            f"<span style='display:inline-block;width:14px;height:14px;background:{c};margin-right:6px;border:1px solid #555'></span>"
            f"<span style='font-size:12px'>{n}</span></div>"
            for n, c in LEGENDA_CLASSES
        )
        legenda_html = (
            "<div style='background:rgba(255,255,255,0.92);padding:8px;border:1px solid #999;border-radius:4px'>"
            f"<b style='font-size:12px'>Classes MapBiomas</b>{itens_legenda}</div>"
        )

        modo = st.radio(
            "Visualizacao:",
            ["Comparar (1985 + 2023)", "Slider — alternar ano"],
            horizontal=True,
        )

        # Limite RH3 em GeoJSON (overlay vetorial) — uniao das geometrias municipais clipadas
        rh3_limite_geojson = gdf.geometry.union_all().__geo_interface__

        def _criar_mapa_lulc(ano):
            png_path = img_1985 if ano == 1985 else img_2023
            m = folium.Map(
                location=[center_lat, center_lon],
                zoom_start=9,
                tiles="cartodbpositron",
                control_scale=True,
            )
            folium.raster_layers.ImageOverlay(
                name=f"MapBiomas {ano}",
                image=str(png_path),
                bounds=bounds_folium,
                opacity=0.85,
                interactive=False,
                cross_origin=False,
                zindex=1,
            ).add_to(m)
            folium.GeoJson(
                rh3_limite_geojson,
                name="Limite RH3",
                style_function=lambda x: {
                    "fillOpacity": 0,
                    "color": "#222",
                    "weight": 2,
                },
            ).add_to(m)
            folium.LayerControl(collapsed=True).add_to(m)
            return m

        if modo == "Comparar (1985 + 2023)":
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**1985**")
                st_folium(_criar_mapa_lulc(1985), height=520, width=None,
                          returned_objects=[], key="mapa_lulc_rk_1985")
            with col2:
                st.markdown("**2023**")
                st_folium(_criar_mapa_lulc(2023), height=520, width=None,
                          returned_objects=[], key="mapa_lulc_rk_2023")
            st.markdown(legenda_html, unsafe_allow_html=True)
        else:
            ano_sel = st.select_slider("Ano:", options=bbox["anos"], value=bbox["anos"][-1])
            map_col, leg_col = st.columns([4, 1])
            with map_col:
                st_folium(_criar_mapa_lulc(ano_sel), height=600, width=None,
                          returned_objects=[], key=f"mapa_lulc_rk_slider_{ano_sel}")
            with leg_col:
                st.markdown(legenda_html, unsafe_allow_html=True)

        st.info(
            "**Interpretacao:** observe a expansao das areas urbanas (vermelho), a alternancia "
            "entre pastagem (amarelo claro) e floresta (verde escuro) ao longo dos vales, "
            "e a recuperacao florestal nas encostas mais acidentadas das porcoes nordeste e leste da bacia."
        )


# =============================================================================
#  PAGINA 3: EVOLUCAO TEMPORAL
# =============================================================================

elif pagina == "📊 Evolucao Temporal":
    st.title("📊 Evolucao Temporal do Uso e Cobertura do Solo")

    tab1, tab2, tab3 = st.tabs(["RH3 Completa", "Por Municipio", "Comparativo"])

    # --- Tab 1: RH3 completa ---
    with tab1:
        st.subheader("Evolucao por classe — RH3 inteira")

        df_rh3 = df_lulc.groupby(["ano", "classe"])["area_ha"].sum().reset_index()

        # Linha: evolucao de cada classe
        fig = px.area(
            df_rh3, x="ano", y="area_ha", color="classe",
            color_discrete_map=CORES_CLASSES,
            labels={"area_ha": "Area (ha)", "ano": "Ano", "classe": "Classe"},
            title="Evolucao do Uso e Cobertura do Solo — RH3",
        )
        fig.update_layout(height=500, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)

        # Floresta isolada
        df_flor = df_rh3[df_rh3["classe"] == "Floresta"]
        fig2 = px.line(
            df_flor, x="ano", y="area_ha",
            markers=True,
            labels={"area_ha": "Area Florestal (ha)", "ano": "Ano"},
            title="Evolucao da Cobertura Florestal — RH3",
        )
        fig2.update_traces(line=dict(color="#1f8d49", width=3), marker=dict(size=10))
        fig2.update_layout(height=400)
        st.plotly_chart(fig2, use_container_width=True)

    # --- Tab 2: Por municipio ---
    with tab2:
        mun_sel = st.selectbox("Selecione o municipio:", municipios_lista, key="evo_mun")
        df_mun = df_lulc[df_lulc["municipio"] == mun_sel]

        fig = px.area(
            df_mun, x="ano", y="area_ha", color="classe",
            color_discrete_map=CORES_CLASSES,
            labels={"area_ha": "Area (ha)", "ano": "Ano", "classe": "Classe"},
            title=f"Evolucao LULC — {mun_sel}",
        )
        fig.update_layout(height=500, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)

        # Composicao percentual
        df_piv = df_mun.pivot_table(index="ano", columns="classe", values="area_ha", fill_value=0)
        df_pct = df_piv.div(df_piv.sum(axis=1), axis=0) * 100

        fig2 = go.Figure()
        for classe in CORES_CLASSES:
            if classe in df_pct.columns:
                fig2.add_trace(go.Bar(
                    x=df_pct.index, y=df_pct[classe],
                    name=NOMES_CLASSES.get(classe, classe),
                    marker_color=CORES_CLASSES[classe],
                ))
        fig2.update_layout(
            barmode="stack",
            title=f"Composicao Percentual — {mun_sel}",
            yaxis_title="Cobertura (%)",
            xaxis_title="Ano",
            height=450,
            legend=dict(orientation="h", y=-0.2),
        )
        st.plotly_chart(fig2, use_container_width=True)

    # --- Tab 3: Comparativo ---
    with tab3:
        munic_comp = st.multiselect("Selecione municipios para comparar:",
                                    municipios_lista, default=municipios_lista[:3])
        if munic_comp:
            classe_comp = st.selectbox("Classe:", list(CORES_CLASSES.keys()),
                                       format_func=lambda x: NOMES_CLASSES.get(x, x))
            df_comp = df_lulc[(df_lulc["municipio"].isin(munic_comp)) & (df_lulc["classe"] == classe_comp)]

            fig = px.line(
                df_comp, x="ano", y="area_ha", color="municipio",
                markers=True,
                labels={"area_ha": "Area (ha)", "ano": "Ano"},
                title=f"Comparativo — {NOMES_CLASSES.get(classe_comp, classe_comp)}",
            )
            fig.update_layout(height=450)
            st.plotly_chart(fig, use_container_width=True)


# =============================================================================
#  PAGINA 4: TRANSICOES
# =============================================================================

elif pagina == "🔄 Transicoes":
    st.title("🔄 Analise de Transicoes de Uso do Solo")

    periodos_disp = sorted(df_trans["periodo"].unique())
    periodo_sel = st.selectbox("Periodo:", periodos_disp, index=len(periodos_disp) - 1)

    df_per = df_trans[df_trans["periodo"] == periodo_sel]

    tab1, tab2 = st.tabs(["Visao Geral RH3", "Por Municipio"])

    with tab1:
        # Soma total por transicao
        df_soma = df_per.groupby("transicao")["area_ha"].sum().sort_values(ascending=True).reset_index()

        cores_trans = []
        for t in df_soma["transicao"]:
            if "para_Floresta" in t or "para_VegNativa" in t:
                cores_trans.append("#1f8d49")
            elif "para_Pastagem" in t or "para_Antropico" in t or "para_Urbano" in t:
                cores_trans.append("#d4271e")
            elif "para_Agricultura" in t:
                cores_trans.append("#e974ed")
            else:
                cores_trans.append("#888888")

        fig = go.Figure(go.Bar(
            y=df_soma["transicao"],
            x=df_soma["area_ha"],
            orientation="h",
            marker_color=cores_trans,
            text=[f"{fmt_br(v)} ha" for v in df_soma["area_ha"]],
            textposition="outside",
        ))
        fig.update_layout(
            title=f"Transicoes de Uso do Solo — RH3 ({periodo_sel})",
            xaxis_title="Area (ha)",
            height=max(400, len(df_soma) * 40),
            margin=dict(l=250, r=80, t=50, b=40),
            yaxis=dict(title=""),
        )
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        trans_sel = st.selectbox("Transicao:", sorted(df_per["transicao"].unique()))
        df_t_mun = df_per[df_per["transicao"] == trans_sel].sort_values("area_ha", ascending=True)

        fig = go.Figure(go.Bar(
            y=df_t_mun["municipio"],
            x=df_t_mun["area_ha"],
            orientation="h",
            marker_color="#1f8d49" if "para_Floresta" in trans_sel or "para_VegNativa" in trans_sel else "#d4271e",
            text=[f"{fmt_br(v)} ha" for v in df_t_mun["area_ha"]],
            textposition="outside",
        ))
        fig.update_layout(
            title=f"{trans_sel} — por municipio ({periodo_sel})",
            xaxis_title="Area (ha)",
            height=max(400, len(df_t_mun) * 30),
            margin=dict(l=220, r=80, t=50, b=40),
            yaxis=dict(title=""),
        )
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
#  PAGINA 5: PERFIL MUNICIPAL
# =============================================================================

elif pagina == "🏙️ Perfil Municipal":
    st.title("🏙️ Perfil Municipal Detalhado")

    seletor_col1, seletor_col2 = st.columns([3, 2])
    with seletor_col1:
        mun_sel = st.selectbox("Municipio:", municipios_lista, key="perfil_mun")
    with seletor_col2:
        comparar = st.checkbox("Comparar com outro municipio", value=False)

    if comparar:
        mun_b_opcoes = [m for m in municipios_lista if m != mun_sel]
        mun_b = st.selectbox("Municipio para comparacao:", mun_b_opcoes, key="perfil_mun_b")
    else:
        mun_b = None

    row = df_idx[df_idx["municipio"] == mun_sel].iloc[0]
    row_score = df_scores[df_scores["municipio"] == mun_sel].iloc[0]
    rank_geral = df_scores.sort_values("score_ambiental", ascending=False).reset_index(drop=True)
    posicao = rank_geral[rank_geral["municipio"] == mun_sel].index[0] + 1
    if mun_b:
        row_b = df_idx[df_idx["municipio"] == mun_b].iloc[0]
        row_score_b = df_scores[df_scores["municipio"] == mun_b].iloc[0]
        posicao_b = rank_geral[rank_geral["municipio"] == mun_b].index[0] + 1

    # KPIs do municipio principal
    st.markdown(f"**{mun_sel}**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Posicao no Ranking", f"{posicao}o / {len(df_idx)}")
    col2.metric("Score Ambiental", fmt_br(row_score["score_ambiental"], 1))
    col3.metric("ICV 2023", f"{fmt_br(row['ICV_2023_pct'], 1)}%")
    col4.metric("Area na RH3", f"{fmt_br(row['area_total_na_rh3_ha'])} ha")

    if mun_b:
        st.markdown(f"**{mun_b}**")
        col1b, col2b, col3b, col4b = st.columns(4)
        col1b.metric("Posicao no Ranking", f"{posicao_b}o / {len(df_idx)}")
        col2b.metric("Score Ambiental", fmt_br(row_score_b["score_ambiental"], 1))
        col3b.metric("ICV 2023", f"{fmt_br(row_b['ICV_2023_pct'], 1)}%")
        col4b.metric("Area na RH3", f"{fmt_br(row_b['area_total_na_rh3_ha'])} ha")

    st.divider()

    col_left, col_right = st.columns(2)

    # Radar
    with col_left:
        st.subheader("Radar de Desempenho (0-100)")
        st.caption("10 eixos = 10 indicadores do Score Composto. Ordem segue a sequencia dos blocos tematicos.")

        cols_score = [d[0] for d in SCORE_DEF]
        categorias = [d[3].replace(" ", "<br>") for d in SCORE_DEF]
        valores_a = [row_score[c] for c in cols_score]
        categorias_r = categorias + [categorias[0]]
        valores_a_r = valores_a + [valores_a[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=valores_a_r, theta=categorias_r, fill="toself",
            fillcolor="rgba(31, 141, 73, 0.3)",
            line=dict(color="#1f8d49", width=2), name=mun_sel,
        ))
        if mun_b:
            valores_b = [row_score_b[c] for c in cols_score]
            valores_b_r = valores_b + [valores_b[0]]
            fig.add_trace(go.Scatterpolar(
                r=valores_b_r, theta=categorias_r, fill="toself",
                fillcolor="rgba(228, 116, 237, 0.25)",
                line=dict(color="#a020f0", width=2), name=mun_b,
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100]),
                       angularaxis=dict(tickfont=dict(size=9))),
            height=480, margin=dict(l=80, r=80, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig, use_container_width=True)

    # Pizza
    with col_right:
        st.subheader("Uso do Solo 2023")
        if mun_b:
            from plotly.subplots import make_subplots
            df_a = df_lulc[(df_lulc["municipio"] == mun_sel) & (df_lulc["ano"] == 2023)]
            df_a = df_a[df_a["area_ha"] > 0].copy()
            df_a["label"] = df_a["classe"].map(NOMES_CLASSES)
            df_b = df_lulc[(df_lulc["municipio"] == mun_b) & (df_lulc["ano"] == 2023)]
            df_b = df_b[df_b["area_ha"] > 0].copy()
            df_b["label"] = df_b["classe"].map(NOMES_CLASSES)

            fig = make_subplots(rows=1, cols=2,
                                specs=[[{"type": "domain"}, {"type": "domain"}]],
                                subplot_titles=[mun_sel, mun_b])
            fig.add_trace(go.Pie(
                labels=df_a["label"], values=df_a["area_ha"],
                marker=dict(colors=[CORES_CLASSES.get(c, "#888") for c in df_a["classe"]]),
                hole=0.4, textinfo="percent",
            ), 1, 1)
            fig.add_trace(go.Pie(
                labels=df_b["label"], values=df_b["area_ha"],
                marker=dict(colors=[CORES_CLASSES.get(c, "#888") for c in df_b["classe"]]),
                hole=0.4, textinfo="percent",
            ), 1, 2)
            fig.update_layout(height=420, showlegend=False, margin=dict(l=20, r=20, t=40, b=20))
            st.plotly_chart(fig, use_container_width=True)
        else:
            df_mun_2023 = df_lulc[(df_lulc["municipio"] == mun_sel) & (df_lulc["ano"] == 2023)]
            df_mun_2023 = df_mun_2023[df_mun_2023["area_ha"] > 0].copy()
            df_mun_2023["label"] = df_mun_2023["classe"].map(NOMES_CLASSES)
            fig = px.pie(df_mun_2023, values="area_ha", names="label",
                         color="classe", color_discrete_map=CORES_CLASSES, hole=0.4)
            fig.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
            fig.update_layout(height=420, showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # Indicadores detalhados
    st.subheader("Indicadores Detalhados")

    if mun_b:
        indicadores_comp = [
            ("Cobertura Vegetal Nativa 2023 (%)", "ICV_2023_pct", 1, False),
            ("Persistencia Florestal 1985-2023 (%)", "persistencia_florestal_pct", 1, False),
            ("Estabilidade do Uso 1985-2023 (%)", "estabilidade_uso_pct", 1, False),
            ("Variacao Veg. Nativa 1985-2023 (ha)", "variacao_veg_ha", 0, True),
            ("Variacao Veg. Nativa 1985-2023 (%)", "variacao_veg_pct", 1, True),
            ("Recuperacao Florestal 2010-2023 (ha)", "recup_florestal_2010_2023_ha", 0, True),
            ("Taxa Recuperacao (ha/ano)", "taxa_recup_florestal_ha_ano", 1, True),
            ("Pasto -> Mata recente (ha)", "pasto_para_mata_recente_ha", 0, False),
            ("Mata -> Pasto total (ha)", "mata_para_pasto_total_ha", 0, False),
            ("Saldo Florestal 1985-2023 (ha)", "saldo_florestal_total_ha", 0, True),
            ("Pressao Antropica 2023 (%)", "pressao_antropica_2023_pct", 1, False),
            ("Variacao Pressao 1985-2023 (pp)", "variacao_pressao_antropica_pp", 1, True),
            ("Crescimento Urbano (ha)", "cresc_urbano_ha", 0, True),
            ("Desmatamento Recente 2020-23 (ha)", "desmatamento_recente_ha", 0, False),
            ("Maior Fragmento Florestal (ha)", "maior_fragmento_florestal_ha", 0, False),
            ("Num. de Fragmentos Florestais", "num_fragmentos_florestais", 0, False),
            ("Densidade de Fragmentos (n/1000 ha)", "densidade_fragmentos_por_kha", 2, False),
        ]
        rows = []
        for label, col, dec, com_sinal in indicadores_comp:
            rows.append({
                "Indicador": label,
                mun_sel: fmt_br(row[col], dec, sinal=com_sinal),
                mun_b: fmt_br(row_b[col], dec, sinal=com_sinal),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=420)
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.markdown("**Cobertura e Estabilidade**")
            st.metric("Cobertura Veg. Nativa 2023", f"{fmt_br(row['ICV_2023_pct'], 1)}%")
            st.metric("Persistencia Florestal", f"{fmt_br(row['persistencia_florestal_pct'], 1)}%",
                      help="% que foi floresta em todos os 9 anos-marco entre 1985 e 2023")
            st.metric("Estabilidade do Uso", f"{fmt_br(row['estabilidade_uso_pct'], 1)}%",
                      help="% com a mesma classe LULC em 1985 e 2023")
        with col2:
            st.markdown("**Dinamica Positiva**")
            delta_veg = row["variacao_veg_ha"]
            st.metric("Saldo Liquido 1985-2023", f"{fmt_br(delta_veg, sinal=True)} ha",
                      delta=f"{fmt_br(row['variacao_veg_pct'], 1, sinal=True)}%",
                      delta_color="normal" if delta_veg >= 0 else "inverse")
            st.metric("Recuperacao 2010-2023", f"{fmt_br(row['recup_florestal_2010_2023_ha'], sinal=True)} ha")
            st.metric("Pasto -> Mata recente", f"{fmt_br(row['pasto_para_mata_recente_ha'])} ha")
        with col3:
            st.markdown("**Dinamica Negativa**")
            st.metric("Pressao Antropica 2023", f"{fmt_br(row['pressao_antropica_2023_pct'], 1)}%")
            st.metric("Var. Pressao (1985-2023)", f"{fmt_br(row['variacao_pressao_antropica_pp'], 1, sinal=True)} pp")
            st.metric("Desmatamento Recente", f"{fmt_br(row['desmatamento_recente_ha'])} ha")
        with col4:
            st.markdown("**Estrutura da Paisagem**")
            st.metric("Maior Fragmento Florestal", f"{fmt_br(row['maior_fragmento_florestal_ha'])} ha")
            st.metric("Num. de Fragmentos", f"{fmt_br(row['num_fragmentos_florestais'])}")
            st.metric("Densidade de Fragmentos", f"{fmt_br(row['densidade_fragmentos_por_kha'], 2)}/kha",
                      help="Numero de patches por 1000 ha — quanto MENOR, mais agregada a paisagem")

    # Evolucao temporal
    if mun_b:
        st.subheader(f"Evolucao da Cobertura Vegetal Nativa — {mun_sel} vs {mun_b}")
        df_a_t = df_lulc[df_lulc["municipio"].isin([mun_sel, mun_b])].copy()
        veg_classes = ["Floresta", "Vegetacao_Natural_Nao_Florestal"]
        df_a_t["is_veg"] = df_a_t["classe"].isin(veg_classes)
        total_ano = df_a_t.groupby(["municipio", "ano"])["area_ha"].sum().reset_index()
        veg_ano = df_a_t[df_a_t["is_veg"]].groupby(["municipio", "ano"])["area_ha"].sum().reset_index()
        veg_ano = veg_ano.merge(total_ano, on=["municipio", "ano"], suffixes=("_veg", "_tot"))
        veg_ano["icv_pct"] = veg_ano["area_ha_veg"] / veg_ano["area_ha_tot"] * 100

        fig_evo = px.line(
            veg_ano, x="ano", y="icv_pct", color="municipio",
            markers=True,
            labels={"icv_pct": "Cobertura Vegetal Nativa (%)", "ano": "Ano", "municipio": ""},
            color_discrete_map={mun_sel: "#1f8d49", mun_b: "#a020f0"},
        )
        fig_evo.update_layout(height=380, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_evo, use_container_width=True)
    else:
        st.subheader(f"Evolucao Temporal — {mun_sel}")
        df_mun_all = df_lulc[df_lulc["municipio"] == mun_sel]
        fig = px.area(df_mun_all, x="ano", y="area_ha", color="classe",
                      color_discrete_map=CORES_CLASSES,
                      labels={"area_ha": "Area (ha)", "ano": "Ano", "classe": "Classe"})
        fig.update_layout(height=400, legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig, use_container_width=True)


# =============================================================================
#  PAGINA 6: METODOLOGIA
# =============================================================================

elif pagina == "📐 Metodologia":
    st.title("📐 Metodologia e Parametros de Avaliacao")

    st.markdown("""
---
## 1. Fonte dos Dados

| Item | Descricao |
|------|-----------|
| **Uso e cobertura do solo** | MapBiomas Colecao 9 — classificacao anual pixel-a-pixel (30 m, Landsat) |
| **Periodo de analise** | 1985 a 2023 (anos-marco: 1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2023) |
| **Limites municipais** | IBGE — malha municipal |
| **Limite da RH3** | Shapefile oficial da Regiao Hidrografica III — Medio Paraiba do Sul |
| **Processamento** | Google Earth Engine (reduceRegions, escala 30 m) |

---

## 2. Regra de Recorte Territorial

O limite mandatorio e o da **RH3**, nao o do municipio.
Municipios parcialmente inseridos tiveram sua geometria **recortada (clipped)** pelo limite da RH3.
Toda a analise considera apenas a **porcao do municipio dentro da RH3**.

---

## 3. Classes de Uso e Cobertura do Solo (MapBiomas)
""")

    classes_df = pd.DataFrame([
        {"Classe Agrupada": "Floresta", "Codigos MapBiomas": "3, 4, 5, 6, 49",
         "Descricao": "Formacao Florestal, Savanica, Mangue, Floresta Alagada, Restinga Arborea"},
        {"Classe Agrupada": "Veg. Natural Nao Florestal", "Codigos MapBiomas": "10, 11, 12, 13, 32, 50",
         "Descricao": "Campo, Area Umida, Apicum, Restinga Herbacea, etc."},
        {"Classe Agrupada": "Silvicultura", "Codigos MapBiomas": "9",
         "Descricao": "Floresta Plantada (eucalipto, pinus)"},
        {"Classe Agrupada": "Pastagem", "Codigos MapBiomas": "15",
         "Descricao": "Pastagem natural e plantada"},
        {"Classe Agrupada": "Agricultura", "Codigos MapBiomas": "18, 19, 20, 35, 36, 39, 40, 41, 46, 47, 48",
         "Descricao": "Todas as culturas agricolas (soja, cana, cafe, citrus, etc.)"},
        {"Classe Agrupada": "Mosaico Agropecuario", "Codigos MapBiomas": "21",
         "Descricao": "Mosaico de agricultura e pastagem"},
        {"Classe Agrupada": "Area Urbana", "Codigos MapBiomas": "24",
         "Descricao": "Infraestrutura urbana"},
        {"Classe Agrupada": "Mineracao", "Codigos MapBiomas": "30",
         "Descricao": "Areas de mineracao"},
        {"Classe Agrupada": "Agua", "Codigos MapBiomas": "26, 33",
         "Descricao": "Corpos d'agua (rios, lagos, reservatorios)"},
        {"Classe Agrupada": "Area Nao Vegetada", "Codigos MapBiomas": "22, 23, 25, 29",
         "Descricao": "Praia, dunas, afloramentos rochosos, outros"},
    ])
    st.dataframe(classes_df, use_container_width=True, hide_index=True)

    st.markdown("""
### 3.1 Precisao e Limitacoes do MapBiomas

O MapBiomas Colecao 9 e o produto mais robusto disponivel publicamente para LULC no Brasil
(classificacao validada com acuracias globais de ~88-90% em Mata Atlantica), mas tem **limitacoes
conhecidas que e importante registrar** antes de qualquer leitura competitiva:

| Limitacao | O que significa para a RH3 |
|-----------|-----------------------------|
| **Resolucao espacial de 30 m** | Pixels com area de 0,09 ha — feicoes menores que isso (capoeiras pequenas, manchas de mata em quintais, faixas estreitas de mata ciliar) podem nao ser detectadas. |
| **Confusao eucalipto vs floresta nativa** | A classificacao tem dificuldade em separar plantio de eucalipto adulto da floresta nativa, **especialmente no RJ**, onde a base de amostras de treinamento e menor do que no 'cinturao silvicola' (MG/ES/BA/SP). Eucalipto maduro tende a aparecer como classe 'floresta'; eucalipto recem-cortado, como pastagem. **Implicacao:** municipios com presenca historica de eucalipto (CSN — Volta Redonda, Barra Mansa, Pinheiral) podem ter cobertura nativa **ligeiramente inflada**. |
| **Sazonalidade da agua** | Areas inundaveis e reservatorios podem mudar de classe entre anos secos e umidos, gerando variacao aparente nao-real. |
| **Mapeamento de classes raras** | Mineracao, aquicultura e algumas culturas especificas tem acuracia menor em areas pequenas. |
| **Periodos de transicao** | Pixels mudando de classe entre anos podem refletir tanto mudanca real quanto **reclassificacao** do algoritmo. |

**Como mitigamos essas limitacoes na analise da RH3:**
- O viez do eucalipto se aplica a **todos** os municipios da bacia — entao a **posicao relativa**
  no ranking permanece informativa, mesmo que os valores absolutos de cobertura tenham sobreposicao.
- Indicadores de **dinamica** (recuperacao, regeneracao, desmatamento) sao mais robustos a esse viez
  porque medem mudanca, nao estoque.
- Indicadores de **estrutura da paisagem** (maior fragmento, densidade de fragmentos) sao calculados
  sobre a mascara binaria de floresta, herdando o mesmo viez, mas continuam comparaveis entre municipios.
- O **score composto** combina 10 indicadores de naturezas diferentes, reduzindo o impacto de qualquer
  viez isolado.

**Para checagem detalhada de acuracia por bioma e classe**, consultar
[mapbiomas.org/colecao-9/acuracia](https://mapbiomas.org/) e a documentacao tecnica da Colecao 9.

---

## 4. Indicadores Calculados (18 indices)

Os indicadores marcados como **Score v2** entram no calculo do Score Ambiental Composto. Os
indicadores **Diagnostico** sao calculados mas servem como contexto / categorias extras.
""")

    indices_df = pd.DataFrame([
        {"#": 1, "Indice": "ICV 2023", "Descricao": "% de cobertura vegetal nativa (floresta + veg. nao florestal) em 2023",
         "Unidade": "%", "Categoria": "Score v2 (15%)"},
        {"#": 2, "Indice": "Persistencia Florestal", "Descricao": "% que foi floresta em TODOS os 9 anos-marco (1985-2023)",
         "Unidade": "ha / %", "Categoria": "Score v2 (8%)"},
        {"#": 3, "Indice": "Estabilidade do Uso", "Descricao": "% com a MESMA classe LULC em 1985 e 2023",
         "Unidade": "ha / %", "Categoria": "Score v2 (7%)"},
        {"#": 4, "Indice": "Recuperacao Florestal", "Descricao": "Aumento de area florestal entre 2010 e 2023",
         "Unidade": "ha / ha/ano", "Categoria": "Score v2 (12%)"},
        {"#": 5, "Indice": "Pasto -> Mata", "Descricao": "Area de pastagem convertida em floresta (regeneracao, 2010-2020)",
         "Unidade": "ha", "Categoria": "Score v2 (8%)"},
        {"#": 6, "Indice": "Saldo Liquido Veg. Nativa", "Descricao": "Variacao absoluta da vegetacao nativa (1985-2023)",
         "Unidade": "ha / %", "Categoria": "Score v2 (5%)"},
        {"#": 7, "Indice": "Desmatamento Recente", "Descricao": "Vegetacao nativa convertida em uso antropico (2020-2023)",
         "Unidade": "ha / ha/ano", "Categoria": "Score v2 (12%, inv.)"},
        {"#": 8, "Indice": "Pressao Antropica", "Descricao": "% da area com uso antropico e sua variacao temporal",
         "Unidade": "% / pp", "Categoria": "Score v2 (13%, inv.)"},
        {"#": 9, "Indice": "Maior Fragmento Florestal", "Descricao": "Tamanho do maior remanescente continuo de floresta (2023)",
         "Unidade": "ha", "Categoria": "Score v2 (12%)"},
        {"#": 10, "Indice": "Densidade de Fragmentos", "Descricao": "Numero de patches florestais por 1000 ha (2023)",
         "Unidade": "n/kha", "Categoria": "Score v2 (8%, inv.)"},
        {"#": 11, "Indice": "Mata -> Pasto", "Descricao": "Area de floresta convertida em pastagem (desmatamento total)",
         "Unidade": "ha", "Categoria": "Diagnostico"},
        {"#": 12, "Indice": "Saldo Florestal por Transicoes", "Descricao": "Pasto->Mata menos Mata->Pasto (1985-2023)",
         "Unidade": "ha", "Categoria": "Diagnostico"},
        {"#": 13, "Indice": "Crescimento Urbano", "Descricao": "Expansao da area urbana entre 1985 e 2023",
         "Unidade": "ha / %", "Categoria": "Diagnostico"},
        {"#": 14, "Indice": "Shannon", "Descricao": "Indice de diversidade de uso do solo (entropia de Shannon)",
         "Unidade": "adimensional", "Categoria": "Diagnostico"},
        {"#": 15, "Indice": "Eficiencia de Regeneracao", "Descricao": "Razao entre area regenerada e area desmatada (1985-2023)",
         "Unidade": "adimensional", "Categoria": "Diagnostico"},
        {"#": 16, "Indice": "Saldo Veg. Nativa <-> Antropico", "Descricao": "Conversao liquida entre vegetacao nativa e uso antropico",
         "Unidade": "ha", "Categoria": "Diagnostico"},
        {"#": 17, "Indice": "Variacao Agropecuaria", "Descricao": "Mudanca na area agropecuaria (pastagem + agricultura + mosaico)",
         "Unidade": "ha / %", "Categoria": "Diagnostico"},
        {"#": 18, "Indice": "Variacao Agua", "Descricao": "Mudanca em corpos d'agua entre 1985 e 2023",
         "Unidade": "ha", "Categoria": "Diagnostico"},
    ])
    st.dataframe(indices_df, use_container_width=True, hide_index=True)

    st.markdown("""
### 4.1 Indicadores de Estrutura da Paisagem (Fragmentacao)

Os indicadores **Maior Fragmento Florestal** e **Densidade de Fragmentos** sao calculados por uma
abordagem diferente dos demais — analise de componentes conexos sobre o raster:

1. **Download:** mascara binaria de floresta de 2023 e baixada via Google Earth Engine como GeoTIFF
   (resolucao 30 m, projecao SIRGAS 2000 UTM 23S, clipada pela geometria municipal).
2. **Rotulagem:** aplica-se `scipy.ndimage.label` com **8-conectividade** (pixels diagonais contam),
   que identifica e numera cada componente conexo (cada 'fragmento' = grupo de pixels-floresta vizinhos).
3. **Metricas:**
   - **Maior fragmento (ha):** area do maior grupo encontrado.
   - **Numero de fragmentos:** quantidade total de grupos.
   - **Densidade (n/1000 ha):** numero de fragmentos dividido pela area do municipio.

**Limitacao:** a deteccao de componentes e sensivel a resolucao — fragmentos separados por estradas
estreitas (<30 m) podem aparecer como um unico fragmento. Para a escala da RH3 e o nivel comparativo
desejado, isso e aceitavel.
""")

    st.markdown("""
---

## 5. Score Ambiental Composto v2 (10 indicadores)

O ranking geral combina **10 indicadores** organizados em **4 blocos tematicos**, normalizados (0-100)
e ponderados conforme sua relevancia para a conservacao ambiental na bacia.
""")

    score_df = pd.DataFrame([
        {"Bloco": "Cobertura e Estabilidade", "Componente": "1. Cobertura Vegetal Nativa (ICV 2023)", "Peso": "15%",
         "Logica": "Maior cobertura = maior score"},
        {"Bloco": "Cobertura e Estabilidade", "Componente": "2. Persistencia Florestal 1985-2023", "Peso": "8%",
         "Logica": "Maior area que foi floresta em TODOS os 9 anos = maior score"},
        {"Bloco": "Cobertura e Estabilidade", "Componente": "3. Estabilidade do Uso 1985 vs 2023", "Peso": "7%",
         "Logica": "Maior area com a mesma classe LULC nos extremos = maior score"},
        {"Bloco": "Dinamica Positiva", "Componente": "4. Recuperacao Florestal 2010-2023", "Peso": "12%",
         "Logica": "Maior ganho de floresta = maior score"},
        {"Bloco": "Dinamica Positiva", "Componente": "5. Regeneracao Pasto -> Mata 2010-2020", "Peso": "8%",
         "Logica": "Maior conversao de pasto em mata = maior score"},
        {"Bloco": "Dinamica Positiva", "Componente": "6. Saldo Liquido de Veg. Nativa 1985-2023", "Peso": "5%",
         "Logica": "Maior variacao absoluta positiva em 38 anos = maior score"},
        {"Bloco": "Dinamica Negativa", "Componente": "7. Desmatamento Recente 2020-2023", "Peso": "12%",
         "Logica": "INVERTIDO — menos desmatamento = maior score"},
        {"Bloco": "Dinamica Negativa", "Componente": "8. Variacao Pressao Antropica 1985-2023", "Peso": "13%",
         "Logica": "INVERTIDO — menor aumento de pressao = maior score"},
        {"Bloco": "Estrutura da Paisagem", "Componente": "9. Maior Fragmento Florestal 2023", "Peso": "12%",
         "Logica": "Maior remanescente continuo = maior score"},
        {"Bloco": "Estrutura da Paisagem", "Componente": "10. Densidade de Fragmentos Florestais 2023", "Peso": "8%",
         "Logica": "INVERTIDO — menos fragmentacao = maior score"},
    ])
    st.dataframe(score_df, use_container_width=True, hide_index=True)

    st.markdown("""
### Dois Indicadores Novos Calculados Via Analise de Paisagem

- **Persistencia Florestal:** sobreposicao das mascaras de floresta de 1985, 1990, 1995, 2000, 2005,
  2010, 2015, 2020 e 2023. Pixel persistente = foi floresta em TODOS os anos. Captura conservacao
  estavel (nao apenas recuperacao recente).
- **Maior Fragmento e Densidade de Fragmentos:** analise de componentes conexos (`scipy.ndimage.label`,
  8-conectividade) sobre a mascara binaria de floresta 2023, com resolucao de 30 m. O maior fragmento
  e o maior remanescente continuo do municipio; a densidade e o numero de patches por 1000 ha.

### Normalizacao

Cada indicador e normalizado pelo metodo **Min-Max** entre os 19 municipios da RH3:

```
Score = (valor - minimo) / (maximo - minimo) x 100
```

Para indicadores **invertidos** (Desmatamento, Pressao e Densidade de Fragmentos), aplica-se:

```
Score = 100 - Score_normalizado
```

### Formula Final

```
Score Ambiental = 0.15 x Cobertura  + 0.08 x Persistencia + 0.07 x Estabilidade
                + 0.12 x Recuperacao + 0.08 x Regeneracao  + 0.05 x SaldoLongo
                + 0.12 x Desmat.(inv) + 0.13 x Pressao(inv)
                + 0.12 x MaiorFragmento + 0.08 x DensidadeFrag(inv)
```

---

## 6. Transicoes Analisadas
""")

    trans_df = pd.DataFrame([
        {"Transicao": "Floresta -> Pastagem", "Significado": "Desmatamento para pecuaria"},
        {"Transicao": "Pastagem -> Floresta", "Significado": "Regeneracao florestal em areas de pasto"},
        {"Transicao": "Floresta -> Agricultura", "Significado": "Desmatamento para cultivos"},
        {"Transicao": "Floresta -> Urbano", "Significado": "Urbanizacao sobre areas florestais"},
        {"Transicao": "Pastagem -> Urbano", "Significado": "Urbanizacao sobre pastagens"},
        {"Transicao": "Agricultura -> Urbano", "Significado": "Urbanizacao sobre areas agricolas"},
        {"Transicao": "Veg. Nativa -> Antropico", "Significado": "Conversao total de vegetacao nativa"},
        {"Transicao": "Antropico -> Veg. Nativa", "Significado": "Recuperacao/regeneracao total"},
        {"Transicao": "Pastagem -> Agricultura", "Significado": "Intensificacao de uso agropecuario"},
        {"Transicao": "Silvicultura -> Floresta", "Significado": "Conversao de plantio florestal em mata nativa"},
        {"Transicao": "Floresta -> Silvicultura", "Significado": "Substituicao de mata nativa por plantio"},
    ])
    st.dataframe(trans_df, use_container_width=True, hide_index=True)

    st.markdown("""
### Periodos de Analise de Transicao

| Periodo | Descricao |
|---------|-----------|
| 1985-2000 | Periodo historico |
| 2000-2010 | Decada 2000 |
| 2010-2020 | Decada 2010 |
| 2020-2023 | Periodo recente |
| 1985-2023 | Periodo completo |

---

## 7. Municipios Analisados (19)
""")

    mun_col1, mun_col2 = st.columns(2)
    with mun_col1:
        st.markdown("""
**Totalmente inseridos na RH3:**
- Barra Mansa
- Comendador Levy Gasparian
- Itatiaia
- Pinheiral
- Porto Real
- Quatis
- Resende
- Rio das Flores
- Valenca
- Volta Redonda
""")
    with mun_col2:
        st.markdown("""
**Parcialmente inseridos (recortados pela RH3):**
- Barra do Pirai
- Mendes
- Miguel Pereira
- Paraiba do Sul
- Paty do Alferes
- Pirai
- Rio Claro
- Tres Rios
- Vassouras
""")

    st.markdown("""
---

*Produto do GT SIGA — Comite de Bacias Hidrograficas do Medio Paraiba do Sul (CBH-MPS).*
""")
