"""Floresta: supressão e recuperação, idade, relevo, unidades de conservação e fragmentos."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from .. import dados, graficos, ui
from ..estilo import FONTE_C11, FONTE_DSV, fmt, pct


def pagina() -> None:
    r = dados.resumo()
    dsv = dados.tabela("dsv_anual.csv")
    d = dsv[(dsv["cod_ibge"] == dados.RH3) & dsv["ano"].between(1988, 2024)].set_index("ano")
    anos_bons = r["dsv_anos_recuperacao_maior_que_supressao_floresta"]
    desde = min(a for a in anos_bons if all(x in anos_bons for x in range(a, 2025)))
    s1, s2 = d.loc[2005:2014, "saldo_floresta_ha"].mean(), d.loc[2015:2024, "saldo_floresta_ha"].mean()
    ucs = dados.tabela("ucs.csv").set_index("categoria")
    fora_ganho = 100 * ucs.loc["Fora de UC", "ganho_bruto_1985_2025_ha"] / ucs["ganho_bruto_1985_2025_ha"].sum()

    st.title("Floresta: o que voltou, o que saiu e o que ficou")
    st.markdown(f"A floresta da bacia cresce desde o início dos anos 1990, mais devagar na última década. A que voltou "
                f"é jovem, e {pct(fora_ganho, 0)} dela está fora de unidades de conservação.")

    st.subheader(f"Desde {desde}, todo ano volta mais floresta do que é derrubada")
    st.markdown(f"No mapa de desmatamento e vegetação secundária do MapBiomas, o saldo médio foi de "
                f"{fmt(s1, sinal=True)} ha por ano de 2005 a 2014 e de {fmt(s2, sinal=True)} ha por ano de 2015 a 2024: "
                "a recuperação perdeu ritmo na última década.")
    ui.grafico(graficos.floresta_dsv(dsv), FONTE_DSV)
    fa = dados.tabela("floresta_anual.csv")
    fa = fa[(fa["cod_ibge"] == dados.RH3) & fa["ano"].between(desde, 2025)].set_index("ano")["saldo_ha"]
    negativos = [str(a) for a, v in fa.items() if v < 0]
    saldo_nat = d.loc[2015:2024, "saldo_ha"].mean()
    ui.nota("O gráfico usa o produto de desmatamento e vegetação secundária do MapBiomas restrito à floresta. Com toda "
            f"a vegetação nativa (floresta, campo e capoeira baixa), o saldo médio de 2015 a 2024 fica em "
            f"{fmt(saldo_nat, sinal=True)} ha por ano: a vegetação aberta perdeu área no período. "
            + (f"Na série anual de cobertura, que compara mapas de anos seguidos, a floresta teve pequenas perdas "
               f"líquidas em {', '.join(negativos[:-1]) + ' e ' + negativos[-1] if len(negativos) > 1 else negativos[0]}. "
               if negativos else "")
            + "O ano de 2025 fica fora porque o produto ainda não fechou os eventos do último ano.")

    idade_pct = r["floresta_2025_por_idade_pct"]
    jovem = idade_pct["1 a 5 anos"] + idade_pct["6 a 10 anos"] + idade_pct["11 a 20 anos"]
    st.subheader("A floresta jovem")
    st.markdown(f"{pct(idade_pct['contínua desde 1985'])} da floresta de 2025 está de pé desde 1985, sem interrupção em "
                f"nenhum ano do mapa. Outros {pct(jovem)} têm até 20 anos: é a floresta mais nova da bacia.")
    ui.grafico(graficos.idade(dados.tabela("floresta_idade_2025.csv"), altura=300),
               "Floresta de 2025 pelo tempo desde o último ano em que não era floresta. " + FONTE_C11)

    rel = dados.tabela("relevo.csv").set_index("declividade")
    enc = rel.loc["25 a 45° (uso restrito)"]
    st.subheader("A mata fica nas encostas")
    st.markdown(f"A floresta cobre {fmt(enc['floresta_2025_pct'])}% das encostas de 25 a 45° e "
                f"{fmt(rel.loc['0 a 10°', 'floresta_2025_pct'])}% das áreas abaixo de 10°. Mas ainda há "
                f"{fmt(enc['pastagem_2025_ha'] / 1000)} mil ha de pasto nas encostas de 25 a 45°, onde o Código "
                "Florestal restringe o uso (restrição, não proibição).")
    ui.grafico(graficos.relevo(dados.tabela("relevo.csv"), altura=380), "Declividade do Copernicus GLO-30. O modelo de "
               "30 m suaviza o relevo: a classe de 45° ou mais não mede a APP de encosta. " + FONTE_C11)

    st.subheader("Fora das unidades de conservação")
    k = st.columns([1, 2], gap="large")
    k[0].metric("Floresta de 2025 fora de unidade de conservação", pct(ucs.loc["Fora de UC", "pct_da_floresta_2025"]))
    with k[0]:
        st.markdown("A restauração da bacia depende sobretudo do proprietário rural.")
    tab = pd.DataFrame({"Categoria": ucs.index, "Área (ha)": ucs["area_ha"].values,
                        "Floresta 2025 (% da área)": ucs["floresta_2025_pct"].values,
                        "% da floresta da bacia": ucs["pct_da_floresta_2025"].values})
    with k[1]:
        ui.tabela(tab, {"Área (ha)": 0, "Floresta 2025 (% da área)": 1, "% da floresta da bacia": 1})
    ui.nota("As unidades de conservação foram criadas onde já havia mata; a diferença de cobertura não mede a eficácia "
            "delas. Fonte das unidades: base mundial de áreas protegidas (WDPA).")

    st.subheader("Fragmentos de floresta")
    fr = r["fragmentacao"]
    k = st.columns(3)
    for col, ano in zip(k, ("1985", "2005", "2025")):
        col.metric(f"Em {ano}", f"{fmt(fr[ano]['n_fragmentos'])} fragmentos",
                   f"{pct(fr[ano]['pct_floresta_em_frag_100ha_ou_mais'])} da floresta em fragmentos de 100 ha ou mais",
                   delta_color="off", delta_arrow="off")
    st.caption("Fragmentos contados com vizinhança de 8 pixels sobre o mapa de 30 m. " + FONTE_C11)
