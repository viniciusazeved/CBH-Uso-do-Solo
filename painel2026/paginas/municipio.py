"""Perfil do município: os mesmos números do panorama na porção do município na RH-III."""

from __future__ import annotations

import io
import zipfile

import pandas as pd
import streamlit as st

from .. import dados, graficos, ui
from .. import ranking_util as ru
from ..estilo import FONTE_C11, FONTE_DSV, FONTE_FOGO, fmt, pct
from .rios import NOTA_FAIXA, uso_faixa

TABELAS = ["composicao_anual.csv", "dsv_anual.csv", "floresta_anual.csv", "floresta_idade_2025.csv", "fogo_anual.csv",
           "fogo_frequencia.csv", "fragmentacao.csv", "relevo_municipios.csv", "restauracao_indicativa.csv",
           "ripario_anual.csv", "ripario_uso.csv", "transicoes_periodos.csv"]


def insercao(cod: int, m: str) -> None:
    mun = dados.municipios().set_index("cod_ibge").loc[cod]
    txt = (f"Os números desta página são da porção de {m} na RH-III: {fmt(mun['area_na_rh3_ha'] / 1000, 1)} mil ha, "
           f"{pct(min(mun['pct_territorio_na_rh3'], 100), 0)} do território do município")
    if mun["pct_territorio_na_rh3"] < 99:
        txt += (f", com {pct(min(mun['pct_urbano_na_rh3'], 100), 0)} da área urbana de 2025. O restante está em outra "
                "região hidrográfica e não entra aqui")
    st.markdown(txt + ".")
    if cod in dados.PORCAO_PEQUENA:
        st.info("Porção pequena na RH-III: com menos de 5.000 ha na bacia, uma única propriedade muda as taxas do "
                "município. No Ranking Ambiental, os indicadores são calculados e publicados, e o município concorre a "
                "menção especial.", icon=":material/info:")


def metricas(cod: int) -> None:
    comp = dados.tabela("composicao_anual.csv")
    p = comp[comp["cod_ibge"] == cod].pivot_table(index="ano", columns="grupo", values="pct", fill_value=0)
    a = comp[comp["cod_ibge"] == cod].pivot_table(index="ano", columns="grupo", values="area_ha", fill_value=0)
    rip = dados.tabela("ripario_anual.csv")
    rr = rip[rip["cod_ibge"] == cod].set_index("ano")
    flo, pas, urb = "Formação florestal", "Pastagem", "Área urbanizada"
    k = st.columns(4)
    k[0].metric("Floresta em 2025", pct(p.loc[2025, flo]), f"{fmt(p.loc[2025, flo] - p.loc[1985, flo], 1, sinal=True)} p.p. desde 1985")
    k[1].metric("Pastagem em 2025", pct(p.loc[2025, pas]), f"{fmt(p.loc[2025, pas] - p.loc[1985, pas], 1, sinal=True)} p.p. desde 1985",
                delta_color="off")
    k[2].metric("Área urbanizada em 2025", f"{fmt(a.loc[2025, urb])} ha", f"{fmt(a.loc[1985, urb])} ha em 1985", delta_color="off",
                delta_arrow="off")
    k[3].metric("Vegetação nativa na beira dos rios", pct(rr.loc[2025, "nativa_zona_pct"]),
                f"{fmt(rr.loc[2025, 'nativa_zona_pct'] - rr.loc[1985, 'nativa_zona_pct'], 1, sinal=True)} p.p. desde 1985",
                help="Floresta e área úmida na faixa de 30 m dos rios e no entorno de 50 m das nascentes.")


def secao_mapa(cod: int, m: str) -> None:
    ui.mapa_uso("municipio", selecionado=cod, altura=500)


def secao_uso(cod: int, m: str) -> None:
    comp = dados.tabela("composicao_anual.csv")
    st.subheader(f"Uso e cobertura do solo em {m}, 1985 a 2025")
    st.caption("Percentual da porção do município na RH-III")
    ui.grafico(graficos.composicao(comp, cod), None, chave="m_comp")
    ui.legenda_classes()
    st.caption(FONTE_C11)
    st.subheader("O que ganhou e o que perdeu")
    st.caption("Área em 2025 menos área em 1985, por classe")
    ui.grafico(graficos.mudanca_liquida(comp, cod, altura=300), None, chave="m_mud")
    st.subheader("Trocas entre classes de 1985 para 2025")
    st.caption("Sem a área que ficou igual; fluxos de 1% ou mais do total trocado, com no mínimo 5 ha")
    ui.grafico(graficos.sankey(dados.tabela("transicoes_periodos.csv"), cod, altura=440), FONTE_C11, chave="m_sankey")


