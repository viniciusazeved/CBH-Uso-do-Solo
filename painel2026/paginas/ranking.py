"""Ranking Ambiental CBH-MPS 2026: destaques, robustez, faixas, auditoria e método.

Sem painel_dados/ranking/decisao.json, a página mostra só o método e a data do anúncio. Classificação do 1º ao 16º pelo
índice do caso-base, com a regra de empate técnico do protocolo (decisão da coordenação do GT SIGA, 17/11/2026); a frequência entre
os três primeiros nos 5.000 cenários vai ao lado, como medida de robustez."""

from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from .. import dados, graficos, ui
from .. import ranking_util as ru
from ..estilo import fmt, pct

INTRO = ("Os municípios com os melhores resultados de uso e cobertura do solo na sua porção da RH-III, nos mandatos de "
         "2017 a 2020 e de 2021 a 2024, em três frentes: proteger a floresta, restaurar o que foi aberto e recuperar "
         "a beira dos rios.")
HASHES = [("Protocolo v1.1, 14/10/2026", "4d185f25ab516e0544defff489bd8d3bff3ab6f7d8cedbf3a97f1cc32f11b066"),
          ("Adendo 1, 15/10/2026", "84939fa11e05d069c8d7454016f93b4e035e6551fe3c955dc71e3c5fa1b4a7ae"),
          ("Adendo 2, 15/10/2026", "0076d456ac06af727cbd74c22b71561011c9deaa2db4d9f316c5fb9e5ffd1a96")]
TITULO_FAIXA = {"1º ao 3º": "Do 1º ao 3º", "4º ao 6º": "Do 4º ao 6º", "7º ao 16º": "Do 7º ao 16º",
                "Porção pequena na RH-III": "Porção pequena na RH-III (concorrem a menção especial)"}


