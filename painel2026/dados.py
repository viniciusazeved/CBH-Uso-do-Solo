"""Leitura dos dados do painel, da pasta painel_dados/ (montada pelo pipeline/24_dados_painel.py).

O Ranking Ambiental 2026 só aparece quando painel_dados/ranking/ existe: a versão pública do repositório
não leva essa pasta antes do anúncio no XI Simpósio Água Boa (30/10/2026).
"""

from __future__ import annotations

import base64
import json
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

RAIZ = Path(__file__).resolve().parents[1]
DIR = RAIZ / "painel_dados"
RH3 = 0                       # código da linha da bacia inteira nas tabelas do panorama
PORCAO_PEQUENA = {3304409: "Rio Claro", 3302908: "Miguel Pereira", 3302809: "Mendes"}


def _versao(caminho: Path) -> int:
    """Data do arquivo na chave do cache: dado regravado aparece sem reiniciar o servidor."""
    return caminho.stat().st_mtime_ns


@st.cache_data(show_spinner=False)
def _csv(caminho: str, versao: int) -> pd.DataFrame:
    return pd.read_csv(caminho)


@st.cache_data(show_spinner=False)
def _json(caminho: str, versao: int) -> dict:
    return json.loads(Path(caminho).read_text(encoding="utf-8"))


def tabela(nome: str) -> pd.DataFrame:
    arq = DIR / "panorama" / nome
    return _csv(str(arq), _versao(arq))


def resumo() -> dict:
    arq = DIR / "panorama" / "resumo_rh3.json"
    return _json(str(arq), _versao(arq))


def celular() -> bool:
    """Navegador de celular pelo User-Agent (para enquadrar o mapa na tela estreita)."""
    try:
        ua = st.context.headers.get("User-Agent", "") or ""
    except Exception:  # noqa: BLE001  (fora de uma sessão, por exemplo em teste)
        return False
    return any(m in ua for m in ("Mobi", "Android", "iPhone"))


def ordem_alfabetica(nome: str) -> str:
    """Chave de ordenação sem acento e sem caixa: Barra do Piraí antes de Barra Mansa."""
    return unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode().casefold()


def municipios() -> pd.DataFrame:
    """Os 19 municípios em ordem alfabética: área na RH-III e inserção (território e área urbana de 2025)."""
    m = tabela("municipios_resumo.csv")
    m = m.loc[m["cod_ibge"] != RH3, ["cod_ibge", "municipio", "area_na_rh3_ha"]]
    ins = tabela("insercao_municipios_rh3.csv").rename(columns={"CD_MUN": "cod_ibge"})
    ins = ins[["cod_ibge", "area_total_ha", "pct_territorio_na_rh3", "pct_urbano_na_rh3"]]
    m = m.merge(ins, on="cod_ibge", how="left")
    return m.sort_values("municipio", key=lambda s: s.map(ordem_alfabetica)).reset_index(drop=True)


def ranking_disponivel() -> bool:
    return (DIR / "ranking" / "decisao.json").exists()


def ranking(nome: str) -> pd.DataFrame | dict:
    arq = DIR / "ranking" / nome
    return _json(str(arq), _versao(arq)) if arq.suffix == ".json" else _csv(str(arq), _versao(arq))


def geojson(nome: str) -> dict:
    arq = DIR / f"{nome}.geojson"
    return _json(str(arq), _versao(arq))


def caixa() -> dict:
    arq = DIR / "mapas" / "caixa.json"
    return _json(str(arq), _versao(arq))


@st.cache_data(show_spinner=False)
def _data_uri(caminho: str, versao: int) -> str:
    return "data:image/png;base64," + base64.b64encode(Path(caminho).read_bytes()).decode()


def imagem_mapa(nome: str) -> str:
    """PNG da pasta mapas/ como data URI (fonte da camada de imagem do mapa)."""
    arq = DIR / "mapas" / f"{nome}.png"
    return _data_uri(str(arq), _versao(arq))


def arquivo(sub: str, nome: str) -> bytes:
    return (DIR / sub / nome).read_bytes()
