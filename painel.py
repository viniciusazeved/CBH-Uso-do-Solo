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
    "recup_florestal_2010_2023_ha": "Recuperacao Florestal 2010-2023 (ha)",
    "saldo_florestal_total_ha": "Saldo Florestal 1985-2023 (ha)",
    "pressao_antropica_2023_pct": "Pressao Antropica 2023 (%)",
    "variacao_veg_pct": "Variacao Veg. Nativa 1985-2023 (%)",
    "desmatamento_recente_ha": "Desmatamento Recente 2020-2023 (ha)",
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


def calcular_scores(df_idx):
    df = df_idx.copy()
    df["score_cobertura"] = _normalizar(df["ICV_2023_pct"])
    df["score_recuperacao"] = _normalizar(df["recup_florestal_2010_2023_ha"])
    df["score_regeneracao"] = _normalizar(df["pasto_para_mata_recente_ha"])
    df["score_saldo"] = _normalizar(df["saldo_florestal_recente_ha"])
    df["score_pressao"] = _normalizar(df["variacao_pressao_antropica_pp"], inverter=True)
    df["score_desmatamento"] = _normalizar(df["desmatamento_recente_ha"], inverter=True)

    pesos = {
        "score_cobertura": 0.20,
        "score_recuperacao": 0.20,
        "score_regeneracao": 0.15,
        "score_saldo": 0.15,
        "score_pressao": 0.15,
        "score_desmatamento": 0.15,
    }
    df["score_ambiental"] = sum(df[col] * peso for col, peso in pesos.items())
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
    ["🏆 Ranking Geral", "🗺️ Mapa Interativo", "📊 Evolucao Temporal",
     "🔄 Transicoes", "🏙️ Perfil Municipal", "📐 Metodologia"],
    index=0,
)

st.sidebar.divider()
st.sidebar.caption("CBH Medio Paraiba do Sul")
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
O **Score Ambiental Composto** e calculado a partir de **6 indicadores**, cada um normalizado de 0 a 100
e ponderado conforme sua relevancia para a conservacao ambiental na bacia:
""")

    param_col1, param_col2 = st.columns(2)
    with param_col1:
        st.markdown("""
| # | Indicador | Peso | O que mede |
|:-:|-----------|:----:|------------|
| 1 | **Cobertura Vegetal Nativa** | 20% | % da area coberta por vegetacao nativa em 2023 |
| 2 | **Recuperacao Florestal** | 20% | Ganho de area florestal entre 2010 e 2023 (ha) |
| 3 | **Regeneracao (Pasto -> Mata)** | 15% | Area de pastagem convertida em floresta (2010-2020) |
""")
    with param_col2:
        st.markdown("""
| # | Indicador | Peso | O que mede |
|:-:|-----------|:----:|------------|
| 4 | **Saldo Florestal** | 15% | Regeneracao menos desmatamento (liquido, 2010-2020) |
| 5 | **Pressao Antropica** | 15% | Variacao da pressao antropica 1985-2023 (invertido) |
| 6 | **Desmatamento Recente** | 15% | Area desmatada 2020-2023 (invertido — menos = melhor) |
""")

    st.info("""
