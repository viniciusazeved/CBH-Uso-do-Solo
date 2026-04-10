"""
=============================================================================
ANÁLISE DE USO E COBERTURA DO SOLO — RH3 MÉDIO PARAÍBA DO SUL
Dados: MapBiomas Coleção 9 (1985–2023)
Objetivo: Ranking Municipal para Premiação CEIVAP
=============================================================================
"""

import ee
import geemap
import geopandas as gpd
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib
import os
import warnings

matplotlib.use("Agg")
warnings.filterwarnings("ignore")

# ====================== CONFIGURAÇÕES ======================
PROJETO_GEE = "ggeantigravity"
SCALE = 30
ANOS_MARCOS = [1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2023]

PERIODOS_TRANSICAO = [
    (1985, 2000),
    (2000, 2010),
    (2010, 2020),
    (2020, 2023),
    (1985, 2023),
]

# Classes MapBiomas Coleção 9
CLASSES = {
    "Floresta": [3, 4, 5, 6, 49],
    "Vegetacao_Natural_Nao_Florestal": [10, 11, 12, 13, 32, 50],
    "Silvicultura": [9],
    "Pastagem": [15],
    "Agricultura": [18, 19, 20, 39, 40, 41, 46, 47, 48, 35, 36],
    "Mosaico_Agropecuario": [21],
    "Area_Urbana": [24],
    "Mineracao": [30],
    "Agua": [26, 33],
    "Area_Nao_Vegetada": [22, 23, 25, 29],
    "Aquicultura": [31],
    "Nao_Observado": [27],
}

VEGETACAO_NATIVA = [3, 4, 5, 6, 10, 11, 12, 13, 32, 49, 50]
USO_ANTROPICO = [9, 15, 18, 19, 20, 21, 24, 30, 31, 35, 36, 39, 40, 41, 46, 47, 48]
FLORESTA = [3, 4, 5, 6, 49]

TRANSICOES_INTERESSE = {
    "Floresta_para_Pastagem": {"de": FLORESTA, "para": [15]},
    "Pastagem_para_Floresta": {"de": [15], "para": FLORESTA},
    "Floresta_para_Agricultura": {"de": FLORESTA, "para": [18, 19, 20, 39, 40, 41, 46, 47, 48, 35, 36]},
    "Floresta_para_Urbano": {"de": FLORESTA, "para": [24]},
    "Pastagem_para_Urbano": {"de": [15], "para": [24]},
    "Agricultura_para_Urbano": {"de": [18, 19, 20, 21, 39, 40, 41], "para": [24]},
    "VegNativa_para_Antropico": {"de": VEGETACAO_NATIVA, "para": USO_ANTROPICO},
    "Antropico_para_VegNativa": {"de": USO_ANTROPICO, "para": VEGETACAO_NATIVA},
    "Pastagem_para_Agricultura": {"de": [15], "para": [18, 19, 20, 39, 40, 41, 46, 47, 48, 35, 36]},
    "Silvicultura_para_Floresta": {"de": [9], "para": FLORESTA},
    "Floresta_para_Silvicultura": {"de": FLORESTA, "para": [9]},
}

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

# ====================== DIRETÓRIOS ======================
for d in ["./data", "./output/graficos", "./output/tabelas"]:
    os.makedirs(d, exist_ok=True)


# =============================================================================
#  ETAPA 1 — PREPARAÇÃO DOS DADOS VETORIAIS
# =============================================================================

