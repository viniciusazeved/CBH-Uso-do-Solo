"""Ranking Ambiental CBH-MPS 2026: destaques, robustez, faixas, auditoria e método.

Sem painel_dados/ranking/decisao.json, a página mostra só o método e a data do anúncio. A publicação não traz índice
nem posição do caso-base: os destaques saem sem ordem e as demais elegíveis em ordem alfabética (protocolo, seções 6
e 7)."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from .. import dados, graficos, ui
from .. import ranking_util as ru
from ..estilo import fmt, pct

INTRO = ("Os municípios com os melhores resultados de uso e cobertura do solo na sua porção da RH-III, nos mandatos de "
         "2017 a 2020 e de 2021 a 2024, em três frentes ligadas ao tema do XI Simpósio Água Boa, Restaurar para "
         "Abastecer: proteger a floresta, restaurar o que foi aberto e recuperar a beira dos rios.")
HASHES = [("Protocolo v1.1, 14/10/2026", "4d185f25ab516e0544defff489bd8d3bff3ab6f7d8cedbf3a97f1cc32f11b066"),
          ("Adendo 1, 15/10/2026", "84939fa11e05d069c8d7454016f93b4e035e6551fe3c955dc71e3c5fa1b4a7ae"),
          ("Adendo 2, 15/10/2026", "0076d456ac06af727cbd74c22b71561011c9deaa2db4d9f316c5fb9e5ffd1a96")]
TITULO_FAIXA = {"Destaque": "Destaques", "4º ao 6º no caso-base": "Do 4º ao 6º no caso-base",
                "Demais elegíveis": "Demais elegíveis",
                "Porção pequena na RH-III": "Porção pequena na RH-III (concorrem a menção especial)"}


def metodo() -> None:
    st.subheader("O que o ranking mede")
    c = st.columns(3, gap="medium")
    frentes = [("Proteger", "35%", "Taxa de supressão de floresta, em % ao ano, de 2017 a 2024. Menor é melhor."),
               ("Restaurar", "35%", "Pasto, lavoura ou mosaico que virou floresta de 2017 a 2022 e continuou floresta "
                                    "até 2025, relativo ao que havia para restaurar."),
               ("Abastecer", "30%", "Quanto do déficit de vegetação nativa na beira dos rios e nascentes foi recuperado "
                                    "de 2015 a 2024 (20%) e quanto dessa faixa tem vegetação nativa em 2024 (10%).")]
    for col, (titulo, peso, texto) in zip(c, frentes):
        with col.container(border=True):
            st.markdown(f"**{titulo}** · peso {peso}")
            st.markdown(texto)
    st.markdown("**Como pontua.** Em cada um dos quatro indicadores, os 16 municípios com pelo menos 5.000 ha na RH-III "
                "recebem um posto, que vira pontos de 0 a 100; o índice soma os pontos com pesos 35, 35, 20 e 10. "
                "Diferença de índice menor que 2 pontos é empate técnico, decidido pelo menor P1 e depois pelo maior A1. "
                "Rio Claro, Miguel Pereira e Mendes têm porção pequena na bacia, onde uma única propriedade muda a taxa: "
                "têm os indicadores calculados e publicados e concorrem a menção especial.")
    st.markdown("**Travas.** Num cenário, não entra entre os três primeiros quem perdeu mais de 0,5% da floresta ou "
                "teve supressão acima de 1,5 vez a taxa da bacia naquele cenário.")
    st.markdown("**Território avaliado.** A porção de cada município na RH-III, sem os parques federais e estaduais "
                "(Parque Nacional do Itatiaia e Parques Estaduais da Serra da Concórdia e da Pedra Selada), sem a "
                "silvicultura provável e sem água: fica o território que município e proprietários manejam.")
    st.markdown("**Por que confiar.** O protocolo foi fixado e registrado em 14/10/2026, com código de verificação, "
                "antes de qualquer resultado municipal ser visto. Dois adendos de 15/10/2026, também registrados antes de "
                "calcular as correções, definiram a conferência em alta resolução e a correção do Restaurar, que vale para "
                "os 19 municípios. O resultado foi testado em 5.000 cenários sorteados, variando normalização, pesos, "
                "janelas, compostos, máscaras, unidades de conservação, faixa ripária, forma do A1, relevo e a incerteza "
                "da correção: conta a frequência com que cada município fica entre os três primeiros, e 80% ou mais é "
                "resultado robusto. O pódio só sai em ordem se a ordem do caso-base for a mais frequente em pelo menos "
                "metade dos cenários; com menos de três municípios robustos, as vagas restantes seguem a ordem do caso-base.")
    with st.expander("Códigos de verificação (SHA-256)"):
        st.markdown("\n".join(f"- {nome_}: `{h}`" for nome_, h in HASHES))
    ui.nota("O ranking mede resultados no território, observados por satélite; não mede políticas nem atribui autoria. "
            "Regeneração espontânea e decisões de proprietários também aparecem no mapa. As práticas que explicam os "
            "resultados, os próprios municípios contam.")


def destaques(t: pd.DataFrame) -> None:
    dec = ru.decisao()
    st.subheader("Os municípios em destaque")
    cols = st.columns(len(dec["destaques"]), gap="medium")
    for col, m in zip(cols, dec["destaques"]):
        linha = t[t["municipio"] == m].iloc[0]
        p = ru.postos(linha)
        with col.container(border=True):
            st.markdown(f"### {m}")
            st.metric("Entre os três primeiros", pct(100 * linha["freq_top3"]), f"dos {fmt(dec['n_cenarios'])} cenários",
                      delta_color="off", delta_arrow="off")
            st.markdown(f"Posto entre os 16 em cada indicador: Proteger {ru.posto_txt(p['P1'])}, Restaurar "
                        f"{ru.posto_txt(p['R1'])}, Abastecer {ru.posto_txt(p['A1'])} (recuperação ripária) e "
                        f"{ru.posto_txt(p['A2'])} (cobertura ripária).")
    st.caption(f"Em ordem alfabética. Resultados na porção de cada município na RH-III, medidos de 2015 a 2024 "
               f"(supressão de 2017 a 2024; regeneração das coortes de 2017 a 2022 que continuou floresta até 2025). Pela "
               f"regra do protocolo, o pódio só sai em ordem quando a ordem do caso-base é a mais frequente em pelo menos "
               f"metade dos cenários; a ordem mais frequente apareceu em {pct(100 * dec['freq_ordem_modal'])} deles, e por "
               f"isso os três aparecem sem ordem.")
    arq = dados.DIR / "ranking" / "mencoes.json"
    if arq.exists():          # decisão do comitê; só entra quando o arquivo existe
        men = json.loads(arq.read_text(encoding="utf-8"))
        st.markdown("**Menções.** " + "; ".join(f"{k}: {v}" for k, v in men.items()) + ".")


def robustez(t: pd.DataFrame) -> None:
    st.subheader("Quem fica entre os três primeiros nos 5.000 cenários")
    freq = t[t["elegivel"]][["municipio", "freq_top3"]]
    ui.grafico(graficos.robustez(freq, ru.decisao()["destaques"]),
               "Cenários sorteados com a semente 20261030, variando normalização, pesos, janelas, compostos, máscaras, "
               "unidades de conservação, faixa ripária, forma do A1, relevo e a incerteza da correção do Restaurar; "
               "travas aplicadas em cada cenário.")


def tabela_faixas(t: pd.DataFrame) -> None:
    med = ru.medianas(t)
    st.subheader("Todos os municípios")
    st.markdown("Os 16 elegíveis aparecem em três faixas, sempre em ordem alfabética: os destaques, os três seguintes no "
                "caso-base e os demais. Cada indicador vem comparado à mediana dos 16 elegíveis: ▲ melhor que a mediana, "
                "▼ pior. Os três municípios de porção pequena vêm à parte.")
    for faixa in ru.FAIXAS:
        sub = t[t["faixa"] == faixa]
        linhas = []
        for _, r in sub.iterrows():
            lin = {"Município": r["municipio"]}
            for col, frente, _, _, casas, menor in ru.INDICADORES:
                lin[f"{col} ({frente})"] = f"{fmt(r[col], casas)} {ru.SIMBOLO[ru.comparar(r[col], med[col], menor)]}"
            if r["elegivel"]:
                lin["Entre os 3 primeiros"] = pct(100 * r["freq_top3"])
            linhas.append(lin)
        st.markdown(f"**{TITULO_FAIXA[faixa]}**")
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch", height=35 * (len(linhas) + 1) + 3,
                     column_config={"Município": st.column_config.TextColumn(pinned=True, width="medium")})
    trav = [f"{r['municipio']} {ru.travas(r)}" for _, r in t.iterrows() if ru.travas(r)]
    if trav:
        st.markdown("**Travas no caso-base.** " + ". ".join(trav) + ". Nos cenários em que a trava vale, o município fica "
                    "fora dos três primeiros.")
    mtx = "; ".join(f"{col} {fmt(med[col], casas)}" for col, _, _, _, casas, _ in ru.INDICADORES)
    st.caption(f"Medianas dos 16 elegíveis: {mtx}. P1: supressão de floresta de 2017 a 2024, % ao ano (menor é melhor). "
               "R1: regeneração persistente das coortes de 2017 a 2022, % (com a correção da auditoria). A1: recuperação "
               "do déficit de vegetação nativa na faixa ripária de 2015 a 2024, %. A2: vegetação nativa na faixa "
               f"ripária em 2024, %. Taxa de supressão da bacia, base da trava: "
               f"{fmt(ru.decisao()['taxa_regional_p1'], 3)}% ao ano.")


def auditoria() -> None:
    f = dados.ranking("fatores_pm_publicacao.csv")
    tot = f[["manchas_inspecionadas", "real", "plantio", "erro_classe", "inconclusivo", "sem_imagem"]].sum()
    sem_juizo = tot["inconclusivo"] + tot["sem_imagem"]
    st.subheader("Auditoria e correção")
    st.markdown("Antes de premiar, conferimos em imagens de 30 a 50 cm os 10 maiores polígonos de perda e os 10 maiores "
                "de ganho de floresta de cada um dos cinco primeiros do caso-base, 100 polígonos ao todo. O mapa contava "
                "plantios comerciais e erros de classificação como floresta recuperada (32% da área conferida, acima do "
                "limite de 30% fixado antes dos resultados) e, como o protocolo já previa, o cálculo foi corrigido para "
                "os 19 municípios.")
    st.markdown("A correção tem duas partes. Os eventos só contam quando persistem: supressão em área com floresta nos "
                "dois anos anteriores e sem floresta no ano seguinte; regeneração sobre uso agropecuário em 2014, 2015 e "
                "2016 e com floresta em 2023, 2024 e 2025. E o Restaurar de cada município é descontado da fração do "
                "ganho de floresta que é plantio ou erro de classe, estimada por amostra de "
                f"{fmt(tot['manchas_inspecionadas'])} manchas. Foram conferidas "
                f"{fmt(tot['manchas_inspecionadas'] - tot['sem_imagem'])} em imagens de alta resolução de antes e depois, "
                f"sem que o revisor soubesse o município: {fmt(tot['real'])} regenerações reais, {fmt(tot['plantio'])} "
                f"plantios, {fmt(tot['erro_classe'])} erros de classe e {fmt(tot['inconclusivo'])} inconclusivas. As "
                f"{fmt(tot['sem_imagem'])} manchas sem imagem nas janelas de data contam como inconclusivas.")
    ui.nota(f"Ressalvas. As manchas que a imagem não permitiu julgar ({fmt(sem_juizo)} das "
            f"{fmt(tot['manchas_inspecionadas'])}, {pct(100 * sem_juizo / tot['manchas_inspecionadas'], 0)}) contaram como "
            "regeneração real, regra fixada antes do resultado; o limite com elas contadas como artefato vai na tabela "
            "abaixo, e o resultado é sensível a essa escolha. Erros de classificação na supressão de floresta não foram "
            "corrigidos e tendem a penalizar, não a favorecer, o município. Plantios na faixa ripária não foram "
            "descontados dos indicadores de beira de rio.")
    with st.expander("Fração descontada do Restaurar em cada município"):
        tab = f[["municipio", "manchas_inspecionadas", "real", "plantio", "erro_classe", "inconclusivo", "sem_imagem"]].copy()
        for col in ("p_m", "p_m_ic95_inf", "p_m_ic95_sup", "p_m_limite_superior"):
            tab[col] = 100 * f[col]
        tab = tab.sort_values("municipio", key=lambda s: s.map(dados.ordem_alfabetica)).rename(columns={
            "municipio": "Município", "manchas_inspecionadas": "Manchas", "real": "Reais", "plantio": "Plantio",
            "erro_classe": "Erro de classe", "inconclusivo": "Inconclusivas", "sem_imagem": "Sem imagem",
            "p_m": "Fração descontada (%)", "p_m_ic95_inf": "IC 95%, de (%)", "p_m_ic95_sup": "IC 95%, até (%)",
            "p_m_limite_superior": "Inconclusivas como artefato (%)"})
        ui.tabela(tab, {c: 1 for c in tab.columns if c.endswith("(%)")},
                  column_config={"Município": st.column_config.TextColumn(pinned=True)})
        st.caption("Inconclusiva conta como não artefato, como fixado antes do cálculo; a última coluna mostra o limite "
                   "com as inconclusivas contadas como artefato. O intervalo de 95% vem da parte sorteada da área de ganho.")


def downloads() -> None:
    st.subheader("Dados do ranking")
    arquivos = [("indicadores_19_publicacao.csv", "Indicadores, faixas e território avaliado dos 19"),
                ("robustez_familias.csv", "Robustez por família de fator"),
                ("fatores_pm_publicacao.csv", "Correção do Restaurar por município"),
                ("indicadores_antes_da_correcao.csv", "Indicadores antes da correção")]
    c = st.columns(2)
    for i, (nome_, rot) in enumerate(arquivos):
        c[i % 2].download_button(rot, dados.arquivo("ranking", nome_), file_name=nome_, mime="text/csv", width="stretch",
                                 icon=":material/download:")


def pagina() -> None:
    st.title("Ranking Ambiental CBH-MPS 2026")
    st.markdown(INTRO)
    if not dados.ranking_disponivel():
        st.info("O resultado do Ranking Ambiental CBH-MPS 2026 será anunciado no XI Simpósio Água Boa, em 30 de outubro "
                "de 2026, no SESC Barra Mansa.", icon=":material/event:")
        metodo()
        return
    t = ru.tabela()
    destaques(t)
    robustez(t)
    tabela_faixas(t)
    auditoria()
    metodo()
    downloads()
