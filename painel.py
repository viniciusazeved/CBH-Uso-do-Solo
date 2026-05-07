"""
Painel Interativo — Diagnostico LULC RH3 Medio Paraiba do Sul
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
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler


def fmt_br(valor, decimais=0, sinal=False):
    """Formata numero no padrao brasileiro (ponto milhar, virgula decimal)."""
    if sinal:
        s = f"{valor:+,.{decimais}f}"
    else:
        s = f"{valor:,.{decimais}f}"
    # Troca: , -> X, . -> , , X -> .
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def botao_download_csv(df, label, filename, key):
    """Wrapper para download_button com encoding utf-8-sig (Excel-friendly)."""
    csv = df.to_csv(index=False).encode("utf-8-sig")
    st.download_button(
        label=label,
        data=csv,
        file_name=filename,
        mime="text/csv",
        key=key,
    )

# =============================================================================
#  CONFIG
# =============================================================================

st.set_page_config(
    page_title="Diagnostico LULC RH3",
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


def normalizar_indicadores(df_idx):
    """Normaliza indicadores via Min-Max (0-100) — apenas posicao relativa na bacia."""
    df = df_idx.copy()
    df["pos_cobertura"] = _normalizar(df["ICV_2023_pct"])
    df["pos_recuperacao"] = _normalizar(df["recup_florestal_2010_2023_ha"])
    df["pos_regeneracao"] = _normalizar(df["pasto_para_mata_recente_ha"])
    df["pos_saldo"] = _normalizar(df["saldo_florestal_recente_ha"])
    df["pos_pressao"] = _normalizar(df["variacao_pressao_antropica_pp"], inverter=True)
    df["pos_desmatamento"] = _normalizar(df["desmatamento_recente_ha"], inverter=True)
    return df


@st.cache_data
def classificar_tipologia(df_idx, n_clusters=4, seed=42):
    """Agrupa municipios em perfis via k-means sobre indicadores padronizados."""
    features = [
        "ICV_2023_pct",
        "variacao_veg_pct",
        "pressao_antropica_2023_pct",
        "recup_florestal_2010_2023_pct",
    ]
    X = df_idx[features].values
    Xs = StandardScaler().fit_transform(X)
    km = KMeans(n_clusters=n_clusters, n_init=20, random_state=seed)
    labels = km.fit_predict(Xs)

    df = df_idx.copy()
    df["cluster_id"] = labels

    centros = df.groupby("cluster_id")[features + ["area_total_na_rh3_ha"]].mean()

    # Ordenar por cobertura decrescente -> rotulo Tipo A, B, C, D
    ordem = centros["ICV_2023_pct"].sort_values(ascending=False).index.tolist()
    letras = ["A", "B", "C", "D", "E", "F"][:n_clusters]
    cid_to_letra = {cid: letras[i] for i, cid in enumerate(ordem)}

    def rotular(row):
        if row["ICV_2023_pct"] >= 35:
            cob = "Florestal"
        elif row["ICV_2023_pct"] >= 18:
            cob = "Misto"
        else:
            cob = "Antropizado"
        v = row["variacao_veg_pct"]
        if v >= 25:
            tra = "em Forte Recuperacao"
        elif v >= 3:
            tra = "em Recuperacao"
        elif v <= -3:
            tra = "em Regressao"
        else:
            tra = "Estavel"
        return f"{cob} {tra}"

    centros["rotulo"] = centros.apply(rotular, axis=1)
    centros["letra"] = centros.index.map(cid_to_letra)
    # Corrigir duplicatas
    counts = {}
    novos_rotulos = {}
    for cid in ordem:
        r = centros.at[cid, "rotulo"]
        counts[r] = counts.get(r, 0) + 1
        novos_rotulos[cid] = r if counts[r] == 1 else f"{r} ({counts[r]})"
    centros["rotulo"] = centros.index.map(novos_rotulos)
    centros["nome"] = centros["letra"] + " — " + centros["rotulo"]

    df["perfil_letra"] = df["cluster_id"].map(centros["letra"])
    df["perfil_rotulo"] = df["cluster_id"].map(centros["rotulo"])
    df["perfil_nome"] = df["cluster_id"].map(centros["nome"])

    return df, centros


# =============================================================================
#  LOAD
# =============================================================================

df_lulc, df_trans, df_idx, gdf = load_data()
df_rel = normalizar_indicadores(df_idx)
municipios_lista = sorted(df_idx["municipio"].unique())

# =============================================================================
#  SIDEBAR
# =============================================================================

st.sidebar.image("logo/LOGO - CBH MPS_colorida.png", width=180)
st.sidebar.title("Diagnostico LULC Municipal")
st.sidebar.caption("Caracterizacao da cobertura e dinamica do solo")
st.sidebar.markdown("MapBiomas Colecao 9 (1985-2023)")
st.sidebar.divider()

pagina = st.sidebar.radio(
    "Navegacao",
    ["🌎 Visao Geral da Bacia", "🗺️ Mapa Interativo", "🛰️ Cobertura LULC 1985 vs 2023",
     "📊 Evolucao Temporal", "🔄 Transicoes", "🧭 Tipologia Municipal",
     "🏙️ Perfil Municipal", "📐 Metodologia"],
    index=0,
)

st.sidebar.divider()

with st.sidebar.expander("📖 Glossario", expanded=False):
    st.markdown("""
