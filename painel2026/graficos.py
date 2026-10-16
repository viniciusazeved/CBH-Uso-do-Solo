"""Gráficos do painel. Os do panorama são os do pipeline/12_graficos.py (mesmos dados, cores e leitura),
com o código do município como parâmetro (0 = RH-III inteira) e o título no texto da página."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go

from .estilo import (AUMENTO, BOM, COR, CRITICO, DESTAQUE, EIXO, FUNDO, GRADE, GRUPOS, NEUTRO, OUTROS, REDUCAO,
                     TINTA, TINTA_2, TINTA_FRACA, VERDE_RAMPA, base, fmt, nome)

ORDEM = [v[0] for v in GRUPOS.values()] + [OUTROS[0]]
CURTO = {"Vegetação herbácea e arbustiva": "Herbácea e arbustiva"}
QUEBRA = {"Vegetação herbácea e arbustiva": "Vegetação herbácea<br>e arbustiva"}


def _unidade(valores) -> tuple[float, str]:
    """mil ha quando o maior valor passa de 1.000 ha; senão, ha."""
    m = float(np.nanmax(np.abs(np.asarray(valores, dtype=float)))) if len(valores) else 0.0
    return (1000.0, "mil ha") if m >= 1000 else (1.0, "ha")


def composicao(comp: pd.DataFrame, cod: int = 0, altura: int = 440) -> go.Figure:
    c = comp[comp["cod_ibge"] == cod].pivot_table(index="ano", columns="grupo", values="pct", fill_value=0)
    outros = c.drop(columns=[g for g in GRUPOS if g in c]).sum(axis=1)
    series = [(rot, cor, c[g] if g in c else outros * 0) for g, (rot, cor) in GRUPOS.items()]
    series.append((OUTROS[0], OUTROS[1], outros))
    fig = go.Figure()
    for rot, cor, s in series:
        fig.add_trace(go.Scatter(x=s.index, y=s.values, name=rot, stackgroup="um", mode="lines",
                                 line={"width": 1, "color": FUNDO}, fillcolor=cor,
                                 hovertemplate=f"{rot}: %{{y:.1f}}%<extra></extra>"))
    acum = 0.0
    for rot, _, s in series:          # rótulo direto nas duas classes que contam a história
        meio = acum + s.iloc[-1] / 2
        acum += s.iloc[-1]
        if rot in ("Floresta", "Pastagem") and s.iloc[-1] >= 6:
            fig.add_annotation(x=2025, y=meio, text=f"{rot} {fmt(s.iloc[-1], 1)}%", showarrow=False,
                               xanchor="right", xshift=-8, bgcolor="rgba(252,252,251,0.88)", borderpad=3,
                               font={"size": 15, "color": TINTA})
    fig.update_yaxes(range=[0, 100], ticksuffix="%")
    fig.update_xaxes(range=[1984.5, 2025.5], tickvals=[1985, 1995, 2005, 2015, 2025], tickangle=0)
    fig.update_layout(hovermode="x unified", showlegend=False)
    return base(fig, altura, margem={"r": 16})


def mudanca_liquida(comp: pd.DataFrame, cod: int = 0, altura: int = 360) -> go.Figure:
    c = comp[comp["cod_ibge"] == cod].pivot_table(index="ano", columns="grupo", values="area_ha", fill_value=0)
    d = (c.loc[2025] - c.loc[1985]).rename(index=nome).groupby(level=0).sum()
    k, un = _unidade(d.values)
    d = d / k
    d = d[d.abs() >= (0.05 if k > 1 else 1)].sort_values()
    cores = [AUMENTO if v > 0 else REDUCAO for v in d.values]
    casas = 1 if k > 1 else 0
    fig = go.Figure(go.Bar(x=d.values, y=[QUEBRA.get(i, i) for i in d.index], orientation="h", marker={"color": cores},
                           text=[fmt(v, casas, sinal=True) for v in d.values], textposition="outside",
                           textfont={"size": 15, "color": TINTA}, cliponaxis=False,
                           customdata=list(d.index),
                           hovertemplate=f"%{{customdata}}: %{{x:.{casas}f}} {un}<extra></extra>"))
    folga = 0.45 * (d.max() - d.min()) if len(d) else 1   # espaço para o rótulo fora da barra, também no celular
    fig.update_xaxes(title=un, showgrid=True, gridcolor=GRADE, zeroline=True,
                     zerolinecolor=EIXO, range=[min(d.min(), 0) - folga, max(d.max(), 0) + folga])
    fig.update_yaxes(showgrid=False)
    fig.update_layout(bargap=0.4, showlegend=False)
    return base(fig, altura)


def sankey(trans: pd.DataFrame, cod: int = 0, periodo: str = "1985-2025", altura: int = 520) -> go.Figure:
    t = trans[(trans["cod_ibge"] == cod) & (trans["periodo"] == periodo)].copy()
    t["de"], t["para"] = t["de"].map(nome), t["para"].map(nome)
    t = t[t["de"] != t["para"]].groupby(["de", "para"], as_index=False)["area_ha"].sum()
    minimo = 300 if cod == 0 else max(5.0, 0.01 * t["area_ha"].sum())
    t = t[t["area_ha"] >= minimo]
    k, un = _unidade(t["area_ha"].values)
    nos = [f"{n} ({periodo[:4]})" for n in ORDEM] + [f"{n} ({periodo[-4:]})" for n in ORDEM]
    idx = {n: i for i, n in enumerate(nos)}

    def rgba(h: str, a: float) -> str:
        return f"rgba({int(h[1:3], 16)},{int(h[3:5], 16)},{int(h[5:7], 16)},{a})"

    casas = 1 if k > 1 else 0
    fig = go.Figure(go.Sankey(
        arrangement="snap",
        node={"label": [CURTO.get(n.rsplit(" (", 1)[0], n.rsplit(" (", 1)[0]) for n in nos], "pad": 14,
              "thickness": 16, "color": [COR[n.rsplit(" (", 1)[0]] for n in nos], "line": {"width": 0},
              "customdata": [n.rsplit(" (", 1)[0] for n in nos],
              "hovertemplate": "%{customdata}: %{value:." + str(casas) + "f} " + un + "<extra></extra>"},
        link={"source": [idx[f"{d} ({periodo[:4]})"] for d in t["de"]],
              "target": [idx[f"{p} ({periodo[-4:]})"] for p in t["para"]],
              "value": (t["area_ha"] / k).round(2).tolist(), "color": [rgba(COR[d], 0.45) for d in t["de"]],
              "customdata": [f"{d} para {p}" for d, p in zip(t["de"], t["para"])],
              "hovertemplate": "%{customdata}: %{value:." + str(casas) + "f} " + un + "<extra></extra>"},
        textfont={"size": 14, "color": TINTA},
    ))
    fig.add_annotation(text=periodo[:4], x=0.0, y=1.07, xref="paper", yref="paper", showarrow=False,
                       font={"size": 15, "color": TINTA})
    fig.add_annotation(text=periodo[-4:], x=1.0, y=1.07, xref="paper", yref="paper", showarrow=False,
                       font={"size": 15, "color": TINTA})
    return base(fig, altura, margem={"t": 40})


def floresta_dsv(dsv: pd.DataFrame, cod: int = 0, altura: int = 440) -> go.Figure:
    d = dsv[(dsv["cod_ibge"] == cod) & (dsv["ano"].between(1988, 2024))].set_index("ano")
    fig = go.Figure()
    fig.add_trace(go.Bar(x=d.index, y=d["recuperacao_floresta_ha"], name="Floresta que voltou (recuperação)",
                         marker={"color": BOM}, hovertemplate="%{x}: %{y:,.0f} ha recuperados<extra></extra>"))
    fig.add_trace(go.Bar(x=d.index, y=-d["supressao_floresta_ha"], name="Floresta derrubada (supressão)",
                         marker={"color": CRITICO}, customdata=d["supressao_floresta_ha"],
                         hovertemplate="%{x}: %{customdata:,.0f} ha suprimidos<extra></extra>"))
    topo = max(float(d["recuperacao_floresta_ha"].max()), 1.0)
    fundo_ = max(float(d["supressao_floresta_ha"].max()), 1.0)
    for a, b in [(1995, 2004), (2005, 2014), (2015, 2024)]:
        s = d.loc[a:b, "saldo_floresta_ha"].mean()
        fig.add_annotation(x=(a + b) / 2, y=topo * 1.2, text=f"{a} a {b}<br>saldo {fmt(s, sinal=True)} ha/ano",
                           showarrow=False, font={"size": 14, "color": TINTA})
    passo = 10 ** math.floor(math.log10(max(topo, fundo_)))
    passo = passo * (2 if max(topo, fundo_) / passo > 5 else 1)
    marcas = np.arange(-math.ceil(fundo_ / passo) * passo, topo + passo, passo)
    fig.update_layout(barmode="relative", bargap=0.25)
    fig.update_yaxes(title="ha por ano", range=[-fundo_ * 1.1, topo * 1.4], tickvals=marcas,
                     ticktext=[fmt(abs(v)) for v in marcas])
    fig.update_xaxes(dtick=4)
    return base(fig, altura)


def idade(idade_df: pd.DataFrame, cod: int = 0, altura: int = 340) -> go.Figure:
    d = idade_df[idade_df["cod_ibge"] == cod].set_index("idade")["pct_floresta_2025"]
    ordem = ["1 a 5 anos", "6 a 10 anos", "11 a 20 anos", "21 a 30 anos", "31 a 40 anos", "contínua desde 1985"]
    d = d.reindex(ordem).fillna(0)
    rotulos = [o.replace("contínua desde 1985", "Desde 1985 (toda a série)") for o in ordem]
    fig = go.Figure(go.Bar(x=d.values, y=rotulos, orientation="h", marker={"color": VERDE_RAMPA},
                           text=[f"{fmt(v, 1)}%" for v in d.values], textposition="outside", cliponaxis=False,
                           textfont={"size": 15, "color": TINTA}, hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
    fig.update_xaxes(ticksuffix="%", range=[0, max(d.max() * 1.18, 10)], showgrid=True, gridcolor=GRADE)
    fig.update_layout(bargap=0.35, showlegend=False)
    return base(fig, altura)


def _decl_curta(d: str) -> str:
    """'25 a 45° (uso restrito)' vira '25 a 45°'. O MDE de 30 m suaviza o relevo: a classe de 45° ou mais não mede a APP."""
    return d.split(" (")[0]


def relevo(rel: pd.DataFrame, altura: int = 400) -> go.Figure:
    r = rel.assign(declividade=rel["declividade"].map(_decl_curta)).set_index("declividade")
    fig = go.Figure()
    for col, nome_, cor, rotulo in [("floresta_1985_pct", "Floresta em 1985", "#93cfa5", False),
                                    ("floresta_2025_pct", "Floresta em 2025", "#1f8d49", True),
                                    ("pastagem_2025_pct", "Pastagem em 2025", "#c9a227", True)]:
        fig.add_trace(go.Bar(x=r.index, y=r[col], name=nome_, marker={"color": cor},
                             text=[f"{fmt(v, 0)}%" for v in r[col]] if rotulo else None, textposition="outside",
                             textfont={"size": 14, "color": TINTA}, cliponaxis=False, constraintext="none",
                             hovertemplate=f"%{{x}}: %{{y:.1f}}% ({nome_.lower()})<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    fig.update_yaxes(ticksuffix="%", range=[0, 78], title="% da área de cada classe de declividade")
    return base(fig, altura)


def relevo_municipio(relmun: pd.DataFrame, cod: int, altura: int = 360) -> go.Figure:
    r = relmun[(relmun["cod_ibge"] == cod) & (relmun["area_ha"] >= 1)].copy()
    r["declividade"] = r["declividade"].map(_decl_curta)
    r = r.set_index("declividade")
    flo = 100 * r["floresta_2025_ha"] / r["area_ha"]
    pas = 100 * r["pastagem_2025_ha"] / r["area_ha"]
    fig = go.Figure()
    for serie, nome_, cor in [(flo, "Floresta em 2025", "#1f8d49"), (pas, "Pastagem em 2025", "#c9a227")]:
        fig.add_trace(go.Bar(x=r.index, y=serie, name=nome_, marker={"color": cor}, customdata=r["area_ha"],
                             text=[f"{fmt(v, 0)}%" for v in serie], textposition="outside", cliponaxis=False,
                             constraintext="none",
                             textfont={"size": 14, "color": TINTA},
                             hovertemplate=f"%{{x}}: %{{y:.1f}}% ({nome_.lower()}); classe com %{{customdata:,.0f}} ha<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.08)
    fig.update_yaxes(ticksuffix="%", range=[0, 100], title="% da área da classe de declividade")
    return base(fig, altura)


def ripario(rip: pd.DataFrame, cod: int = 0, altura: int = 400) -> go.Figure:
    r = rip[rip["cod_ibge"] == cod].set_index("ano")
    fig = go.Figure()
    linhas = [("nativa_zona_pct", "Faixa de 30 m dos rios e entorno de 50 m das nascentes", "#1f8d49", "bottom right"),
              ("nativa_nascentes_pct", "Só o entorno de 50 m das nascentes", "#2a78d6", "top right")]
    if r["nativa_zona_pct"].iloc[-1] > r["nativa_nascentes_pct"].iloc[-1]:   # rótulo de cima acima da linha
        linhas = [(a, b, c, p.replace("bottom", "X").replace("top", "bottom").replace("X", "top")) for a, b, c, p in linhas]
    for col, nome_, cor, pos in linhas:
        fig.add_trace(go.Scatter(x=r.index, y=r[col], name=nome_, mode="lines", line={"width": 3, "color": cor},
                                 hovertemplate=f"{nome_}: %{{y:.1f}}%<extra></extra>"))
        for ano, posicao in ((2025, pos), (1985, "middle left")):
            fig.add_trace(go.Scatter(x=[ano], y=[r.loc[ano, col]], mode="markers+text", showlegend=False,
                                     marker={"size": 9, "color": cor, "line": {"width": 2, "color": FUNDO}},
                                     text=[f"{fmt(r.loc[ano, col], 1)}%"], textposition=posicao,
                                     textfont={"size": 15, "color": TINTA}, hoverinfo="skip"))
    topo = max(50.0, float(r[["nativa_zona_pct", "nativa_nascentes_pct"]].max().max()) * 1.2)
    fig.update_yaxes(ticksuffix="%", range=[0, min(topo, 100)], title="vegetação nativa (% da zona)")
    fig.update_xaxes(range=[1978, 2030], dtick=5)
    fig.update_layout(hovermode="x unified")
    return base(fig, altura)


def halteres(df: pd.DataFrame, col_a: str, col_b: str, sufixo: str, casas: int, cor_a: str, cor_b: str,
             nome_a: str, nome_b: str, destacar: str | None = None, altura: int = 600) -> go.Figure:
    d = df.sort_values(col_b)
    fig = go.Figure()
    for _, r in d.iterrows():
        fig.add_trace(go.Scatter(x=[r[col_a], r[col_b]], y=[r["municipio"]] * 2, mode="lines",
                                 line={"color": TINTA if r["municipio"] == destacar else EIXO, "width": 2},
                                 showlegend=False, hoverinfo="skip"))
    fig.add_trace(go.Scatter(x=d[col_a], y=d["municipio"], mode="markers", name=nome_a,
                             marker={"size": 11, "color": cor_a, "line": {"width": 2, "color": FUNDO}},
                             hovertemplate=f"%{{y}}: %{{x:.{casas}f}}{sufixo} ({nome_a})<extra></extra>"))
    fig.add_trace(go.Scatter(x=d[col_b], y=d["municipio"], mode="markers+text", name=nome_b,
                             marker={"size": 11, "color": cor_b, "line": {"width": 2, "color": FUNDO}},
                             text=[fmt(v, casas) + sufixo for v in d[col_b]], cliponaxis=False,
                             textposition=["middle right" if b >= a else "middle left" for a, b in zip(d[col_a], d[col_b])],
                             textfont={"size": 14, "color": TINTA},
                             hovertemplate=f"%{{y}}: %{{x:.{casas}f}}{sufixo} ({nome_b})<extra></extra>"))
    lo = min(d[col_a].min(), d[col_b].min())
    hi = max(d[col_a].max(), d[col_b].max())
    fig.update_yaxes(showgrid=False, tickfont={"size": 14},
                     ticktext=[f"<b>{m}</b>" if m == destacar else m for m in d["municipio"]], tickvals=d["municipio"])
    fig.update_xaxes(showgrid=True, gridcolor=GRADE, ticksuffix=sufixo, range=[lo - 0.08 * (hi - lo), hi + 0.16 * (hi - lo)])
    fig.update_layout(legend={"y": -0.06})
    return base(fig, altura)


def fogo(fogo_df: pd.DataFrame, cod: int = 0, altura: int = 420) -> go.Figure:
    f = fogo_df[fogo_df["cod_ibge"] == cod].copy()
    f["g"] = f["grupo_queimado"].map(nome)
    p = f.pivot_table(index="ano", columns="g", values="area_ha", aggfunc="sum", fill_value=0)
    p = p.reindex(range(1985, 2025), fill_value=0)
    k, un = _unidade(p.sum(axis=1).values)
    p = p / k
    casas = 1 if k > 1 else 0
    fig = go.Figure()
    for g in ["Floresta", "Vegetação herbácea e arbustiva", "Pastagem", "Mosaico de usos", OUTROS[0]]:
        if g in p:
            fig.add_trace(go.Bar(x=p.index, y=p[g], name=g, marker={"color": COR[g], "line": {"width": 0}},
                                 hovertemplate=f"{g}: %{{y:.{casas}f}} {un}<extra></extra>"))
    tot = p.sum(axis=1)
    for ano in sorted(set(tot.nlargest(3).index)):
        if tot[ano] > 0:
            fig.add_annotation(x=ano, y=tot[ano], text=f"{fmt(tot[ano], casas)} {un}", showarrow=False, yshift=12,
                               font={"size": 13, "color": TINTA})
    if cod == 0 and "Floresta" in p:
        flo = p["Floresta"]
        fig.add_annotation(x=flo.idxmax(), y=flo.max(), text=f"floresta: {fmt(flo.max() * k)} ha,<br>maior da série",
                           showarrow=True, arrowhead=0, arrowcolor=TINTA_FRACA, axref="x", ayref="y",
                           ax=flo.idxmax() - 3.5, ay=10.5, font={"size": 14, "color": TINTA}, align="center")
    fig.update_layout(barmode="stack", bargap=0.2, hovermode="x unified")
    fig.update_yaxes(title=f"{un} queimados no ano")
    fig.update_xaxes(dtick=5)
    return base(fig, altura)


def c9_c11(c9: pd.DataFrame, altura: int = 400) -> go.Figure:
    d = c9[c9["ano"] == 2023].set_index("grupo")
    ordem = ["Formação florestal", "Vegetação herbácea e arbustiva", "Pastagem", "Mosaico de usos", "Área urbanizada", "Água"]
    d = d.reindex(ordem)
    nomes = [GRUPOS[g][0] for g in ordem]
    fig = go.Figure()
    for col, nome_, cor, tinta in [("c9_pct", "Coleção 9 (apresentada em abril)", "#b4b2a9", TINTA_2),
                                   ("c11_pct", "Coleção 11 (atual)", "#2a78d6", TINTA)]:
        fig.add_trace(go.Bar(y=nomes, x=d[col], name=nome_, orientation="h", marker={"color": cor},
                             text=[f"{fmt(v, 1)}%" for v in d[col]], textposition="outside", cliponaxis=False,
                             textfont={"size": 14, "color": tinta},
                             hovertemplate=f"%{{y}}: %{{x:.1f}}% ({nome_})<extra></extra>"))
    fig.update_layout(barmode="group", bargap=0.3, bargroupgap=0.1)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(ticksuffix="%", range=[0, 70], showgrid=True, gridcolor=GRADE)
    return base(fig, altura)


def restauracao(prio: pd.DataFrame, destacar: str | None = None, altura: int = 620) -> go.Figure:
    p = prio[prio["cod_ibge"] > 0].copy()
    p["perto"] = p["pasto_prioritario_ate_100m_de_fragmento_100ha_ha"] / 1000
    p["demais"] = (p["pasto_prioritario_ha"] - p["pasto_prioritario_ate_100m_de_fragmento_100ha_ha"]) / 1000
    p = p.sort_values("pasto_prioritario_ha")
    fig = go.Figure()
    fig.add_trace(go.Bar(y=p["municipio"], x=p["perto"], orientation="h", marker={"color": "#1f8d49"},
                         name="a até 100 m de um fragmento de mata de 100 ha ou mais",
                         hovertemplate="%{y}: %{x:.1f} mil ha perto de fragmento grande<extra></extra>"))
    fig.add_trace(go.Bar(y=p["municipio"], x=p["demais"], orientation="h", marker={"color": "#c9a227"},
                         name="demais", text=[fmt(v / 1000, 1) for v in p["pasto_prioritario_ha"]],
                         textposition="outside", cliponaxis=False, textfont={"size": 14, "color": TINTA},
                         hovertemplate="%{y}: %{x:.1f} mil ha nos demais trechos<extra></extra>"))
    fig.update_layout(barmode="stack", bargap=0.3, legend={"y": -0.06, "traceorder": "normal"})
    fig.update_xaxes(title="mil ha de pasto em 2025", showgrid=True, gridcolor=GRADE)
    fig.update_yaxes(showgrid=False, tickfont={"size": 14},
                     ticktext=[f"<b>{m}</b>" if m == destacar else m for m in p["municipio"]], tickvals=p["municipio"])
    return base(fig, altura)


def robustez(freq: pd.DataFrame, destaques: list[str], limiar: float = 0.8, altura: int = 520) -> go.Figure:
    d = freq.sort_values("freq_top3")
    cores = [DESTAQUE if m in destaques else NEUTRO for m in d["municipio"]]
    fig = go.Figure(go.Bar(x=100 * d["freq_top3"], y=d["municipio"], orientation="h", marker={"color": cores},
                           text=[f"{fmt(100 * v, 1)}%" for v in d["freq_top3"]], textposition="outside", cliponaxis=False,
                           textfont={"size": 14, "color": TINTA},
                           hovertemplate="%{y}: entre os três primeiros em %{x:.1f}% dos cenários<extra></extra>"))
    fig.add_vline(x=100 * limiar, line={"color": TINTA_2, "width": 1.5, "dash": "dash"})
    fig.add_annotation(x=100 * limiar, y=1.0, yref="paper", yanchor="bottom", yshift=4,
                       text=f"limiar de {fmt(100 * limiar)}%", showarrow=False, font={"size": 13, "color": TINTA_2})
    fig.update_xaxes(range=[0, 112], ticksuffix="%", showgrid=True, gridcolor=GRADE,
                     title="% dos cenários")
    fig.update_yaxes(showgrid=False, tickfont={"size": 14})
    fig.update_layout(showlegend=False, bargap=0.3)
    return base(fig, altura, margem={"t": 40})


# ---- mapas (MapLibre pelo Plotly: sem chave de acesso, sem rodar o app de novo a cada zoom) ----------

def _y_mercator(lat: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def zoom_caixa(oeste: float, norte: float, leste: float, sul: float, largura_px: int = 950,
               altura_px: int = 520) -> tuple[dict, float]:
    """Centro e zoom que põem a caixa inteira num mapa de largura_px x altura_px (MapLibre: tile de 512 px)."""
    yc = (_y_mercator(norte) + _y_mercator(sul)) / 2
    centro = {"lon": (oeste + leste) / 2, "lat": math.degrees(2 * math.atan(math.exp(yc)) - math.pi / 2)}
    zw = math.log2(largura_px / (512 * (leste - oeste) / 360))
    zh = math.log2(altura_px / (512 * abs(_y_mercator(norte) - _y_mercator(sul)) / (2 * math.pi)))
    return centro, min(zw, zh)


def _zoom(caixa: dict, altura_px: int = 520, largura_px: int = 950) -> tuple[dict, float]:
    e = caixa.get("enquadramento", caixa)
    return zoom_caixa(e["oeste"], e["norte"], e["leste"], e["sul"], largura_px=largura_px, altura_px=altura_px)


def _contornos(geo_mun: dict, geo_rh3: dict, selecionado: int | None) -> list[dict]:
    camadas = [{"sourcetype": "geojson", "source": geo_rh3, "type": "line", "color": TINTA, "line": {"width": 1.6}}]
    if selecionado is not None:
        sel = {"type": "FeatureCollection",
               "features": [f for f in geo_mun["features"] if f["properties"]["cod_ibge"] == selecionado]}
        camadas.append({"sourcetype": "geojson", "source": sel, "type": "line", "color": TINTA, "line": {"width": 3.2}})
    return camadas


def mapa_imagem(imagem: str, caixa: dict, geo_mun: dict, geo_rh3: dict, selecionado: int | None = None,
                altura: int = 560, opacidade: float = 0.95, largura: int = 950) -> go.Figure:
    """Mapa com a sobreposição (PNG em Web Mercator) e os limites; passar o mouse mostra o município."""
    o, n, le, s = caixa["oeste"], caixa["norte"], caixa["leste"], caixa["sul"]
    feats = geo_mun["features"]
    fig = go.Figure(go.Choroplethmap(
        geojson=geo_mun, featureidkey="properties.cod_ibge", locations=[f["properties"]["cod_ibge"] for f in feats],
        z=[0] * len(feats), customdata=[f["properties"]["municipio"] for f in feats],
        colorscale=[[0, "rgba(0,0,0,0)"], [1, "rgba(0,0,0,0)"]], showscale=False,
        marker={"line": {"width": 1.1, "color": "rgba(255,255,255,0.95)"}},
        hovertemplate="%{customdata}<extra></extra>"))
    centro, zoom = _zoom(caixa, altura - 40, largura)
    camadas = [{"sourcetype": "image", "source": imagem, "coordinates": [[o, n], [le, n], [le, s], [o, s]],
                "opacity": opacidade, "below": "traces"}] + _contornos(geo_mun, geo_rh3, selecionado)
    fig.update_layout(map={"style": "carto-positron", "center": centro, "zoom": zoom, "layers": camadas},
                      height=altura, margin={"l": 0, "r": 0, "t": 0, "b": 0}, paper_bgcolor=FUNDO)
    return fig


def mapa_coropletico(df: pd.DataFrame, coluna: str, rotulo: str, sufixo: str, casas: int, geo_mun: dict,
                     geo_rh3: dict, caixa: dict, divergente: bool = False, altura: int = 560,
                     largura: int = 950) -> go.Figure:
    if divergente:
        escala, meio = [[0, REDUCAO], [0.5, "#f2f1ed"], [1, AUMENTO]], 0
    else:
        escala, meio = [[i / (len(VERDE_RAMPA) - 1), c] for i, c in enumerate(VERDE_RAMPA)], None
    texto = [f"{fmt(v, casas)}{sufixo}" for v in df[coluna]]
    fig = go.Figure(go.Choroplethmap(
        geojson=geo_mun, featureidkey="properties.cod_ibge", locations=df["cod_ibge"], z=df[coluna], zmid=meio,
        colorscale=escala, marker={"opacity": 0.85, "line": {"width": 0.8, "color": "#ffffff"}},
        customdata=np.stack([df["municipio"], texto], axis=-1),
        hovertemplate="<b>%{customdata[0]}</b><br>" + rotulo + ": %{customdata[1]}<extra></extra>",
        colorbar={"title": {"text": rotulo, "side": "right", "font": {"size": 13}}, "ticksuffix": sufixo,
                  "thickness": 14, "len": 0.8, "tickformat": f",.{casas}f"}))
    centro, zoom = _zoom(caixa, altura - 40, largura - 90)
    fig.update_layout(map={"style": "carto-positron", "center": centro, "zoom": zoom,
                           "layers": [{"sourcetype": "geojson", "source": geo_rh3, "type": "line", "color": TINTA,
                                       "line": {"width": 1.6}}]},
                      height=altura, margin={"l": 0, "r": 0, "t": 0, "b": 0}, paper_bgcolor=FUNDO,
                      separators=",.")
    return fig