**Normalizacao:** Cada indicador e normalizado pelo metodo Min-Max (0-100) entre os 19 municipios.
Para indicadores negativos (pressao antropica e desmatamento), a escala e invertida: menor valor = maior score.
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

    score_cols = ["score_cobertura", "score_recuperacao", "score_regeneracao",
                  "score_saldo", "score_pressao", "score_desmatamento"]
    score_labels = ["Cobertura Vegetal", "Recuperacao Florestal", "Regeneracao",
                    "Saldo Florestal", "Pressao Antropica", "Desmatamento Recente"]

    fig2 = go.Figure()
    for col, label in zip(score_cols, score_labels):
        fig2.add_trace(go.Bar(
            y=rank["municipio"],
            x=rank[col],
            name=label,
            orientation="h",
            hovertemplate=f"<b>%{{y}}</b><br>{label}: %{{x:.1f}}<extra></extra>",
        ))

    fig2.update_layout(
        barmode="group",
        height=max(600, len(rank) * 40),
        yaxis=dict(autorange="reversed", title=""),
        xaxis=dict(title="Score (0-100)"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        margin=dict(l=200, r=50, t=60, b=40),
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

    mun_sel = st.selectbox("Selecione o municipio:", municipios_lista, key="perfil_mun")
    row = df_idx[df_idx["municipio"] == mun_sel].iloc[0]
    row_score = df_scores[df_scores["municipio"] == mun_sel].iloc[0]

    # Posicao no ranking
    rank_geral = df_scores.sort_values("score_ambiental", ascending=False).reset_index(drop=True)
    posicao = rank_geral[rank_geral["municipio"] == mun_sel].index[0] + 1

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Posicao no Ranking", f"{posicao}o / {len(df_idx)}")
    col2.metric("Score Ambiental", fmt_br(row_score['score_ambiental'], 1))
    col3.metric("ICV 2023", f"{fmt_br(row['ICV_2023_pct'], 1)}%")
    col4.metric("Area na RH3", f"{fmt_br(row['area_total_na_rh3_ha'])} ha")

    st.divider()

    col_left, col_right = st.columns(2)

    with col_left:
        # Radar chart dos scores
        st.subheader("Radar de Desempenho")

        categorias = ["Cobertura\nVegetal", "Recuperacao\nFlorestal", "Regeneracao",
                      "Saldo\nFlorestal", "Pressao\nAntropica", "Desmatamento\nRecente"]
        valores = [
            row_score["score_cobertura"],
            row_score["score_recuperacao"],
            row_score["score_regeneracao"],
            row_score["score_saldo"],
            row_score["score_pressao"],
            row_score["score_desmatamento"],
        ]
        # Fechar o poligono
        categorias_r = categorias + [categorias[0]]
        valores_r = valores + [valores[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=valores_r,
            theta=categorias_r,
            fill="toself",
            fillcolor="rgba(31, 141, 73, 0.3)",
            line=dict(color="#1f8d49", width=2),
            name=mun_sel,
        ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            height=400,
            margin=dict(l=60, r=60, t=40, b=40),
        )
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        # Composicao LULC 2023 — pizza
        st.subheader("Uso do Solo 2023")

        df_mun_2023 = df_lulc[(df_lulc["municipio"] == mun_sel) & (df_lulc["ano"] == 2023)]
        df_mun_2023 = df_mun_2023[df_mun_2023["area_ha"] > 0].copy()
        df_mun_2023["label"] = df_mun_2023["classe"].map(NOMES_CLASSES)

        fig = px.pie(
            df_mun_2023, values="area_ha", names="label",
            color="classe", color_discrete_map=CORES_CLASSES,
            hole=0.4,
        )
        fig.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
        fig.update_layout(height=400, showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)

    # Indicadores detalhados
    st.subheader("Indicadores Detalhados")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown("**Vegetacao Nativa**")
        delta_veg = row["variacao_veg_ha"]
        st.metric("Variacao 1985-2023", f"{fmt_br(delta_veg, sinal=True)} ha",
                  delta=f"{fmt_br(row['variacao_veg_pct'], 1, sinal=True)}%",
                  delta_color="normal" if delta_veg >= 0 else "inverse")
        st.metric("Recuperacao Florestal 2010-2023",
                  f"{fmt_br(row['recup_florestal_2010_2023_ha'], sinal=True)} ha")
        st.metric("Taxa Recuperacao", f"{fmt_br(row['taxa_recup_florestal_ha_ano'], 1, sinal=True)} ha/ano")

    with col2:
        st.markdown("**Transicoes**")
        st.metric("Pasto -> Mata (total)", f"{fmt_br(row['pasto_para_mata_total_ha'])} ha")
        st.metric("Mata -> Pasto (total)", f"{fmt_br(row['mata_para_pasto_total_ha'])} ha")
        saldo = row["saldo_florestal_total_ha"]
        st.metric("Saldo Florestal", f"{fmt_br(saldo, sinal=True)} ha",
                  delta_color="normal" if saldo >= 0 else "inverse")

    with col3:
        st.markdown("**Pressao e Urbanizacao**")
        st.metric("Pressao Antropica 2023", f"{fmt_br(row['pressao_antropica_2023_pct'], 1)}%")
        st.metric("Var. Pressao (1985-2023)", f"{fmt_br(row['variacao_pressao_antropica_pp'], 1, sinal=True)} pp")
        st.metric("Crescimento Urbano", f"{fmt_br(row['cresc_urbano_ha'], sinal=True)} ha")
        st.metric("Desmatamento Recente (2020-23)", f"{fmt_br(row['desmatamento_recente_ha'])} ha")

    # Evolucao temporal deste municipio
    st.subheader(f"Evolucao Temporal — {mun_sel}")
    df_mun_all = df_lulc[df_lulc["municipio"] == mun_sel]

    fig = px.area(
        df_mun_all, x="ano", y="area_ha", color="classe",
        color_discrete_map=CORES_CLASSES,
        labels={"area_ha": "Area (ha)", "ano": "Ano", "classe": "Classe"},
    )
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
---

## 4. Indicadores Calculados (14 indices)
""")

    indices_df = pd.DataFrame([
        {"#": 1, "Indice": "ICV 2023", "Descricao": "% de cobertura vegetal nativa (floresta + veg. nao florestal) em 2023",
         "Unidade": "%", "Categoria": "Premiacao"},
        {"#": 2, "Indice": "Variacao Veg. Nativa", "Descricao": "Mudanca absoluta e relativa da vegetacao nativa (1985-2023)",
         "Unidade": "ha / %", "Categoria": "Premiacao"},
        {"#": 3, "Indice": "Recuperacao Florestal", "Descricao": "Aumento de area florestal entre 2010 e 2023",
         "Unidade": "ha / ha/ano", "Categoria": "Premiacao"},
        {"#": 4, "Indice": "Pasto -> Mata", "Descricao": "Area de pastagem convertida em floresta (regeneracao)",
         "Unidade": "ha", "Categoria": "Premiacao"},
        {"#": 5, "Indice": "Mata -> Pasto", "Descricao": "Area de floresta convertida em pastagem (desmatamento)",
         "Unidade": "ha", "Categoria": "Diagnostico"},
        {"#": 6, "Indice": "Saldo Florestal", "Descricao": "Regeneracao menos desmatamento (valor liquido)",
         "Unidade": "ha", "Categoria": "Premiacao"},
        {"#": 7, "Indice": "Crescimento Urbano", "Descricao": "Expansao da area urbana entre 1985 e 2023",
         "Unidade": "ha / %", "Categoria": "Diagnostico"},
        {"#": 8, "Indice": "Pressao Antropica", "Descricao": "% da area com uso antropico e sua variacao temporal",
         "Unidade": "% / pp", "Categoria": "Premiacao"},
        {"#": 9, "Indice": "Shannon", "Descricao": "Indice de diversidade de uso do solo (entropia de Shannon)",
         "Unidade": "adimensional", "Categoria": "Diagnostico"},
        {"#": 10, "Indice": "Eficiencia de Regeneracao", "Descricao": "Razao entre area regenerada e area desmatada",
         "Unidade": "adimensional", "Categoria": "Diagnostico"},
        {"#": 11, "Indice": "Saldo Veg. Nativa", "Descricao": "Conversao liquida entre vegetacao nativa e uso antropico",
         "Unidade": "ha", "Categoria": "Diagnostico"},
        {"#": 12, "Indice": "Variacao Agropecuaria", "Descricao": "Mudanca na area agropecuaria (pastagem + agricultura + mosaico)",
         "Unidade": "ha / %", "Categoria": "Diagnostico"},
        {"#": 13, "Indice": "Desmatamento Recente", "Descricao": "Vegetacao nativa convertida em uso antropico (2020-2023)",
         "Unidade": "ha / ha/ano", "Categoria": "Premiacao"},
        {"#": 14, "Indice": "Variacao Agua", "Descricao": "Mudanca em corpos d'agua entre 1985 e 2023",
         "Unidade": "ha", "Categoria": "Diagnostico"},
    ])
    st.dataframe(indices_df, use_container_width=True, hide_index=True)

    st.markdown("""
---

## 5. Score Ambiental Composto

O ranking geral utiliza **6 dos 14 indicadores**, combinados em um score ponderado de 0 a 100:
""")

    score_df = pd.DataFrame([
        {"Componente": "Cobertura Vegetal Nativa (ICV 2023)", "Peso": "20%",
         "Logica": "Maior cobertura = maior score"},
        {"Componente": "Recuperacao Florestal (2010-2023)", "Peso": "20%",
         "Logica": "Maior ganho de floresta = maior score"},
        {"Componente": "Regeneracao Pasto -> Mata (2010-2020)", "Peso": "15%",
         "Logica": "Maior conversao de pasto em mata = maior score"},
        {"Componente": "Saldo Florestal (2010-2020)", "Peso": "15%",
         "Logica": "Maior saldo liquido positivo = maior score"},
        {"Componente": "Variacao Pressao Antropica (1985-2023)", "Peso": "15%",
         "Logica": "INVERTIDO — menor aumento de pressao = maior score"},
        {"Componente": "Desmatamento Recente (2020-2023)", "Peso": "15%",
         "Logica": "INVERTIDO — menos desmatamento = maior score"},
    ])
    st.dataframe(score_df, use_container_width=True, hide_index=True)

    st.markdown("""
### Normalizacao

Cada indicador e normalizado pelo metodo **Min-Max** entre os 19 municipios da RH3:

```
Score = (valor - minimo) / (maximo - minimo) x 100
```

Para indicadores **invertidos** (pressao antropica e desmatamento), aplica-se:

```
Score = 100 - Score_normalizado
```

Assim, municipios com **menor** pressao/desmatamento recebem **maior** score.

### Formula Final

```
Score Ambiental = 0.20 x Cobertura + 0.20 x Recuperacao + 0.15 x Regeneracao
                + 0.15 x Saldo + 0.15 x Pressao (inv.) + 0.15 x Desmatamento (inv.)
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