def secao_floresta(cod: int, m: str) -> None:
    dsv = dados.tabela("dsv_anual.csv")
    d = dsv[(dsv["cod_ibge"] == cod) & dsv["ano"].between(1988, 2024)].set_index("ano")
    st.subheader(f"Floresta que voltou e floresta derrubada em {m}")
    st.caption(f"Saldo médio de {fmt(d.loc[2005:2014, 'saldo_floresta_ha'].mean(), sinal=True)} ha por ano de 2005 a "
               f"2014 e de {fmt(d.loc[2015:2024, 'saldo_floresta_ha'].mean(), sinal=True)} ha por ano de 2015 a 2024")
    ui.grafico(graficos.floresta_dsv(dsv, cod), FONTE_DSV, chave="m_dsv")
    st.subheader("Idade da floresta de 2025")
    st.caption("Tempo desde o último ano em que não era floresta")
    ui.grafico(graficos.idade(dados.tabela("floresta_idade_2025.csv"), cod, altura=300), None, chave="m_idade")
    st.subheader("Floresta e pasto por declividade, 2025")
    st.caption("Percentual da área de cada classe de declividade (Copernicus GLO-30); classes com menos de 1 ha ficam de fora")
    ui.grafico(graficos.relevo_municipio(dados.tabela("relevo_municipios.csv"), cod), None, chave="m_relevo")
    fr = dados.tabela("fragmentacao.csv")
    fr = fr[fr["cod_ibge"] == cod].set_index("ano")
    k = st.columns(3)
    for col, ano in zip(k, (1985, 2005, 2025)):
        col.metric(f"Fragmentos de floresta em {ano}", fmt(fr.loc[ano, "n_fragmentos"]),
                   f"maior: {fmt(fr.loc[ano, 'maior_ha'])} ha", delta_color="off", delta_arrow="off")


def secao_rios(cod: int, m: str) -> None:
    st.subheader(f"Vegetação nativa na faixa ripária de {m}")
    ui.grafico(graficos.ripario(dados.tabela("ripario_anual.csv"), cod), None, chave="m_rip")
    st.subheader("O que ocupa a faixa ripária em 2025")
    ui.grafico(uso_faixa(dados.tabela("ripario_uso.csv"), cod), None, chave="m_rip_uso")
    pr = dados.tabela("restauracao_indicativa.csv").set_index("cod_ibge").loc[cod]
    st.subheader("Onde a restauração mais ajuda a água")
    st.markdown(f"Pasto em 2025 na faixa ripária: {fmt(pr['pasto_zona_ripária_ha'])} ha; em encosta de 25° ou mais: "
                f"{fmt(pr['pasto_encosta_25graus_ha'])} ha; nos dois juntos, sem contar duas vezes: "
                f"{fmt(pr['pasto_prioritario_ha'])} ha ({pct(pr['pasto_prioritario_pct_da_area'])} da porção na RH-III), "
                f"dos quais {fmt(pr['pasto_prioritario_ate_100m_de_fragmento_100ha_ha'])} ha a até 100 m de um fragmento "
                "de mata de 100 ha ou mais. Indicativo, não é mapa oficial de prioridade.")
    ui.nota(NOTA_FAIXA)
    st.caption(FONTE_C11)


def secao_fogo(cod: int, m: str) -> None:
    fq = dados.tabela("fogo_frequencia.csv")
    fq = fq[fq["cod_ibge"] == cod].set_index("vezes_queimado_1985_2024")
    nunca = fq.loc["nunca", "pct_area"] if "nunca" in fq.index else 100.0
    st.subheader(f"Área queimada por ano em {m}")
    st.caption(f"{pct(100 - nunca, 0)} da porção na RH-III queimou ao menos uma vez de 1985 a 2024")
    ui.grafico(graficos.fogo(dados.tabela("fogo_anual.csv"), cod), FONTE_FOGO, chave="m_fogo")


