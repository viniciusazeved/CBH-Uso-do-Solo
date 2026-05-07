"""
Gera PNGs georeferenciados do MapBiomas Colecao 9 (1985 e 2023) clipados pela RH3
para uso como ImageOverlay no painel Streamlit.

Saidas:
  output/mapas/lulc_1985.png
  output/mapas/lulc_2023.png
  output/mapas/bbox.json   (bounding box em WGS84 + paleta usada)
"""
import json
from pathlib import Path

import ee
import geopandas as gpd
import requests

PROJETO_GEE = "ggeantigravity"
ASSET_MB = "projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1"
ANOS = [1985, 2023]
DIMENSOES = 1600
SHP_RH3 = "shp/RH_III.shp"
OUT_DIR = Path("output/mapas")

# Paleta MapBiomas Colecao 9 — apenas as classes presentes na nossa agregacao
# (mantemos chaves usadas em main.py)
PALETA_MB = {
    1: "#32a65e",
    3: "#1f8d49",   # Floresta
    4: "#7dc975",   # Savanica
    5: "#04381d",   # Mangue
    6: "#026975",   # Floresta alagavel
    9: "#7a5900",   # Silvicultura
    10: "#d6bc74",
    11: "#519799",
    12: "#d6bc74",  # Veg. Nao Florestal
    13: "#d89f5c",
    14: "#ffffb2",
    15: "#edde8e",  # Pastagem
    18: "#e974ed",  # Agricultura
    19: "#c27ba0",
    20: "#db7093",
    21: "#ffefc3",  # Mosaico Agropecuario
    22: "#d4271e",
    23: "#ffa07a",
    24: "#d4271e",  # Area Urbana
    25: "#db4d4f",
    26: "#0000ff",  # Agua
    29: "#ffaa5f",
    30: "#9c0027",  # Mineracao
    31: "#091077",  # Aquicultura
    32: "#fc8114",
    33: "#0000ff",
    35: "#9065d0",
    36: "#d082de",
    39: "#f5b3c8",
    40: "#c71585",
    41: "#f54ca9",
    46: "#d68fe2",
    47: "#9932cc",
    48: "#e6ccff",
    49: "#02d659",  # Restinga arborea
    50: "#ad5100",
}


def main():
    ee.Initialize(project=PROJETO_GEE)

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # RH3 em WGS84
    rh3 = gpd.read_file(SHP_RH3).to_crs(epsg=4326)
    geom_geojson = json.loads(gpd.GeoSeries([rh3.geometry.union_all()]).to_json())
    coords = geom_geojson["features"][0]["geometry"]["coordinates"]
    geom_type = geom_geojson["features"][0]["geometry"]["type"]
    if geom_type == "Polygon":
        rh3_ee = ee.Geometry.Polygon(coords)
    else:
        rh3_ee = ee.Geometry.MultiPolygon(coords)

    minx, miny, maxx, maxy = rh3.total_bounds
    region = ee.Geometry.Rectangle([minx, miny, maxx, maxy])

    # Remap das classes presentes para indices contiguos (0 = nao mapeado)
    classes_presentes = sorted(PALETA_MB.keys())
    remap_new = list(range(1, len(classes_presentes) + 1))
    paleta_lista = ["#ffffff"] + [PALETA_MB[c] for c in classes_presentes]

    img_mb = ee.Image(ASSET_MB)

    for ano in ANOS:
        print(f"Gerando {ano}...")
        banda = f"classification_{ano}"
        img = img_mb.select(banda).clip(rh3_ee)
        img_remap = img.remap(classes_presentes, remap_new, 0)
        img_rgb = img_remap.visualize(
            min=0,
            max=len(classes_presentes),
            palette=paleta_lista,
        )

        url = img_rgb.getThumbURL({
            "region": region,
            "dimensions": DIMENSOES,
            "format": "png",
        })
        print(f"  URL: {url[:80]}...")

        resp = requests.get(url, timeout=120)
        resp.raise_for_status()
        out_png = OUT_DIR / f"lulc_{ano}.png"
        out_png.write_bytes(resp.content)
        print(f"  Salvo: {out_png} ({len(resp.content) / 1024:.1f} KB)")

    bbox_data = {
        "south": float(miny),
        "north": float(maxy),
        "west": float(minx),
        "east": float(maxx),
        "anos": ANOS,
        "fonte": "MapBiomas Colecao 9",
    }
    (OUT_DIR / "bbox.json").write_text(json.dumps(bbox_data, indent=2))
    print(f"Bbox salvo em {OUT_DIR / 'bbox.json'}")


if __name__ == "__main__":
    main()