def preparar_municipios_rh3():
    """Carrega shapefiles locais, clipa municípios pela RH3 e retorna GeoDataFrame."""
    print("=" * 60)
    print("ETAPA 1 — Preparação dos dados vetoriais")
    print("=" * 60)

    rh3 = gpd.read_file("./shp/RH_III.shp")
    municipios = gpd.read_file("./shp/MUNICIPIOS_RJ.shp", encoding="utf-8")

    # Garantir mesmo CRS (ambos já são 31983, mas por segurança)
    municipios = municipios.to_crs(rh3.crs)

    # Clipar municípios pela RH3
    munic_rh3 = gpd.overlay(municipios, rh3[["geometry"]], how="intersection")

    # Calcular área dentro da RH3 (CRS já é métrico — SIRGAS 2000 / UTM 23S)
    munic_rh3["area_na_rh3_km2"] = munic_rh3.geometry.area / 1e6
    munic_rh3["area_na_rh3_ha"] = munic_rh3.geometry.area / 1e4

    # Salvar
    munic_rh3.to_file("./data/municipios_clipped_rh3.shp", encoding="utf-8")

    print(f"  Total de municípios na RH3: {len(munic_rh3)}")
    print(f"  Área total da RH3 coberta: {munic_rh3['area_na_rh3_km2'].sum():.1f} km²")
    print(f"  Municípios: {', '.join(sorted(munic_rh3['NM_MUN'].tolist()))}")
    print()

    return munic_rh3


# =============================================================================
#  ETAPA 2 — EXTRAÇÃO LULC VIA GEE
# =============================================================================

def _criar_mascara_classe(classificacao, classe_ids):
    """Cria máscara binária para uma lista de IDs de classe."""
    mascara = classificacao.eq(classe_ids[0])
    for cid in classe_ids[1:]:
        mascara = mascara.Or(classificacao.eq(cid))
    return mascara


def extrair_lulc_por_municipio(municipios_fc, mapbiomas_img, ano):
    """
    Para cada município (já clippado pela RH3), calcula a área (ha) de cada classe LULC.
    Usa uma imagem empilhada com uma banda por classe para fazer uma única reduceRegions.
    """
    banda = f"classification_{ano}"
    classificacao = mapbiomas_img.select(banda)
    pixel_area = ee.Image.pixelArea().divide(10000)  # hectares

    # Empilhar todas as classes em uma só imagem
    imagens = []
    nomes = []
    for classe_nome, classe_ids in CLASSES.items():
        mascara = _criar_mascara_classe(classificacao, classe_ids)
        imagens.append(pixel_area.updateMask(mascara).rename(classe_nome))
        nomes.append(classe_nome)

    img_empilhada = ee.Image(imagens)

    stats = img_empilhada.reduceRegions(
        collection=municipios_fc,
        reducer=ee.Reducer.sum(),
        scale=SCALE,
        crs="EPSG:4326",
    )

    feat_list = stats.getInfo()["features"]

    resultados = []
    for feat in feat_list:
        props = feat["properties"]
        mun_nome = props.get("NM_MUN", "NA")
        cod_ibge = props.get("CD_MUN", "NA")
        for classe_nome in nomes:
            resultados.append({
                "municipio": mun_nome,
                "cod_ibge": cod_ibge,
                "ano": ano,
                "classe": classe_nome,
                "area_ha": props.get(classe_nome, 0) or 0,
            })

    return resultados


def extrair_lulc_todos_anos(municipios_fc, mapbiomas_img, anos):
    """Extrai LULC para todos os anos-marco."""
    print("=" * 60)
    print("ETAPA 2 — Extração de dados LULC (MapBiomas)")
    print("=" * 60)

    todos = []
    for i, ano in enumerate(anos):
        print(f"  [{i+1}/{len(anos)}] Processando {ano}...")
        res = extrair_lulc_por_municipio(municipios_fc, mapbiomas_img, ano)
        todos.extend(res)

    df = pd.DataFrame(todos)
    df.to_csv("./output/lulc_municipios_rh3.csv", index=False, encoding="utf-8-sig")
    print(f"  Total de registros: {len(df)}")
    print()
    return df


# =============================================================================
#  ETAPA 3 — TRANSIÇÕES
# =============================================================================

