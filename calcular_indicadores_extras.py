"""
Calcula 4 indicadores extras para o Score Composto v2 e mescla no CSV principal:

  1. Persistencia Florestal 1985-2023 — area que foi floresta em TODOS os 9 anos-marco
  2. Estabilidade do Uso 1985 vs 2023 — area com a mesma classe nos dois extremos
  3. Maior Fragmento Florestal 2023 — area do maior remanescente continuo de floresta
  4. Densidade de Fragmentos Florestais 2023 — numero de patches por 1000 ha

Saidas:
  output/tabelas/indicadores_extras_rh3.csv
  Adiciona colunas ao indices_municipais_rh3.csv (mantendo as existentes).
"""
import io
import json
import time
from pathlib import Path

import ee
import geemap
import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import requests
from rasterio.io import MemoryFile
from scipy import ndimage

# =============================================================================
#  CONFIG
# =============================================================================

PROJETO_GEE = "ggeantigravity"
ASSET_MB = (
    "projects/mapbiomas-public/assets/brazil/lulc/collection9/"
    "mapbiomas_collection90_integration_v1"
)
ANOS_MARCO = [1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2023]
FLORESTA = [3, 4, 5, 6, 49]
SCALE_M = 30
PIXEL_HA = (SCALE_M * SCALE_M) / 10000.0  # 0.09 ha por pixel

SHP_MUNIC = "data/municipios_clipped_rh3.shp"
CSV_INDICES = "output/tabelas/indices_municipais_rh3.csv"
CSV_EXTRAS = "output/tabelas/indicadores_extras_rh3.csv"
TMP_RASTERS = Path("output/rasters_tmp")


# =============================================================================
#  HELPERS
# =============================================================================


def _mascara_classes(classificacao, classe_ids):
    """Mascara binaria para uma lista de IDs de classe."""
    mascara = classificacao.eq(classe_ids[0])
    for cid in classe_ids[1:]:
        mascara = mascara.Or(classificacao.eq(cid))
    return mascara


def calcular_persistencia_estabilidade(municipios_fc, img_mb):
    """
    Calcula via GEE, em uma unica reduceRegions empilhada:
      - persistencia_florestal_ha : pixel foi floresta em todos os 9 anos-marco
      - estabilidade_uso_ha       : classe 1985 == classe 2023 (qualquer classe)
    """
    print("  [GEE] Calculando persistencia florestal e estabilidade...")
    pixel_area = ee.Image.pixelArea().divide(10000)

    # Persistencia: AND logico das mascaras de floresta em todos os anos
    mascara_persist = _mascara_classes(
        img_mb.select(f"classification_{ANOS_MARCO[0]}"), FLORESTA
    )
    for ano in ANOS_MARCO[1:]:
        m = _mascara_classes(img_mb.select(f"classification_{ano}"), FLORESTA)
        mascara_persist = mascara_persist.And(m)

    img_persist = pixel_area.updateMask(mascara_persist).rename("persistencia_florestal_ha")

    # Estabilidade: mesma classe em 1985 e 2023
    class_85 = img_mb.select("classification_1985")
    class_23 = img_mb.select("classification_2023")
    mascara_estab = class_85.eq(class_23)
    img_estab = pixel_area.updateMask(mascara_estab).rename("estabilidade_uso_ha")

    img_stack = ee.Image([img_persist, img_estab])
    stats = img_stack.reduceRegions(
        collection=municipios_fc,
        reducer=ee.Reducer.sum(),
        scale=SCALE_M,
        crs="EPSG:4326",
    )

    feats = stats.getInfo()["features"]
    out = []
    for f in feats:
        p = f["properties"]
        out.append({
            "cod_ibge": str(p.get("CD_MUN", "")),
            "municipio": p.get("NM_MUN", ""),
            "persistencia_florestal_ha": float(p.get("persistencia_florestal_ha", 0) or 0),
            "estabilidade_uso_ha": float(p.get("estabilidade_uso_ha", 0) or 0),
        })
    return pd.DataFrame(out)