- **ICV (Indice de Cobertura Vegetal Nativa):** percentual da area do municipio
  coberto por floresta + vegetacao natural nao florestal em 2023.
- **Recuperacao florestal:** ganho liquido de area florestal entre 2010 e 2023.
- **Saldo florestal:** regeneracao - desmatamento (valor liquido de transicoes).
- **Pressao antropica:** percentual da area com uso antropico (pastagem, agricultura,
  mosaico, silvicultura, urbano, mineracao).
- **Diversidade de Shannon:** entropia das classes de uso. Valores maiores indicam
  paisagem mais heterogenea.
- **Pasto -> Mata:** area que era pastagem em um ano e virou floresta em outro
  (regeneracao em pastagem).
- **Mata -> Pasto:** area que era floresta e foi convertida em pastagem (desmatamento).
- **Posicao relativa (0-100):** normalizacao Min-Max do indicador entre os 19
  municipios da RH3. So tem leitura comparativa interna a bacia.
""")

st.sidebar.caption("CBH Medio Paraiba do Sul · GT SIGA")
st.sidebar.caption("Fonte: MapBiomas Colecao 9 (1985-2023)")
st.sidebar.caption("Painel atualizado em maio/2026")


# =============================================================================
#  PAGINA 1: RANKING GERAL
# =============================================================================

if pagina == "🌎 Visao Geral da Bacia":
    st.title("Visao Geral da Bacia — RH3")
    st.markdown("**Diagnostico de uso e cobertura do solo** | Medio Paraiba do Sul | MapBiomas Colecao 9 (1985-2023)")

    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Municipios", f"{len(df_idx)}")
    col2.metric("Area Total na RH3", f"{fmt_br(df_idx['area_total_na_rh3_ha'].sum())} ha")
    media_icv = df_idx["ICV_2023_pct"].mean()
    col3.metric("Cobertura Vegetal Media 2023", f"{fmt_br(media_icv, 1)}%")
    media_pressao = df_idx["pressao_antropica_2023_pct"].mean()
    col4.metric("Pressao Antropica Media", f"{fmt_br(media_pressao, 1)}%")

    st.divider()

    st.markdown("""
Este painel **caracteriza** a cobertura e a dinamica do uso do solo nos 19 municipios
da RH3 entre 1985 e 2023. A intencao nao e ranquear municipios, mas diagnosticar como
cada um se inscreve na heterogeneidade da bacia — identificando padroes de cobertura,
trajetorias de mudanca, transicoes dominantes e focos de pressao territorial.
""")

    st.divider()

    # Composicao 2023 — RH3 agregada
    st.subheader("Composicao do Uso do Solo em 2023 — RH3 agregada")
    st.caption("Soma das areas por classe MapBiomas em toda a bacia hidrografica.")

    df_2023 = df_lulc[df_lulc["ano"] == 2023].groupby("classe")["area_ha"].sum().reset_index()
    df_2023 = df_2023[df_2023["area_ha"] > 0].sort_values("area_ha", ascending=True)
    df_2023["label"] = df_2023["classe"].map(NOMES_CLASSES).fillna(df_2023["classe"])
    total_rh3 = df_2023["area_ha"].sum()
    df_2023["pct"] = df_2023["area_ha"] / total_rh3 * 100

    fig_comp = go.Figure(go.Bar(
        y=df_2023["label"],
        x=df_2023["area_ha"],
        orientation="h",
        marker_color=[CORES_CLASSES.get(c, "#888") for c in df_2023["classe"]],
        text=[f"{fmt_br(v)} ha  ({fmt_br(p, 1)}%)" for v, p in zip(df_2023["area_ha"], df_2023["pct"])],
        textposition="outside",
        hovertemplate="<b>%{y}</b><br>Area: %{x:,.0f} ha<extra></extra>",
    ))
    fig_comp.update_layout(
        height=max(380, len(df_2023) * 38),
        xaxis_title="Area (ha)",
        margin=dict(l=200, r=140, t=20, b=40),
        yaxis=dict(title=""),
    )
    st.plotly_chart(fig_comp, use_container_width=True)

    st.divider()

    # Diagnostico cruzado: cobertura atual x trajetoria
    st.subheader("Diagnostico Cruzado: Cobertura Atual x Trajetoria 1985-2023")
    st.caption("Cada bolha e um municipio. Eixo X: cobertura nativa hoje. Eixo Y: variacao da vegetacao nativa em 38 anos. Tamanho: area na RH3.")

    df_quad = df_idx.copy()
    mediana_icv = df_quad["ICV_2023_pct"].median()

    fig_quad = px.scatter(
        df_quad,
        x="ICV_2023_pct",
        y="variacao_veg_pct",
        size="area_total_na_rh3_ha",
        hover_name="municipio",
        text="municipio",
        color="variacao_veg_pct",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        size_max=42,
        labels={
            "ICV_2023_pct": "Cobertura Vegetal Nativa em 2023 (%)",
            "variacao_veg_pct": "Variacao da Vegetacao Nativa 1985-2023 (%)",
            "area_total_na_rh3_ha": "Area na RH3 (ha)",
        },
    )
    fig_quad.add_hline(y=0, line_dash="dash", line_color="grey", opacity=0.6)
    fig_quad.add_vline(
        x=mediana_icv, line_dash="dash", line_color="grey", opacity=0.6,
        annotation_text=f"Mediana ({fmt_br(mediana_icv, 1)}%)",
        annotation_position="top",
    )
    fig_quad.update_traces(textposition="top center", textfont=dict(size=10))
    fig_quad.update_layout(height=540, margin=dict(l=20, r=20, t=20, b=40))
    st.plotly_chart(fig_quad, use_container_width=True)

    st.markdown("""