def calcular_transicao(municipios_fc, mapbiomas_img, ano_inicio, ano_fim):
    """Calcula a área de cada transição de interesse entre dois anos."""
    class_ini = mapbiomas_img.select(f"classification_{ano_inicio}")
    class_fim = mapbiomas_img.select(f"classification_{ano_fim}")
    pixel_area = ee.Image.pixelArea().divide(10000)

    # Empilhar todas as transições em uma só imagem
    imagens = []
    nomes = []
    for trans_nome, trans_def in TRANSICOES_INTERESSE.items():
        mascara_de = _criar_mascara_classe(class_ini, trans_def["de"])
        mascara_para = _criar_mascara_classe(class_fim, trans_def["para"])
        transicao = mascara_de.And(mascara_para)
        imagens.append(pixel_area.updateMask(transicao).rename(trans_nome))
        nomes.append(trans_nome)

    img_empilhada = ee.Image(imagens)

    stats = img_empilhada.reduceRegions(
        collection=municipios_fc,
        reducer=ee.Reducer.sum(),
        scale=SCALE,
        crs="EPSG:4326",
    )

    feat_list = stats.getInfo()["features"]

    resultados = []
    for feat in feat_list:
        props = feat["properties"]
        mun_nome = props.get("NM_MUN", "NA")
        cod_ibge = props.get("CD_MUN", "NA")
        for trans_nome in nomes:
            resultados.append({
                "municipio": mun_nome,
                "cod_ibge": cod_ibge,
                "transicao": trans_nome,
                "periodo": f"{ano_inicio}-{ano_fim}",
                "area_ha": props.get(trans_nome, 0) or 0,
            })

    return resultados


def extrair_transicoes_todos_periodos(municipios_fc, mapbiomas_img, periodos):
    """Extrai transições para todos os períodos."""
    print("=" * 60)
    print("ETAPA 3 — Análise de transições")
    print("=" * 60)

    todos = []
    for i, (ini, fim) in enumerate(periodos):
        print(f"  [{i+1}/{len(periodos)}] Transições {ini}–{fim}...")
        res = calcular_transicao(municipios_fc, mapbiomas_img, ini, fim)
        todos.extend(res)

    df = pd.DataFrame(todos)
    df.to_csv("./output/transicoes_municipios_rh3.csv", index=False, encoding="utf-8-sig")
    print(f"  Total de registros: {len(df)}")
    print()
    return df


# =============================================================================
#  ETAPA 4 — CÁLCULO DOS ÍNDICES
# =============================================================================