def baixar_mascara_floresta_2023(geom_ee, dimensoes=2048, retries=3):
    """
    Baixa GeoTIFF (uint8) da mascara binaria de floresta 2023 para a geometria.
    1 = floresta, 0 = nao-floresta (ou fora da mascara).
    """
    img_mb = ee.Image(ASSET_MB)
    classif = img_mb.select("classification_2023")
    mascara = _mascara_classes(classif, FLORESTA).clip(geom_ee).unmask(0).toUint8()

    params = {
        "region": geom_ee,
        "scale": SCALE_M,
        "crs": "EPSG:31983",
        "format": "GEO_TIFF",
        "filePerBand": False,
    }

    last_err = None
    for tentativa in range(retries):
        try:
            url = mascara.getDownloadURL(params)
            resp = requests.get(url, timeout=300)
            resp.raise_for_status()
            return resp.content
        except Exception as e:
            last_err = e
            time.sleep(2 + tentativa * 2)
    raise RuntimeError(f"Falha ao baixar mascara: {last_err}")


def analisar_fragmentacao(tif_bytes):
    """
    Aplica scipy.ndimage.label sobre mascara binaria de floresta.
    Retorna (maior_fragmento_ha, num_fragmentos, area_total_ha).
    """
    with MemoryFile(tif_bytes) as memfile:
        with memfile.open() as src:
            arr = src.read(1)

    # Mascara binaria: True onde floresta
    binaria = arr == 1

    # 8-conectividade (vizinhos diagonais tambem contam) — mais permissivo
    estrutura = np.ones((3, 3), dtype=bool)
    labels, n = ndimage.label(binaria, structure=estrutura)
    if n == 0:
        return 0.0, 0, 0.0

    # Tamanho de cada componente em pixels
    tamanhos_px = ndimage.sum(binaria, labels, index=range(1, n + 1))
    tamanhos_ha = tamanhos_px * PIXEL_HA
    maior_ha = float(tamanhos_ha.max())
    area_total_ha = float(tamanhos_ha.sum())
    return maior_ha, int(n), area_total_ha


def calcular_fragmentacao_municipios(gdf_munic):
    """
    Itera por municipio, baixa raster de mascara floresta 2023 e calcula
    maior fragmento + numero de fragmentos.
    """
    print("  [GEE+local] Baixando rasters e calculando fragmentacao...")
    TMP_RASTERS.mkdir(parents=True, exist_ok=True)

    # GDF ja vem em EPSG:31983 (UTM 23S); reprojetar para WGS84 so para geometria do GEE
    gdf_wgs = gdf_munic.to_crs(epsg=4326)

    resultados = []
    n_mun = len(gdf_munic)
    for i, (_, row) in enumerate(gdf_munic.iterrows(), 1):
        mun = row["NM_MUN"]
        cod = str(row["CD_MUN"])

        # Geometria para GEE (WGS84)
        row_wgs = gdf_wgs[gdf_wgs["CD_MUN"] == row["CD_MUN"]].iloc[0]
        geom_geojson = row_wgs.geometry.__geo_interface__
        if geom_geojson["type"] == "Polygon":
            geom_ee = ee.Geometry.Polygon(geom_geojson["coordinates"])
        else:
            geom_ee = ee.Geometry.MultiPolygon(geom_geojson["coordinates"])

        print(f"    [{i}/{n_mun}] {mun}...", end=" ", flush=True)
        cache_path = TMP_RASTERS / f"floresta_2023_{cod}.tif"
        if cache_path.exists():
            tif_bytes = cache_path.read_bytes()
            print("(cache)", end=" ")
        else:
            tif_bytes = baixar_mascara_floresta_2023(geom_ee)
            cache_path.write_bytes(tif_bytes)

        maior_ha, n_frag, area_flor_ha = analisar_fragmentacao(tif_bytes)
        densidade = (n_frag / row["area_na_rh3_ha"] * 1000.0) if row["area_na_rh3_ha"] > 0 else 0.0

        resultados.append({
            "cod_ibge": cod,
            "municipio": mun,
            "maior_fragmento_florestal_ha": maior_ha,
            "num_fragmentos_florestais": n_frag,
            "densidade_fragmentos_por_kha": densidade,
            "area_florestal_2023_calc_ha": area_flor_ha,
        })
        print(f"maior={maior_ha:.0f} ha, n={n_frag}, dens={densidade:.2f}/kha")

    return pd.DataFrame(resultados)


# =============================================================================
#  MAIN
# =============================================================================