def secao_ranking(cod: int, m: str) -> None:
    t = ru.tabela()
    r = t.set_index("cod_ibge").loc[cod]
    med = ru.medianas(t)
    st.subheader(f"Ranking Ambiental CBH-MPS 2026: resultados na porção de {m} na RH-III")
    st.markdown(f"Faixa: **{r['faixa']}**." + (f" Entre os três primeiros em {pct(100 * r['freq_top3'])} dos "
                                                f"{fmt(ru.decisao()['n_cenarios'])} cenários." if r["elegivel"] else ""))
    linhas = [{"Indicador": f"{col}. {frente}: {nome_}", "Unidade e sentido": un, "Valor": fmt(r[col], casas),
               "Mediana dos 16 elegíveis": fmt(med[col], casas), "Comparação": ru.comparar(r[col], med[col], menor)}
              for col, frente, nome_, un, casas, menor in ru.INDICADORES]
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    perda = r["perda_floresta_pct"]
    k = st.columns(2)
    k[0].metric("Saldo de floresta no território avaliado, 2015 a 2024", "ganho" if perda <= 0 else "perda",
                f"{fmt(-perda, 2, sinal=True)}% do estoque de 2015", delta_color="normal",
                delta_arrow="up" if perda <= 0 else "down")
    k[1].metric("Supressão em relação à taxa da bacia", f"{fmt(r['razao_p1_regional'], 2)} vez" +
                ("es" if r["razao_p1_regional"] >= 2 else ""), "limite da trava: 1,5", delta_color="off",
                delta_arrow="off")
    if ru.travas(r):
        st.warning(f"Trava no caso-base: {m} {ru.travas(r)}. Nos cenários em que a trava vale, o município fica fora "
                   "dos três primeiros.", icon=":material/block:")
    st.markdown("**Território avaliado**")
    terr = pd.DataFrame([("Porção do município na RH-III", r["recorte_rh3_ha"]),
                         ("Retirado: parques federais e estaduais", r["retirado_uc_ha"]),
                         ("Retirado: silvicultura provável", r["retirado_silvicultura_ha"]),
                         ("Retirado: água", r["retirado_agua_ha"]),
                         ("Território avaliado", r["territorio_ha"])], columns=["Item", "Área (ha)"])
    ui.tabela(terr, {"Área (ha)": 0})
    st.caption("Os indicadores do ranking são calculados no território avaliado, com o estado de cada pixel pela classe "
               "mais frequente em três anos (2014 a 2016 e 2023 a 2025) e, na faixa ripária, sem a área urbana de 2015. "
               "Por isso diferem dos números das outras seções desta página. A fração descontada do Restaurar pela "
               "auditoria está na página do ranking.")


def secao_dados(cod: int, m: str) -> None:
    st.subheader("Dados")
    st.markdown(f"Tabelas da porção de {m} na RH-III, em CSV (separador vírgula, ponto decimal), num arquivo zip.")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for nome_ in TABELAS:
            df = dados.tabela(nome_)
            z.writestr(nome_, df[df["cod_ibge"] == cod].to_csv(index=False))
    st.download_button(f"Baixar os dados de {m}", buf.getvalue(), file_name=f"uso_do_solo_rh3_{cod}.zip",
                       mime="application/zip", icon=":material/download:")


def _manter_secao() -> None:
    if st.session_state.get("_secao_mun") is None:
        st.session_state["_secao_mun"] = st.session_state.get("_secao_mun_ultima", "Mapa")
    st.session_state["_secao_mun_ultima"] = st.session_state["_secao_mun"]


def pagina() -> None:
    st.title("Perfil do município")
    cod, m = ui.escolher_municipio()
    insercao(cod, m)
    metricas(cod)
    secoes = {"Mapa": secao_mapa, "Uso do solo": secao_uso, "Floresta": secao_floresta, "Rios e nascentes": secao_rios,
              "Fogo": secao_fogo}
    if dados.ranking_disponivel():
        secoes["Ranking 2026"] = secao_ranking
    secoes["Dados"] = secao_dados
    escolha = st.pills("Ver", list(secoes), default="Mapa", key="_secao_mun", on_change=_manter_secao,
                       label_visibility="collapsed") or "Mapa"
    secoes[escolha](cod, m)