def calcular_indices(df_lulc, df_transicoes):
    """Calcula todos os índices ambientais por município."""
    print("=" * 60)
    print("ETAPA 4 — Cálculo dos índices municipais")
    print("=" * 60)

    indices = []
    municipios = df_lulc["municipio"].unique()
    classes_veg = ["Floresta", "Vegetacao_Natural_Nao_Florestal"]
    classes_antrop = ["Pastagem", "Agricultura", "Mosaico_Agropecuario",
                      "Area_Urbana", "Mineracao", "Silvicultura"]

    for mun in municipios:
        df_m = df_lulc[df_lulc["municipio"] == mun]
        df_t = df_transicoes[df_transicoes["municipio"] == mun]
        cod = df_m["cod_ibge"].iloc[0]
        r = {"municipio": mun, "cod_ibge": cod}

        # Áreas auxiliares
        area_total_2023 = df_m[df_m["ano"] == 2023]["area_ha"].sum()
        area_total_1985 = df_m[df_m["ano"] == 1985]["area_ha"].sum()
        area_veg_2023 = df_m[(df_m["ano"] == 2023) & df_m["classe"].isin(classes_veg)]["area_ha"].sum()
        area_veg_1985 = df_m[(df_m["ano"] == 1985) & df_m["classe"].isin(classes_veg)]["area_ha"].sum()
        area_flor_2010 = df_m[(df_m["ano"] == 2010) & (df_m["classe"] == "Floresta")]["area_ha"].sum()
        area_flor_2023 = df_m[(df_m["ano"] == 2023) & (df_m["classe"] == "Floresta")]["area_ha"].sum()

        # 1. ICV — Índice de Cobertura Vegetal Nativa (%)
        r["ICV_2023_pct"] = (area_veg_2023 / area_total_2023 * 100) if area_total_2023 > 0 else 0

        # 2. Variação da Cobertura Vegetal (1985–2023)
        r["variacao_veg_ha"] = area_veg_2023 - area_veg_1985
        r["variacao_veg_pct"] = ((area_veg_2023 - area_veg_1985) / area_veg_1985 * 100) if area_veg_1985 > 0 else 0

        # 3. Recuperação Florestal (2010–2023)
        r["recup_florestal_2010_2023_ha"] = area_flor_2023 - area_flor_2010
        r["recup_florestal_2010_2023_pct"] = (
            (area_flor_2023 - area_flor_2010) / area_flor_2010 * 100
        ) if area_flor_2010 > 0 else 0
        r["taxa_recup_florestal_ha_ano"] = (area_flor_2023 - area_flor_2010) / 13

        # 4. Pasto → Mata (regeneração)
        def _get_trans(transicao, periodo):
            t = df_t[(df_t["transicao"] == transicao) & (df_t["periodo"] == periodo)]
            return t["area_ha"].sum() if len(t) > 0 else 0

        r["pasto_para_mata_total_ha"] = _get_trans("Pastagem_para_Floresta", "1985-2023")
        r["pasto_para_mata_recente_ha"] = _get_trans("Pastagem_para_Floresta", "2010-2020")

        # 5. Mata → Pasto (desmatamento)
        r["mata_para_pasto_total_ha"] = _get_trans("Floresta_para_Pastagem", "1985-2023")
        r["mata_para_pasto_recente_ha"] = _get_trans("Floresta_para_Pastagem", "2010-2020")

        # 6. Saldo Florestal
        r["saldo_florestal_total_ha"] = r["pasto_para_mata_total_ha"] - r["mata_para_pasto_total_ha"]
        r["saldo_florestal_recente_ha"] = r["pasto_para_mata_recente_ha"] - r["mata_para_pasto_recente_ha"]

        # 7. Crescimento Urbano
        area_urb_1985 = df_m[(df_m["ano"] == 1985) & (df_m["classe"] == "Area_Urbana")]["area_ha"].sum()
        area_urb_2023 = df_m[(df_m["ano"] == 2023) & (df_m["classe"] == "Area_Urbana")]["area_ha"].sum()
        r["cresc_urbano_ha"] = area_urb_2023 - area_urb_1985
        r["cresc_urbano_pct"] = (
            (area_urb_2023 - area_urb_1985) / area_urb_1985 * 100
        ) if area_urb_1985 > 0 else 0
        r["area_urbana_2023_ha"] = area_urb_2023

        # 8. Pressão Antrópica
        area_antrop_2023 = df_m[(df_m["ano"] == 2023) & df_m["classe"].isin(classes_antrop)]["area_ha"].sum()
        area_antrop_1985 = df_m[(df_m["ano"] == 1985) & df_m["classe"].isin(classes_antrop)]["area_ha"].sum()
        r["pressao_antropica_2023_pct"] = (area_antrop_2023 / area_total_2023 * 100) if area_total_2023 > 0 else 0
        r["pressao_antropica_1985_pct"] = (area_antrop_1985 / area_total_1985 * 100) if area_total_1985 > 0 else 0
        r["variacao_pressao_antropica_pp"] = r["pressao_antropica_2023_pct"] - r["pressao_antropica_1985_pct"]

        # 9. Shannon (diversidade de uso)
        areas_2023 = df_m[df_m["ano"] == 2023].groupby("classe")["area_ha"].sum()
        total = areas_2023.sum()
        if total > 0:
            props = areas_2023 / total
            props = props[props > 0]
            r["shannon_2023"] = -np.sum(props * np.log(props))
        else:
            r["shannon_2023"] = 0

        # 10. Eficiência de Regeneração
        if r["mata_para_pasto_total_ha"] > 0:
            r["eficiencia_regeneracao"] = r["pasto_para_mata_total_ha"] / r["mata_para_pasto_total_ha"]
        else:
            r["eficiencia_regeneracao"] = float("inf") if r["pasto_para_mata_total_ha"] > 0 else 1.0

        # 11. Saldo Veg. Nativa ↔ Antrópico
        veg_p_antrop = _get_trans("VegNativa_para_Antropico", "1985-2023")
        antrop_p_veg = _get_trans("Antropico_para_VegNativa", "1985-2023")
        r["saldo_veg_nativa_total_ha"] = antrop_p_veg - veg_p_antrop

        # 12. Variação Agropecuária
        classes_agro = ["Pastagem", "Agricultura", "Mosaico_Agropecuario"]
        area_agro_2023 = df_m[(df_m["ano"] == 2023) & df_m["classe"].isin(classes_agro)]["area_ha"].sum()
        area_agro_1985 = df_m[(df_m["ano"] == 1985) & df_m["classe"].isin(classes_agro)]["area_ha"].sum()
        r["variacao_agropecuaria_ha"] = area_agro_2023 - area_agro_1985
        r["variacao_agropecuaria_pct"] = (
            (area_agro_2023 - area_agro_1985) / area_agro_1985 * 100
        ) if area_agro_1985 > 0 else 0

        # 13. Desmatamento Recente (2020–2023)
        r["desmatamento_recente_ha"] = _get_trans("VegNativa_para_Antropico", "2020-2023")
        r["taxa_desmatamento_recente_ha_ano"] = r["desmatamento_recente_ha"] / 3

        # 14. Variação Água
        area_agua_1985 = df_m[(df_m["ano"] == 1985) & (df_m["classe"] == "Agua")]["area_ha"].sum()
        area_agua_2023 = df_m[(df_m["ano"] == 2023) & (df_m["classe"] == "Agua")]["area_ha"].sum()
        r["variacao_agua_ha"] = area_agua_2023 - area_agua_1985
        r["area_agua_2023_ha"] = area_agua_2023

        # Área total
        r["area_total_na_rh3_ha"] = area_total_2023

        indices.append(r)

    df = pd.DataFrame(indices)
    print(f"  Índices calculados para {len(df)} municípios.")
    print()
    return df