def metodo() -> None:
    st.subheader("O que o ranking mede")
    c = st.columns(3, gap="medium")
    frentes = [("Proteger", "35%", "P1, supressão de floresta: taxa em % ao ano, de 2017 a 2024. Menor é melhor."),
               ("Restaurar", "35%", "R1, regeneração persistente: pasto, lavoura ou mosaico que virou floresta de 2017 a "
                                    "2022 e continuou floresta até 2025, em proporção à área que havia para restaurar."),
               ("Abastecer", "30%", "A1, 20%: quanto da faixa dos rios e nascentes que estava sem vegetação nativa em "
                                    "2015 foi recuperado até 2024. A2, 10%: vegetação nativa na mesma faixa em 2024.")]
    for col, (titulo, peso, texto) in zip(c, frentes):
        with col.container(border=True):
            st.markdown(f"**{titulo}** · peso {peso}")
            st.markdown(texto)
    st.markdown("**Janelas de tempo.** O período é o dos dois últimos mandatos municipais, 2017 a 2020 e 2021 a 2024; cada "
                "frente usa o que o satélite consegue confirmar.")
    st.markdown("| Frente | Janela | Por quê |\n|---|---|---|\n"
                "| Proteger | Derrubada de floresta que se manteve, somada de 2017 a 2024 | Só conta a derrubada em floresta "
                "que existia nos dois anos anteriores e que seguiu sem floresta no ano seguinte; o mapa de 2025 só confirma as "
                "derrubadas de 2024. As derrubadas de 2025 ficam fora da soma: o registro do último ano ainda está incompleto "
                "(18% de um ano normal). |\n"
                "| Restaurar | Regeneração de 2017 a 2022, confirmada em 2023, 2024 e 2025 | Capoeira de um ou dois anos pode "
                "ser roçada de novo. Só conta a mata nova que seguiu floresta nos três anos; a que surgiu em 2023 e 2024 entra "
                "na próxima edição. |\n"
                "| Abastecer | Retrato de antes (2014 a 2016) e de depois (2023 a 2025) | Compara a vegetação nativa na faixa "
                "dos rios e nascentes antes e depois dos mandatos; cada retrato usa a classe mais frequente em três anos, o "
                "que reduz o erro de um ano isolado. |")
    st.caption("Testado: mudando só a janela (Proteger de 2015 ou de 2019 a 2024; Restaurar de 2015 ou de 2019 a 2022), os "
               "mesmos três municípios continuam nos três primeiros lugares em todos os casos.")
    st.markdown("**Cálculo, passo a passo.** 1) Posição: em cada indicador, os 16 municípios com 5.000 ha ou mais na RH-III "
                "vão do melhor ao pior. 2) Pontos = 100 × (16 − posição) ÷ 15: o 1º recebe 100 e o 16º recebe 0; cada posição "
                "vale 6,7 pontos. 3) Índice: soma dos pontos com os pesos 35% Proteger, 35% Restaurar, 20% e 10% Abastecer; "
                "é o índice do caso-base. 4) O cálculo é refeito em 5.000 cenários, variando a forma de pontuar, os pesos, as "
                "janelas e outras escolhas do método: robusto é ficar entre os três primeiros em 80% ou mais. Exemplo de um "
                "município hipotético:")
    ui.tabela(pd.DataFrame([("Proteger: supressão de floresta", "10º", 40.0, "35%", 14.0),
                            ("Restaurar: regeneração persistente", "1º", 100.0, "35%", 35.0),
                            ("Abastecer: recuperação ripária", "7º", 60.0, "20%", 12.0),
                            ("Abastecer: cobertura ripária", "5º", 73.3, "10%", 7.3),
                            ("Índice do município hipotético", "", None, "", 68.3)],
                           columns=["Indicador", "Posição", "Pontos", "Peso", "Contribuição"]),
              {"Pontos": 1, "Contribuição": 1})
    st.markdown("**Como pontua.** Em cada um dos quatro indicadores, os 16 municípios com pelo menos 5.000 ha na RH-III "
                "recebem uma posição, do melhor ao pior, que vira pontos de 0 a 100; o índice soma os pontos com pesos 35, "
                "35, 20 e 10: é o índice do caso-base. Diferença de índice menor que 2 pontos é empate técnico: fica à frente "
                "quem tem a menor taxa de supressão de floresta e, se ela também empatar, a maior recuperação ripária. "
                "Rio Claro, Miguel Pereira e Mendes têm porção pequena na bacia (menos de 5.000 ha), onde uma única "
                "propriedade muda a taxa: ficam fora da ordenação, têm os indicadores calculados e publicados e concorrem a "
                "menção especial. O critério é a área dentro da bacia, não a fração do município: Piraí (10,4 mil ha, 21% do "
                "município) e Três Rios (9,7 mil ha, 30%) entram.")
    st.markdown("**Travas.** Num cenário, não entra entre os três primeiros quem teve perda líquida de mais de 0,5% da "
                "floresta entre 2015 e 2024 ou supressão acima de 1,5 vez a taxa da bacia naquele cenário.")
    st.markdown("**Território avaliado.** A porção de cada município na RH-III, sem os parques federais e estaduais "
                "(Parque Nacional do Itatiaia e Parques Estaduais da Serra da Concórdia e da Pedra Selada), sem a "
                "silvicultura provável e sem água: fica o território que município e proprietários manejam.")
    st.markdown("**Por que confiar.** O protocolo foi fixado e registrado em 14/10/2026, com código de verificação, "
                "antes de qualquer resultado municipal ser visto. Dois adendos de 15/10/2026, também registrados antes de "
                "calcular as correções, definiram a conferência em alta resolução e a correção do Restaurar, que vale para "
                "os 19 municípios. O resultado foi testado em 5.000 cenários sorteados, variando normalização, pesos, "
                "janelas, compostos, máscaras, unidades de conservação, faixa ripária, forma do A1, relevo e a incerteza "
                "da correção: conta a frequência com que cada município fica entre os três primeiros, e 80% ou mais é "
                "resultado robusto. A classificação segue o índice do caso-base, com a regra de empate técnico do "
                "protocolo. O protocolo previa os três primeiros sem ordem quando a ordem mais frequente nos cenários "
                "ficasse abaixo da metade (ela apareceu em 18,7%); por decisão da coordenação do GT SIGA, de 17/11/2026, a "
                "classificação é publicada completa, do 1º ao 16º, com a frequência ao lado.")
    with st.expander("Códigos de verificação (SHA-256)"):
        st.markdown("\n".join(f"- {nome_}: `{h}`" for nome_, h in HASHES))
    ui.nota("O ranking mede resultados no território, observados por satélite; não mede políticas nem atribui autoria. "
            "Regeneração espontânea e decisões de proprietários também aparecem no mapa. As práticas que explicam os "
            "resultados, os próprios municípios contam.")