**Como ler o grafico:**
- **Quadrante superior direito** — alta cobertura nativa hoje **e** ganhando vegetacao (conservacao com regeneracao).
- **Quadrante superior esquerdo** — baixa cobertura, mas em recuperacao (degradacao com sinais de reversao).
- **Quadrante inferior direito** — alta cobertura, porem perdendo vegetacao (conservacao sob pressao).
- **Quadrante inferior esquerdo** — baixa cobertura **e** continuando a perder (degradacao persistente).
""")

    st.divider()

    # Distribuicao entre municipios
    st.subheader("Distribuicao dos Indicadores entre os Municipios")
    st.caption("Cada ponto representa um municipio. A caixa mostra a mediana, os quartis e a amplitude observada na bacia.")

    indicadores_dist = {
        "ICV_2023_pct": "Cobertura Vegetal Nativa 2023 (%)",
        "pressao_antropica_2023_pct": "Pressao Antropica 2023 (%)",
        "recup_florestal_2010_2023_ha": "Recuperacao Florestal 2010-2023 (ha)",
        "saldo_florestal_total_ha": "Saldo Florestal 1985-2023 (ha)",
        "desmatamento_recente_ha": "Desmatamento Recente 2020-2023 (ha)",
        "variacao_veg_pct": "Variacao Veg. Nativa 1985-2023 (%)",
        "shannon_2023": "Diversidade de Uso (Shannon)",
    }

    indic_sel = st.selectbox(
        "Indicador:",
        list(indicadores_dist.keys()),
        format_func=lambda x: indicadores_dist[x],
    )

    df_dist = df_idx[["municipio", indic_sel]].copy().sort_values(indic_sel)

    fig_box = go.Figure()
    fig_box.add_trace(go.Box(
        x=df_dist[indic_sel],
        boxpoints="all",
        jitter=0.5,
        pointpos=0,
        marker=dict(color="#1f8d49", size=9, line=dict(width=1, color="#0e5d2e")),
        line=dict(color="#1f8d49"),
        fillcolor="rgba(31,141,73,0.18)",
        text=df_dist["municipio"],
        hovertemplate="<b>%{text}</b><br>" + indicadores_dist[indic_sel] + ": %{x:.2f}<extra></extra>",
        name="",
    ))
    fig_box.update_layout(
        height=300,
        xaxis_title=indicadores_dist[indic_sel],
        showlegend=False,
        margin=dict(l=40, r=40, t=20, b=40),
        yaxis=dict(showticklabels=False),
    )
    st.plotly_chart(fig_box, use_container_width=True)

    # Estatisticas resumo
    serie_ind = df_dist[indic_sel]
    stat_col1, stat_col2, stat_col3, stat_col4 = st.columns(4)
    stat_col1.metric("Mediana", fmt_br(serie_ind.median(), 2))
    stat_col2.metric("Media", fmt_br(serie_ind.mean(), 2))
    stat_col3.metric("Minimo", fmt_br(serie_ind.min(), 2))
    stat_col4.metric("Maximo", fmt_br(serie_ind.max(), 2))

    with st.expander("Distribuicao ordenada por municipio"):
        df_show = df_dist.reset_index(drop=True)
        df_show.index = df_show.index + 1
        df_show.columns = ["Municipio", indicadores_dist[indic_sel]]
        st.dataframe(df_show, use_container_width=True, height=420)

    st.divider()

    # Tabela completa
    with st.expander("Tabela completa de indicadores municipais"):
        df_full = df_idx.sort_values("municipio").reset_index(drop=True)
        st.dataframe(df_full, use_container_width=True, height=500)
        botao_download_csv(
            df_full,
            "⬇️ Baixar tabela de indicadores (CSV)",
            "indicadores_rh3.csv",
            key="dl_full_idx",
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

    # Extremos da distribuicao
    st.caption("Municipios nos extremos da distribuicao para o indicador selecionado.")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Maiores valores observados")
        top5 = df_idx.nlargest(5, indicador)[["municipio", indicador]].reset_index(drop=True)
        top5.index = top5.index + 1
        top5.columns = ["Municipio", INDICADORES_MAPA[indicador]]
        st.dataframe(top5, use_container_width=True)

    with col2:
        st.subheader("Menores valores observados")
        bot5 = df_idx.nsmallest(5, indicador)[["municipio", indicador]].reset_index(drop=True)
        bot5.index = bot5.index + 1
        bot5.columns = ["Municipio", INDICADORES_MAPA[indicador]]
        st.dataframe(bot5, use_container_width=True)

    df_dl_mapa = df_idx[["municipio", "cod_ibge", indicador]].sort_values(indicador, ascending=False)
    botao_download_csv(
        df_dl_mapa,
        f"⬇️ Baixar valores de {INDICADORES_MAPA[indicador]} (CSV)",
        f"mapa_{indicador}.csv",
        key=f"dl_mapa_{indicador}",
    )


# =============================================================================
#  PAGINA: COBERTURA LULC 1985 vs 2023 (mapa raster)
# =============================================================================

elif pagina == "🛰️ Cobertura LULC 1985 vs 2023":
    st.title("🛰️ Cobertura LULC 1985 vs 2023")
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

        # Limite RH3 em GeoJSON (overlay vetorial)
        rh3_limite_geojson = gdf.geometry.union_all().__geo_interface__

        def _criar_mapa(ano, key_suffix):
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
                st_folium(_criar_mapa(1985, "1985"), height=520, width=None,
                          returned_objects=[], key="mapa_lulc_1985")
            with col2:
                st.markdown("**2023**")
                st_folium(_criar_mapa(2023, "2023"), height=520, width=None,
                          returned_objects=[], key="mapa_lulc_2023")
            st.markdown(legenda_html, unsafe_allow_html=True)
        else:
            ano_sel = st.select_slider("Ano:", options=bbox["anos"], value=bbox["anos"][-1])
            map_col, leg_col = st.columns([4, 1])
            with map_col:
                st_folium(_criar_mapa(ano_sel, f"slider_{ano_sel}"),
                          height=600, width=None, returned_objects=[],
                          key=f"mapa_lulc_slider_{ano_sel}")
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

    # Cores por classe (origem/destino) para o Sankey
    CORES_NODE = {
        "Floresta": "#1f8d49",
        "VegNativa": "#7dc975",
        "Silvicultura": "#7a5900",
        "Pastagem": "#ffd966",
        "Agricultura": "#e974ed",
        "Mosaico": "#ffefc3",
        "Urbano": "#d4271e",
        "Antropico": "#d4271e",
    }

    tab1, tab2, tab3 = st.tabs(["Sankey de Fluxos", "Visao Geral RH3", "Por Municipio"])

    # --- Tab Sankey ---
    with tab1:
        st.caption("Fluxo de area entre classes de uso e cobertura. Largura proporcional a area transicionada (ha).")

        # Filtra agregados para evitar duplo-contagem
        agregados = {"VegNativa_para_Antropico", "Antropico_para_VegNativa"}
        df_sk = df_per[~df_per["transicao"].isin(agregados)].copy()
        df_sk = df_sk.groupby("transicao", as_index=False)["area_ha"].sum()
        df_sk = df_sk[df_sk["area_ha"] > 0]

        # Parse origem/destino
        df_sk[["origem", "destino"]] = df_sk["transicao"].str.split("_para_", n=1, expand=True)

        # Filtro de area minima para limpar visualizacao
        area_min = st.slider(
            "Filtrar fluxos abaixo de (ha):",
            min_value=0.0,
            max_value=float(df_sk["area_ha"].max()),
            value=10.0,
            step=10.0,
        )
        df_sk = df_sk[df_sk["area_ha"] >= area_min]

        if len(df_sk) == 0:
            st.info("Nenhum fluxo acima do limiar selecionado.")
        else:
            # Sufixos para diferenciar origem/destino e permitir bipartido visual
            origens = [f"{o} (origem)" for o in df_sk["origem"].unique()]
            destinos = [f"{d} (destino)" for d in df_sk["destino"].unique()]
            labels = origens + destinos
            label_to_idx = {label: i for i, label in enumerate(labels)}

            # Cores dos nos
            node_colors = []
            for label in labels:
                base = label.split(" (")[0]
                node_colors.append(CORES_NODE.get(base, "#888888"))

            sources = [label_to_idx[f"{o} (origem)"] for o in df_sk["origem"]]
            targets = [label_to_idx[f"{d} (destino)"] for d in df_sk["destino"]]
            values = df_sk["area_ha"].tolist()

            # Cor do link = cor do destino (com transparencia) — mostra para onde vai
            link_colors = []
            for d in df_sk["destino"]:
                base_color = CORES_NODE.get(d, "#888888")
                # Converte hex para rgba com 0.5 alpha
                r, g, b = int(base_color[1:3], 16), int(base_color[3:5], 16), int(base_color[5:7], 16)
                link_colors.append(f"rgba({r},{g},{b},0.45)")

            fig_sk = go.Figure(go.Sankey(
                arrangement="snap",
                node=dict(
                    pad=18,
                    thickness=18,
                    line=dict(color="black", width=0.5),
                    label=labels,
                    color=node_colors,
                ),
                link=dict(
                    source=sources,
                    target=targets,
                    value=values,
                    color=link_colors,
                    hovertemplate="<b>%{source.label} -> %{target.label}</b><br>%{value:,.0f} ha<extra></extra>",
                ),
            ))
            fig_sk.update_layout(
                height=560,
                margin=dict(l=10, r=10, t=20, b=20),
                font=dict(size=12),
            )
            st.plotly_chart(fig_sk, use_container_width=True)

            with st.expander("Tabela dos fluxos"):
                df_show = df_sk.copy().sort_values("area_ha", ascending=False).reset_index(drop=True)
                df_show.index = df_show.index + 1
                df_show = df_show.rename(columns={
                    "transicao": "Transicao",
                    "area_ha": "Area (ha)",
                    "origem": "Origem",
                    "destino": "Destino",
                })
                st.dataframe(df_show, use_container_width=True)

    # --- Tab Visao Geral (barras horizontais) ---
    with tab2:
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

    # --- Tab Por Municipio ---
    with tab3:
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
#  PAGINA: TIPOLOGIA MUNICIPAL (k-means)
# =============================================================================

elif pagina == "🧭 Tipologia Municipal":
    st.title("🧭 Tipologia Municipal — Perfis na RH3")
    st.caption(
        "Agrupamento dos 19 municipios em perfis ambientais usando k-means (k=4) "
        "sobre 4 indicadores padronizados: cobertura nativa 2023, variacao da vegetacao "
        "1985-2023, pressao antropica 2023 e taxa de recuperacao florestal 2010-2023."
    )

    df_tip, centros_tip = classificar_tipologia(df_idx)

    perfis_unicos = sorted(df_tip["perfil_nome"].unique())
    palette = ["#1f8d49", "#7dc975", "#e974ed", "#d4271e", "#ffd966", "#888888"]
    cor_perfil = {p: palette[i % len(palette)] for i, p in enumerate(perfis_unicos)}

    # Mapa dos perfis
    st.subheader("Distribuicao Espacial dos Perfis")

    gdf_tip = gdf.merge(
        df_tip[["municipio", "perfil_nome", "perfil_letra"]],
        on="municipio", how="left",
    )
    gdf_tip_json = json.loads(gdf_tip.to_json())
    for i, feat in enumerate(gdf_tip_json["features"]):
        feat["id"] = str(i)
    gdf_tip["_id"] = [str(i) for i in range(len(gdf_tip))]

    bounds = gdf_tip.total_bounds
    center_lat = (bounds[1] + bounds[3]) / 2
    center_lon = (bounds[0] + bounds[2]) / 2

    fig_map = px.choropleth_mapbox(
        gdf_tip,
        geojson=gdf_tip_json,
        locations="_id",
        color="perfil_nome",
        hover_name="municipio",
        hover_data={"perfil_letra": True, "_id": False},
        color_discrete_map=cor_perfil,
        mapbox_style="carto-positron",
        center={"lat": center_lat, "lon": center_lon},
        zoom=8.5,
        opacity=0.75,
        labels={"perfil_nome": "Perfil", "perfil_letra": "Tipo"},
    )
    fig_map.update_layout(
        height=540,
        margin=dict(l=0, r=0, t=20, b=0),
        legend=dict(title="Perfil"),
    )
    st.plotly_chart(fig_map, use_container_width=True)

    # Scatter do diagnostico cruzado, colorido por perfil
    st.subheader("Cobertura Atual x Trajetoria, Colorido por Perfil")
    fig_scatter = px.scatter(
        df_tip,
        x="ICV_2023_pct",
        y="variacao_veg_pct",
        size="area_total_na_rh3_ha",
        color="perfil_nome",
        text="municipio",
        color_discrete_map=cor_perfil,
        size_max=42,
        labels={
            "ICV_2023_pct": "Cobertura Vegetal Nativa em 2023 (%)",
            "variacao_veg_pct": "Variacao da Vegetacao Nativa 1985-2023 (%)",
            "area_total_na_rh3_ha": "Area na RH3 (ha)",
            "perfil_nome": "Perfil",
        },
    )
    fig_scatter.add_hline(y=0, line_dash="dash", line_color="grey", opacity=0.5)
    fig_scatter.update_traces(textposition="top center", textfont=dict(size=10))
    fig_scatter.update_layout(height=520, margin=dict(l=20, r=20, t=20, b=40))
    st.plotly_chart(fig_scatter, use_container_width=True)

    st.divider()

    # Caracterizacao dos perfis (cards)
    st.subheader("Caracterizacao de Cada Perfil")
    for nome in perfis_unicos:
        with st.container(border=True):
            df_perfil = df_tip[df_tip["perfil_nome"] == nome]
            mun_nomes = ", ".join(sorted(df_perfil["municipio"].tolist()))

            cor_box = cor_perfil[nome]
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:12px'>"
                f"<div style='width:14px;height:14px;background:{cor_box};border-radius:3px'></div>"
                f"<h4 style='margin:0'>{nome}</h4></div>",
                unsafe_allow_html=True,
            )

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Municipios", f"{len(df_perfil)}")
            c2.metric("Cobertura Media 2023", f"{fmt_br(df_perfil['ICV_2023_pct'].mean(), 1)}%")
            c3.metric("Variacao 1985-2023", f"{fmt_br(df_perfil['variacao_veg_pct'].mean(), 1, sinal=True)}%")
            c4.metric("Pressao Antropica 2023", f"{fmt_br(df_perfil['pressao_antropica_2023_pct'].mean(), 1)}%")
            st.markdown(f"**Municipios:** {mun_nomes}")

    botao_download_csv(
        df_tip[["municipio", "cod_ibge", "perfil_letra", "perfil_rotulo", "perfil_nome"]],
        "⬇️ Baixar tipologia por municipio (CSV)",
        "tipologia_municipios_rh3.csv",
        key="dl_tipologia",
    )

    with st.expander("Como o agrupamento foi feito"):
        st.markdown("""