# =============================================================================
#  ETAPA 5 — RANKING
# =============================================================================

def _normalizar(serie, inverter=False):
    """Min-max normalization 0–100. Se inverter, valores menores = score maior."""
    min_val = serie.min()
    max_val = serie.max()
    if max_val == min_val:
        return pd.Series([50.0] * len(serie), index=serie.index)
    n = (serie - min_val) / (max_val - min_val) * 100
    return (100 - n) if inverter else n


def gerar_rankings(df_indices):
    """Gera rankings por categoria de premiação + score composto."""
    print("=" * 60)
    print("ETAPA 5 — Geração dos rankings")
    print("=" * 60)

    rankings = {}

    # Prêmio 1: Município mais Verde
    rankings["municipio_mais_verde"] = df_indices.nlargest(10, "ICV_2023_pct")[
        ["municipio", "ICV_2023_pct", "area_total_na_rh3_ha"]
    ].reset_index(drop=True)

    # Prêmio 2: Maior Recuperação Florestal
    rankings["maior_recuperacao_florestal"] = df_indices.nlargest(10, "recup_florestal_2010_2023_ha")[
        ["municipio", "recup_florestal_2010_2023_ha", "recup_florestal_2010_2023_pct", "taxa_recup_florestal_ha_ano"]
    ].reset_index(drop=True)

    # Prêmio 3: Maior Regeneração (Pasto → Mata)
    rankings["maior_regeneracao"] = df_indices.nlargest(10, "pasto_para_mata_recente_ha")[
        ["municipio", "pasto_para_mata_recente_ha", "pasto_para_mata_total_ha"]
    ].reset_index(drop=True)

    # Prêmio 4: Melhor Saldo Florestal
    rankings["melhor_saldo_florestal"] = df_indices.nlargest(10, "saldo_florestal_recente_ha")[
        ["municipio", "saldo_florestal_recente_ha", "saldo_florestal_total_ha", "eficiencia_regeneracao"]
    ].reset_index(drop=True)

    # Prêmio 5: Menor Pressão Antrópica
    rankings["menor_pressao_antropica"] = df_indices.nsmallest(10, "variacao_pressao_antropica_pp")[
        ["municipio", "pressao_antropica_2023_pct", "pressao_antropica_1985_pct", "variacao_pressao_antropica_pp"]
    ].reset_index(drop=True)

    # Prêmio 6: Menor Desmatamento Recente
    rankings["menor_desmatamento_recente"] = df_indices.nsmallest(10, "desmatamento_recente_ha")[
        ["municipio", "desmatamento_recente_ha", "taxa_desmatamento_recente_ha_ano"]
    ].reset_index(drop=True)

    # Diagnóstico: Crescimento Urbano
    rankings["crescimento_urbano"] = df_indices.nlargest(10, "cresc_urbano_ha")[
        ["municipio", "cresc_urbano_ha", "cresc_urbano_pct", "area_urbana_2023_ha"]
    ].reset_index(drop=True)

    # Diagnóstico: Maior Variação Veg. histórica
    rankings["maior_variacao_veg_historica"] = df_indices.nlargest(10, "variacao_veg_ha")[
        ["municipio", "variacao_veg_ha", "variacao_veg_pct"]
    ].reset_index(drop=True)

    # ---- Score Composto ----
    df_score = df_indices.copy()
    df_score["score_cobertura"] = _normalizar(df_score["ICV_2023_pct"])
    df_score["score_recuperacao"] = _normalizar(df_score["recup_florestal_2010_2023_ha"])
    df_score["score_regeneracao"] = _normalizar(df_score["pasto_para_mata_recente_ha"])
    df_score["score_saldo"] = _normalizar(df_score["saldo_florestal_recente_ha"])
    df_score["score_pressao"] = _normalizar(df_score["variacao_pressao_antropica_pp"], inverter=True)
    df_score["score_desmatamento"] = _normalizar(df_score["desmatamento_recente_ha"], inverter=True)

    pesos = {
        "score_cobertura": 0.20,
        "score_recuperacao": 0.20,
        "score_regeneracao": 0.15,
        "score_saldo": 0.15,
        "score_pressao": 0.15,
        "score_desmatamento": 0.15,
    }
    df_score["score_ambiental"] = sum(df_score[col] * peso for col, peso in pesos.items())

    rankings["ranking_geral"] = df_score.nlargest(len(df_score), "score_ambiental")[
        ["municipio", "score_ambiental", "score_cobertura", "score_recuperacao",
         "score_regeneracao", "score_saldo", "score_pressao", "score_desmatamento",
         "ICV_2023_pct", "area_total_na_rh3_ha"]
    ].reset_index(drop=True)

    print(f"  Rankings gerados: {list(rankings.keys())}")
    print()
    return rankings, df_score