def destaques(t: pd.DataFrame) -> None:
    dec = ru.decisao()
    st.subheader("Os três primeiros")
    st.markdown(":orange-badge[Resultado provisório] pela metodologia abaixo (três frentes, quatro indicadores e "
                "seus pesos), sujeito à conferência dos dados pelos municípios.")
    tres = t[t["elegivel"]].sort_values("posicao_caso_base").head(3)
    cols = st.columns(3, gap="medium")
    for col, (_, linha) in zip(cols, tres.iterrows()):
        p = ru.postos(linha)
        with col.container(border=True):
            st.markdown(f"### {int(linha['posicao_caso_base'])}º {linha['municipio']}")
            st.metric("Índice no caso-base", fmt(linha["indice_caso_base"], 1),
                      f"entre os três primeiros em {pct(100 * linha['freq_top3'])} dos {fmt(dec['n_cenarios'])} cenários",
                      delta_color="off", delta_arrow="off")
            st.markdown(f"Posição entre os 16 em cada indicador: Proteger {ru.posto_txt(p['P1'])}, Restaurar "
                        f"{ru.posto_txt(p['R1'])}, Abastecer {ru.posto_txt(p['A1'])} (recuperação ripária) e "
                        f"{ru.posto_txt(p['A2'])} (cobertura ripária).")
    a, b = tres.iloc[0], tres.iloc[1]
    dif = b["indice_caso_base"] - a["indice_caso_base"]
    if 0 < dif < 2:     # empate técnico com o de trás tendo índice maior: a regra do protocolo vai à vista
        st.info(f"**Por que {a['municipio']} está à frente de {b['municipio']}.** Os dois estão em empate técnico: o índice "
                f"difere em {'menos de meio ponto' if dif < 0.5 else 'menos de 2 pontos'} ({fmt(a['indice_caso_base'], 1)} e "
                f"{fmt(b['indice_caso_base'], 1)}). Pela regra do protocolo, fixada antes dos resultados, dentro do empate "
                f"fica à frente quem tem a menor taxa de supressão de floresta: {a['municipio']}, com "
                f"{fmt(a['P1'], 3)}% ao ano, contra {fmt(b['P1'], 3)}% de {b['municipio']}.", icon=":material/balance:")
    st.caption(f"Resultados na porção de cada município na RH-III, nos mandatos de 2017 a 2020 e de 2021 a 2024 "
               f"(supressão de 2017 a 2024; regeneração das coortes de 2017 a 2022 que continuou floresta até 2025; beira "
               f"dos rios comparada entre 2015 e 2024). Ordem pelo índice do caso-base, com a regra de empate técnico do "
               f"protocolo. Os três "
               f"ficam entre os três primeiros em 80% ou mais dos {fmt(dec['n_cenarios'])} cenários; a ordem entre eles "
               f"muda conforme o cenário, e a mais frequente apareceu em {pct(100 * dec['freq_ordem_modal'])} deles.")
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
    st.subheader("Classificação dos 16 municípios")
    st.markdown("Posição e índice do caso-base. Índices a menos de 2 pontos um do outro são empate técnico, e dentro do "
                "empate fica à frente quem tem a menor taxa de supressão de floresta (regra do protocolo); por isso, num "
                "empate, quem está à frente pode ter índice menor. A coluna Empate técnico diz quais posições estão "
                "empatadas: 1º e 2º, 5º ao 7º, 9º ao 11º e 13º e 14º. A coluna Entre os 3 primeiros mostra em quantas das "
                "5.000 vezes em que o cálculo foi refeito, variando pesos, janelas e a forma de pontuar, o município ficou "
                "entre os três primeiros. Cada indicador vem comparado à mediana "
                "dos 16: ▲ melhor que a mediana, ▼ pior. Os três municípios de porção pequena na RH-III vêm à parte, fora "
                "da ordenação: com menos de 5.000 ha na bacia, uma única propriedade muda as taxas. O critério é a área "
                "dentro da bacia, não a fração do município: Piraí e Três Rios, também só em parte na RH-III, têm mais de "
                "9 mil ha nela.")
    grupos = [("Do 1º ao 16º no caso-base", t[t["elegivel"]].sort_values("posicao_caso_base")),
              (TITULO_FAIXA["Porção pequena na RH-III"], t[~t["elegivel"]])]
    emp = ru.empates(t)
    for titulo, sub in grupos:
        linhas = []
        for _, r in sub.iterrows():
            lin = {}
            if pd.notna(r.get("posicao_caso_base")):
                lin["Posição"] = f"{int(r['posicao_caso_base'])}º"
            lin["Município"] = r["municipio"]
            if pd.notna(r.get("indice_caso_base")):
                lin["Índice"] = fmt(r["indice_caso_base"], 1)
                lin["Empate técnico"] = emp.get(int(r["cod_ibge"]), "")
            for col, frente, _, _, casas, menor in ru.INDICADORES:
                lin[f"{col} ({frente})"] = f"{fmt(r[col], casas)} {ru.SIMBOLO[ru.comparar(r[col], med[col], menor)]}"
            if r["elegivel"]:
                lin["Entre os 3 primeiros"] = pct(100 * r["freq_top3"])
            linhas.append(lin)
        st.markdown(f"**{titulo}**")
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch", height=35 * (len(linhas) + 1) + 3,
                     column_config={"Posição": st.column_config.TextColumn(pinned=True, width="small"),
                                    "Município": st.column_config.TextColumn(pinned=True, width="medium")})
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
    arquivos = [("indicadores_19_publicacao.csv", "Indicadores, classificação e território avaliado dos 19"),
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
        st.info("O resultado do Ranking Ambiental CBH-MPS 2026 será divulgado depois que os municípios conferirem os "
                "seus dados. Abaixo, a metodologia.", icon=":material/event:")
        metodo()
        return
    t = ru.tabela()
    destaques(t)
    robustez(t)
    tabela_faixas(t)
    auditoria()
    metodo()
    downloads()