- **Algoritmo**: k-means com k=4, n_init=20, seed=42 (resultado deterministico).
- **Variaveis**: ICV_2023_pct, variacao_veg_pct (1985-2023), pressao_antropica_2023_pct,
  recup_florestal_2010_2023_pct.
- **Padronizacao**: z-score (StandardScaler) — todas as variaveis em escala comparavel.
- **Rotulagem**: cada cluster recebe uma letra (ordenada por cobertura decrescente)
  e um descritor heuristico baseado nos centros do cluster (Florestal/Misto/Antropizado +
  em Recuperacao/Estavel/em Regressao).
- **Limitacao**: tipologia descritiva, util para sintetizar a heterogeneidade da
  bacia. Nao substitui analise individual de cada municipio.
""")


# =============================================================================
#  PAGINA 5: PERFIL MUNICIPAL
# =============================================================================

elif pagina == "🏙️ Perfil Municipal":
    st.title("🏙️ Perfil Municipal")
    st.caption("Caracterizacao individual do municipio dentro da RH3 — sem comparacao competitiva.")

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
    row_rel = df_rel[df_rel["municipio"] == mun_sel].iloc[0]
    if mun_b:
        row_b = df_idx[df_idx["municipio"] == mun_b].iloc[0]
        row_rel_b = df_rel[df_rel["municipio"] == mun_b].iloc[0]

    # KPIs do municipio principal
    st.markdown(f"**{mun_sel}**")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Area na RH3", f"{fmt_br(row['area_total_na_rh3_ha'])} ha")
    col2.metric("ICV 2023", f"{fmt_br(row['ICV_2023_pct'], 1)}%")
    col3.metric("Pressao Antropica 2023", f"{fmt_br(row['pressao_antropica_2023_pct'], 1)}%")
    col4.metric("Diversidade (Shannon)", fmt_br(row["shannon_2023"], 2))

    if mun_b:
        st.markdown(f"**{mun_b}**")
        col1b, col2b, col3b, col4b = st.columns(4)
        col1b.metric("Area na RH3", f"{fmt_br(row_b['area_total_na_rh3_ha'])} ha")
        col2b.metric("ICV 2023", f"{fmt_br(row_b['ICV_2023_pct'], 1)}%")
        col3b.metric("Pressao Antropica 2023", f"{fmt_br(row_b['pressao_antropica_2023_pct'], 1)}%")
        col4b.metric("Diversidade (Shannon)", fmt_br(row_b["shannon_2023"], 2))

    st.divider()

    col_left, col_right = st.columns(2)

    # ---- Radar ----
    with col_left:
        st.subheader("Perfil Relativo na Bacia (0-100)")
        st.caption(
            "Cada eixo mostra a posicao relativa do municipio na distribuicao da RH3 "
            "(Min-Max entre os 19 municipios). Indica onde o municipio se encaixa na bacia, "
            "nao um julgamento absoluto."
        )

        categorias = ["Cobertura\nVegetal", "Recuperacao\nFlorestal", "Regeneracao",
                      "Saldo\nFlorestal", "Pressao\nAntropica", "Desmatamento\nRecente"]
        cols_pos = ["pos_cobertura", "pos_recuperacao", "pos_regeneracao",
                    "pos_saldo", "pos_pressao", "pos_desmatamento"]

        valores_a = [row_rel[c] for c in cols_pos]
        categorias_r = categorias + [categorias[0]]
        valores_a_r = valores_a + [valores_a[0]]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=valores_a_r,
            theta=categorias_r,
            fill="toself",
            fillcolor="rgba(31, 141, 73, 0.3)",
            line=dict(color="#1f8d49", width=2),
            name=mun_sel,
        ))
        if mun_b:
            valores_b = [row_rel_b[c] for c in cols_pos]
            valores_b_r = valores_b + [valores_b[0]]
            fig.add_trace(go.Scatterpolar(
                r=valores_b_r,
                theta=categorias_r,
                fill="toself",
                fillcolor="rgba(228, 116, 237, 0.25)",
                line=dict(color="#a020f0", width=2),
                name=mun_b,
            ))
        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            height=420,
            margin=dict(l=60, r=60, t=40, b=40),
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, xanchor="center", x=0.5),
        )
        st.plotly_chart(fig, use_container_width=True)

    # ---- Pizza ----
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

            fig = px.pie(
                df_mun_2023, values="area_ha", names="label",
                color="classe", color_discrete_map=CORES_CLASSES,
                hole=0.4,
            )
            fig.update_traces(textposition="inside", textinfo="percent+label", textfont_size=11)
            fig.update_layout(height=420, showlegend=False, margin=dict(l=20, r=20, t=20, b=20))
            st.plotly_chart(fig, use_container_width=True)

    # ---- Indicadores ----
    st.subheader("Indicadores Detalhados")

    if mun_b:
        # Tabela comparativa
        indicadores_comp = [
            ("Variacao Veg. Nativa 1985-2023 (ha)", "variacao_veg_ha", 0, True),
            ("Variacao Veg. Nativa 1985-2023 (%)", "variacao_veg_pct", 1, True),
            ("Recuperacao Florestal 2010-2023 (ha)", "recup_florestal_2010_2023_ha", 0, True),
            ("Taxa Recuperacao (ha/ano)", "taxa_recup_florestal_ha_ano", 1, True),
            ("Pasto -> Mata total (ha)", "pasto_para_mata_total_ha", 0, False),
            ("Mata -> Pasto total (ha)", "mata_para_pasto_total_ha", 0, False),
            ("Saldo Florestal 1985-2023 (ha)", "saldo_florestal_total_ha", 0, True),
            ("Pressao Antropica 2023 (%)", "pressao_antropica_2023_pct", 1, False),
            ("Variacao Pressao 1985-2023 (pp)", "variacao_pressao_antropica_pp", 1, True),
            ("Crescimento Urbano (ha)", "cresc_urbano_ha", 0, True),
            ("Desmatamento Recente 2020-23 (ha)", "desmatamento_recente_ha", 0, False),
        ]
        rows = []
        for label, col, dec, com_sinal in indicadores_comp:
            rows.append({
                "Indicador": label,
                mun_sel: fmt_br(row[col], dec, sinal=com_sinal),
                mun_b: fmt_br(row_b[col], dec, sinal=com_sinal),
            })
        df_comp_ind = pd.DataFrame(rows)
        st.dataframe(df_comp_ind, use_container_width=True, hide_index=True, height=420)
    else:
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

    # ---- Evolucao temporal ----
    if mun_b:
        st.subheader(f"Evolucao da Cobertura Vegetal Nativa — {mun_sel} vs {mun_b}")
        # Calcular ICV temporal de ambos
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
        {"#": 1, "Indice": "ICV 2023",
         "Descricao": "% de cobertura vegetal nativa (floresta + veg. nao florestal) em 2023",
         "Unidade": "%"},
        {"#": 2, "Indice": "Variacao Veg. Nativa",
         "Descricao": "Mudanca absoluta e relativa da vegetacao nativa (1985-2023)",
         "Unidade": "ha / %"},
        {"#": 3, "Indice": "Recuperacao Florestal",
         "Descricao": "Aumento de area florestal entre 2010 e 2023",
         "Unidade": "ha / ha/ano"},
        {"#": 4, "Indice": "Pasto -> Mata",
         "Descricao": "Area de pastagem convertida em floresta (regeneracao)",
         "Unidade": "ha"},
        {"#": 5, "Indice": "Mata -> Pasto",
         "Descricao": "Area de floresta convertida em pastagem (desmatamento)",
         "Unidade": "ha"},
        {"#": 6, "Indice": "Saldo Florestal",
         "Descricao": "Regeneracao menos desmatamento (valor liquido)",
         "Unidade": "ha"},
        {"#": 7, "Indice": "Crescimento Urbano",
         "Descricao": "Expansao da area urbana entre 1985 e 2023",
         "Unidade": "ha / %"},
        {"#": 8, "Indice": "Pressao Antropica",
         "Descricao": "% da area com uso antropico e sua variacao temporal",
         "Unidade": "% / pp"},
        {"#": 9, "Indice": "Shannon",
         "Descricao": "Indice de diversidade de uso do solo (entropia de Shannon)",
         "Unidade": "adimensional"},
        {"#": 10, "Indice": "Eficiencia de Regeneracao",
         "Descricao": "Razao entre area regenerada e area desmatada",
         "Unidade": "adimensional"},
        {"#": 11, "Indice": "Saldo Veg. Nativa",
         "Descricao": "Conversao liquida entre vegetacao nativa e uso antropico",
         "Unidade": "ha"},
        {"#": 12, "Indice": "Variacao Agropecuaria",
         "Descricao": "Mudanca na area agropecuaria (pastagem + agricultura + mosaico)",
         "Unidade": "ha / %"},
        {"#": 13, "Indice": "Desmatamento Recente",
         "Descricao": "Vegetacao nativa convertida em uso antropico (2020-2023)",
         "Unidade": "ha / ha/ano"},
        {"#": 14, "Indice": "Variacao Agua",
         "Descricao": "Mudanca em corpos d'agua entre 1985 e 2023",
         "Unidade": "ha"},
    ])
    st.dataframe(indices_df, use_container_width=True, hide_index=True)

    st.markdown("""