# =============================================================================
#  ETAPA 6 — GRÁFICOS
# =============================================================================

def gerar_graficos(df_lulc, df_indices, rankings):
    """Gera todos os gráficos para o relatório."""
    print("=" * 60)
    print("ETAPA 6 — Geração de gráficos")
    print("=" * 60)

    # 1. Evolução temporal da cobertura florestal (RH3 inteira)
    fig, ax = plt.subplots(figsize=(14, 6))
    df_flor = df_lulc[df_lulc["classe"] == "Floresta"].groupby("ano")["area_ha"].sum()
    ax.plot(df_flor.index, df_flor.values / 1000, "g-o", linewidth=2, markersize=8)
    ax.set_xlabel("Ano", fontsize=12)
    ax.set_ylabel("Área Florestal (mil ha)", fontsize=12)
    ax.set_title("Evolução da Cobertura Florestal na RH3 — Médio Paraíba do Sul", fontsize=14)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig("./output/graficos/evolucao_florestal_rh3.png", dpi=200)
    plt.close()
    print("  [1/4] evolucao_florestal_rh3.png")

    # 2. Top 10 municípios — Score Ambiental
    fig, ax = plt.subplots(figsize=(12, 8))
    top10 = rankings["ranking_geral"].head(10)
    colors = plt.cm.Greens(np.linspace(0.4, 0.9, 10))[::-1]
    bars = ax.barh(range(10), top10["score_ambiental"], color=colors)
    ax.set_yticks(range(10))
    ax.set_yticklabels(top10["municipio"], fontsize=11)
    ax.set_xlabel("Score Ambiental Composto", fontsize=12)
    ax.set_title("Top 10 Municípios — Ranking Ambiental RH3", fontsize=14)
    ax.invert_yaxis()
    for bar, val in zip(bars, top10["score_ambiental"]):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height() / 2,
                f"{val:.1f}", va="center", fontsize=10)
    plt.tight_layout()
    plt.savefig("./output/graficos/ranking_ambiental_top10.png", dpi=200)
    plt.close()
    print("  [2/4] ranking_ambiental_top10.png")

    # 3. Composição LULC por município em 2023 (stacked bar)
    df_2023 = df_lulc[df_lulc["ano"] == 2023].pivot_table(
        index="municipio", columns="classe", values="area_ha", fill_value=0
    )
    df_2023_pct = df_2023.div(df_2023.sum(axis=1), axis=0) * 100
    if "Floresta" in df_2023_pct.columns:
        df_2023_pct = df_2023_pct.sort_values("Floresta", ascending=True)

    cols_plot = [c for c in CORES_CLASSES if c in df_2023_pct.columns]
    n_munic = len(df_2023_pct)
    fig, ax = plt.subplots(figsize=(16, max(10, n_munic * 0.35)))
    df_2023_pct[cols_plot].plot(
        kind="barh", stacked=True, ax=ax,
        color=[CORES_CLASSES[c] for c in cols_plot],
    )
    ax.set_xlabel("Cobertura (%)", fontsize=12)
    ax.set_title("Composição do Uso e Cobertura do Solo por Município (2023) — RH3", fontsize=14)
    ax.legend(bbox_to_anchor=(1.02, 1), loc="upper left", fontsize=9)
    plt.tight_layout()
    plt.savefig("./output/graficos/composicao_lulc_municipios_2023.png", dpi=200, bbox_inches="tight")
    plt.close()
    print("  [3/4] composicao_lulc_municipios_2023.png")

    # 4. Saldo florestal por município (barra divergente)
    df_saldo = df_indices[["municipio", "saldo_florestal_total_ha"]].sort_values("saldo_florestal_total_ha")
    fig, ax = plt.subplots(figsize=(14, max(10, len(df_saldo) * 0.35)))
    cores = ["#d4271e" if x < 0 else "#1f8d49" for x in df_saldo["saldo_florestal_total_ha"]]
    ax.barh(range(len(df_saldo)), df_saldo["saldo_florestal_total_ha"], color=cores)
    ax.set_yticks(range(len(df_saldo)))
    ax.set_yticklabels(df_saldo["municipio"], fontsize=8)
    ax.axvline(x=0, color="black", linewidth=0.8)
    ax.set_xlabel("Saldo Florestal (ha) — Regeneração - Desmatamento", fontsize=12)
    ax.set_title("Saldo Florestal por Município (1985–2023) — RH3", fontsize=14)
    plt.tight_layout()
    plt.savefig("./output/graficos/saldo_florestal_municipios.png", dpi=200)
    plt.close()
    print("  [4/4] saldo_florestal_municipios.png")
    print()