def main():
    print("=" * 60)
    print("  INDICADORES EXTRAS — Persistencia, Estabilidade, Fragmentacao")
    print("=" * 60)

    print("Inicializando GEE...")
    ee.Initialize(project=PROJETO_GEE)
    print("  GEE OK.\n")

    # Carregar municipios (EPSG:31983)
    print("Carregando municipios clipados da RH3...")
    gdf_munic = gpd.read_file(SHP_MUNIC, encoding="utf-8")
    if "area_na_rh3_ha" not in gdf_munic.columns:
        gdf_munic["area_na_rh3_ha"] = gdf_munic.geometry.area / 1e4
    print(f"  {len(gdf_munic)} municipios.\n")

    # FeatureCollection para reducao do GEE (persistencia + estabilidade)
    gdf_wgs = gdf_munic.to_crs(epsg=4326)
    municipios_fc = geemap.gdf_to_ee(gdf_wgs)
    img_mb = ee.Image(ASSET_MB)

    # 1+2: Persistencia + Estabilidade (GEE puro)
    df_gee = calcular_persistencia_estabilidade(municipios_fc, img_mb)

    # 3+4: Fragmentacao (GEE para download, scipy local)
    df_frag = calcular_fragmentacao_municipios(gdf_munic)

    # Merge dos extras
    df_extras = df_gee.merge(df_frag, on=["cod_ibge", "municipio"], how="outer")

    # Calcular percentuais (relativos a area do municipio na RH3)
    gdf_area = gdf_munic[["CD_MUN", "area_na_rh3_ha"]].copy()
    gdf_area["cod_ibge"] = gdf_area["CD_MUN"].astype(str)
    df_extras = df_extras.merge(
        gdf_area[["cod_ibge", "area_na_rh3_ha"]],
        on="cod_ibge",
        how="left",
    )
    df_extras["persistencia_florestal_pct"] = (
        df_extras["persistencia_florestal_ha"] / df_extras["area_na_rh3_ha"] * 100
    ).fillna(0)
    df_extras["estabilidade_uso_pct"] = (
        df_extras["estabilidade_uso_ha"] / df_extras["area_na_rh3_ha"] * 100
    ).fillna(0)
    df_extras = df_extras.drop(columns=["area_na_rh3_ha"])

    # Salvar CSV de extras
    Path("output/tabelas").mkdir(parents=True, exist_ok=True)
    df_extras.to_csv(CSV_EXTRAS, index=False, encoding="utf-8-sig")
    print(f"\nSalvo: {CSV_EXTRAS}")

    # Mesclar com indices_municipais_rh3.csv
    print(f"\nMesclando com {CSV_INDICES}...")
    df_idx = pd.read_csv(CSV_INDICES, dtype={"cod_ibge": str})
    df_extras["cod_ibge"] = df_extras["cod_ibge"].astype(str)

    cols_novas = [
        "persistencia_florestal_ha",
        "persistencia_florestal_pct",
        "estabilidade_uso_ha",
        "estabilidade_uso_pct",
        "maior_fragmento_florestal_ha",
        "num_fragmentos_florestais",
        "densidade_fragmentos_por_kha",
        "area_florestal_2023_calc_ha",
    ]
    # Remover colunas se ja existem (re-execucao)
    for col in cols_novas:
        if col in df_idx.columns:
            df_idx = df_idx.drop(columns=col)

    df_idx = df_idx.merge(
        df_extras[["cod_ibge"] + cols_novas],
        on="cod_ibge",
        how="left",
    )

    df_idx.to_csv(CSV_INDICES, index=False, encoding="utf-8-sig")
    print(f"  {CSV_INDICES} atualizado com {len(cols_novas)} colunas novas.")

    # Resumo
    print("\n" + "=" * 60)
    print("RESUMO DOS INDICADORES EXTRAS")
    print("=" * 60)
    resumo = df_extras[[
        "municipio",
        "persistencia_florestal_pct",
        "estabilidade_uso_pct",
        "maior_fragmento_florestal_ha",
        "num_fragmentos_florestais",
        "densidade_fragmentos_por_kha",
    ]].sort_values("persistencia_florestal_pct", ascending=False)
    print(resumo.to_string(index=False))
    print()


if __name__ == "__main__":
    main()
