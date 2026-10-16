"""Contas da página do Ranking Ambiental 2026, iguais às das fichas técnicas (pipeline/20_fichas_contraditorio.py):
mediana dos 16 elegíveis e comparação com a mediana. As faixas do protocolo (seção 6) chegam prontas na publicação
(painel_dados/ranking/indicadores_19_publicacao.csv), que não traz índice nem posição do caso-base."""

from __future__ import annotations

import pandas as pd

from . import dados
from .estilo import fmt

# (coluna, frente, nome, unidade e sentido, casas, menor é melhor)
INDICADORES = [
    ("P1", "Proteger", "Supressão de floresta, 2017 a 2024", "% ao ano; menor é melhor", 3, True),
    ("R1", "Restaurar", "Regeneração persistente, coortes 2017 a 2022",
     "%; maior é melhor; com o desconto da auditoria", 3, False),
    ("A1", "Abastecer", "Recuperação ripária, 2015 a 2024", "% do déficit de 2015; maior é melhor", 2, False),
    ("A2", "Abastecer", "Cobertura nativa ripária em 2024", "% da faixa; maior é melhor", 1, False),
]
SIMBOLO = {"melhor que a mediana": "▲", "pior que a mediana": "▼", "igual à mediana": "="}
FAIXAS = ["Destaque", "4º ao 6º no caso-base", "Demais elegíveis", "Porção pequena na RH-III"]


def tabela() -> pd.DataFrame:
    t = dados.ranking("indicadores_19_publicacao.csv")
    return t.sort_values("municipio", key=lambda s: s.map(dados.ordem_alfabetica)).reset_index(drop=True)


def medianas(t: pd.DataFrame) -> dict:
    eleg = t[t["elegivel"]]
    return {col: float(eleg[col].median()) for col, *_ in INDICADORES}


def comparar(valor: float, mediana: float, menor_melhor: bool) -> str:
    if abs(valor - mediana) < 1e-9:
        return "igual à mediana"
    melhor = valor < mediana if menor_melhor else valor > mediana
    return "melhor que a mediana" if melhor else "pior que a mediana"


def decisao() -> dict:
    return dados.ranking("decisao.json")


def faixas(t: pd.DataFrame) -> dict[int, str]:
    return dict(zip(t["cod_ibge"], t["faixa"]))


def frequencias(t: pd.DataFrame) -> pd.Series:
    return t.set_index("cod_ibge")["freq_top3"]


def postos(linha: pd.Series) -> dict[str, float] | None:
    if not linha["elegivel"]:
        return None
    return {k: float(linha[f"posto_{k}"]) for k in ("P1", "R1", "A1", "A2")}


def posto_txt(p: float) -> str:
    return f"{fmt(p, 1)}º" if p % 1 else f"{int(p)}º"


def travas(linha: pd.Series) -> str:
    """Motivo das travas do caso-base, em texto corrido; vazio se não houver."""
    motivos = []
    if linha["trava_perda_floresta"]:
        motivos.append(f"perdeu {fmt(linha['perda_floresta_pct'], 2)}% da floresta, acima do limite de 0,5%")
    if linha["trava_desmatamento"]:
        vezes = "vezes" if linha["razao_p1_regional"] >= 2 else "vez"
        motivos.append(f"teve supressão de {fmt(linha['razao_p1_regional'], 2)} {vezes} a taxa da bacia, acima do limite de 1,5")
    return ", e ".join(motivos)