# =============================================================================
#  ETAPA 7 — EXPORTAÇÃO
# =============================================================================

def exportar_resultados(df_indices, rankings, df_lulc, df_transicoes):
    """Exporta todos os resultados (CSVs + Excel consolidado)."""
    print("=" * 60)
    print("ETAPA 7 — Exportação dos resultados")
    print("=" * 60)

    enc = "utf-8-sig"

    # CSVs
    df_indices.to_csv("./output/tabelas/indices_municipais_rh3.csv", index=False, encoding=enc)
    df_lulc.to_csv("./output/tabelas/lulc_completo_rh3.csv", index=False, encoding=enc)
    df_transicoes.to_csv("./output/tabelas/transicoes_completas_rh3.csv", index=False, encoding=enc)

    for nome, df_rank in rankings.items():
        df_rank.to_csv(f"./output/tabelas/ranking_{nome}.csv", index=False, encoding=enc)

    # Excel consolidado
    with pd.ExcelWriter("./output/ranking_ambiental_rh3.xlsx", engine="openpyxl") as writer:
        df_indices.to_excel(writer, sheet_name="Indices_Completos", index=False)
        rankings["ranking_geral"].to_excel(writer, sheet_name="Ranking_Geral", index=False)
        rankings["municipio_mais_verde"].to_excel(writer, sheet_name="Mais_Verde", index=False)
        rankings["maior_recuperacao_florestal"].to_excel(writer, sheet_name="Recuperacao_Florestal", index=False)
        rankings["maior_regeneracao"].to_excel(writer, sheet_name="Regeneracao", index=False)
        rankings["melhor_saldo_florestal"].to_excel(writer, sheet_name="Saldo_Florestal", index=False)
        rankings["menor_pressao_antropica"].to_excel(writer, sheet_name="Menor_Pressao", index=False)
        rankings["menor_desmatamento_recente"].to_excel(writer, sheet_name="Menor_Desmatamento", index=False)
        rankings["crescimento_urbano"].to_excel(writer, sheet_name="Cresc_Urbano", index=False)

    print("  Excel: ./output/ranking_ambiental_rh3.xlsx")
    print("  CSVs:  ./output/tabelas/")
    print()