---

## 5. Posicao Relativa na Bacia (Normalizacao Min-Max)

Para facilitar a leitura comparativa **descritiva** (sem juizo de valor), o painel
expressa alguns indicadores em uma escala de 0 a 100 que representa a **posicao
relativa do municipio na distribuicao da RH3**. Essa normalizacao alimenta o radar
do *Perfil Municipal* e nao deve ser interpretada como score de desempenho.

```
Posicao = (valor - minimo) / (maximo - minimo) x 100
```

Para indicadores em que **menor e melhor do ponto de vista ambiental** (variacao da
pressao antropica e desmatamento recente), a escala e invertida:

```
Posicao = 100 - Posicao_normalizada
```

Assim, valores proximos de 100 indicam que o municipio esta no extremo da bacia
para aquele indicador — **o que importa e o conjunto**, nao o numero isolado.

| Indicador | Direcao da escala |
|-----------|-------------------|
| Cobertura Vegetal Nativa (ICV 2023) | Direta (maior valor -> 100) |
| Recuperacao Florestal (2010-2023) | Direta |
| Regeneracao Pasto -> Mata (2010-2020) | Direta |
| Saldo Florestal (2010-2020) | Direta |
| Variacao Pressao Antropica (1985-2023) | Invertida |
| Desmatamento Recente (2020-2023) | Invertida |

> **Observacao:** o painel nao agrega esses valores em um indice composto. A leitura
> deve ser feita indicador a indicador, considerando o contexto territorial de cada
> municipio (tamanho da porcao na RH3, vocacao economica, historico de ocupacao).

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