# =============================================================================
#  MAIN
# =============================================================================

def main():
    print()
    print("=" * 60)
    print("  ANALISE LULC -- RH3 MEDIO PARAIBA DO SUL")
    print("  MapBiomas Colecao 9 - 1985-2023")
    print("  Ranking Municipal -- Premiacao CEIVAP")
    print("=" * 60)
    print()

    # 1. Inicializar GEE
    print("Inicializando Google Earth Engine...")
    ee.Initialize(project=PROJETO_GEE)
    print("  GEE OK.\n")

    # 2. Preparar dados vetoriais (clip municípios pela RH3)
    munic_rh3_gdf = preparar_municipios_rh3()

    # 3. Converter para FeatureCollection do GEE
    print("Convertendo geometrias para GEE...")
    # Reprojetar para WGS84 (GEE espera lon/lat)
    munic_rh3_wgs = munic_rh3_gdf.to_crs(epsg=4326)
    municipios_fc = geemap.gdf_to_ee(munic_rh3_wgs)
    print(f"  FeatureCollection com {municipios_fc.size().getInfo()} feições.\n")

    # 4. Carregar MapBiomas
    mapbiomas = ee.Image(
        "projects/mapbiomas-public/assets/brazil/lulc/collection9/"
        "mapbiomas_collection90_integration_v1"
    )

    # 5. Extrair LULC
    df_lulc = extrair_lulc_todos_anos(municipios_fc, mapbiomas, ANOS_MARCOS)

    # 6. Extrair transições
    df_transicoes = extrair_transicoes_todos_periodos(municipios_fc, mapbiomas, PERIODOS_TRANSICAO)

    # 7. Calcular índices
    df_indices = calcular_indices(df_lulc, df_transicoes)

    # 8. Gerar rankings
    rankings, df_score = gerar_rankings(df_indices)

    # 9. Gráficos
    gerar_graficos(df_lulc, df_indices, rankings)

    # 10. Exportar
    exportar_resultados(df_indices, rankings, df_lulc, df_transicoes)

    print("=" * 60)
    print("ANÁLISE CONCLUÍDA COM SUCESSO!")
    print("=" * 60)
    print()
    print("Top 5 — Ranking Geral:")
    top5 = rankings["ranking_geral"].head(5)
    for i, row in top5.iterrows():
        print(f"  {i+1}. {row['municipio']:30s} Score: {row['score_ambiental']:.1f}  ICV: {row['ICV_2023_pct']:.1f}%")
    print()


if __name__ == "__main__":
    main()
