"""
Auditoria de coerencia interna dos 4 indicadores novos do Score v2.
Valida invariantes logicas que DEVEM ser verdadeiras se o calculo estiver correto.
"""
import pandas as pd

CSV = "output/tabelas/indices_municipais_rh3.csv"
df = pd.read_csv(CSV, dtype={"cod_ibge": str})

print("=" * 70)
print("AUDITORIA — Indicadores Extras do Score v2 (4 indicadores novos)")
print("=" * 70)

falhas = []
warnings = []

# --- Check 1: Persistencia <= Cobertura Nativa 2023 ---
# Quem foi floresta nos 9 anos-marco e necessariamente floresta hoje (subset)
# Como ICV inclui floresta + veg nao florestal, e persistencia conta so floresta,
# entao persistencia % <= ICV % sempre.
print("\n[1] Persistencia Florestal <= ICV 2023 (subset logico)")
mask = df["persistencia_florestal_pct"] > df["ICV_2023_pct"] + 0.5  # tolerancia 0.5pp
if mask.any():
    falhas.append(("Persistencia > ICV", df[mask][["municipio", "persistencia_florestal_pct", "ICV_2023_pct"]]))
    print("  FAIL:", df[mask]["municipio"].tolist())
else:
    diffs = df["ICV_2023_pct"] - df["persistencia_florestal_pct"]
    print(f"  OK — diff (ICV - Persist): media {diffs.mean():.1f}pp, max {diffs.max():.1f}pp")

# --- Check 2: Estabilidade do Uso >= Persistencia Florestal ---
# Estabilidade conta qualquer classe estavel; persistencia apenas floresta estavel.
print("\n[2] Estabilidade do Uso >= Persistencia Florestal (Persist e subset)")
mask = df["persistencia_florestal_pct"] > df["estabilidade_uso_pct"] + 0.5
if mask.any():
    falhas.append(("Persistencia > Estabilidade", df[mask][["municipio", "persistencia_florestal_pct", "estabilidade_uso_pct"]]))
    print("  FAIL:", df[mask]["municipio"].tolist())
else:
    diffs = df["estabilidade_uso_pct"] - df["persistencia_florestal_pct"]
    print(f"  OK — diff (Estab - Persist): media {diffs.mean():.1f}pp, max {diffs.max():.1f}pp")

# --- Check 3: Maior Fragmento <= Area Florestal 2023 ---
# O maior patch nao pode ser maior que toda a floresta do municipio.
# area_florestal_2023_calc_ha = soma dos pixels floresta na mascara binaria usada (deve bater
# aprox com a area de Floresta do lulc_municipios_rh3.csv).
print("\n[3] Maior Fragmento Florestal <= Area Florestal Total 2023")
mask = df["maior_fragmento_florestal_ha"] > df["area_florestal_2023_calc_ha"] + 1.0
if mask.any():
    falhas.append(("Maior frag > total flor", df[mask][["municipio", "maior_fragmento_florestal_ha", "area_florestal_2023_calc_ha"]]))
    print("  FAIL:", df[mask]["municipio"].tolist())
else:
    ratios = df["maior_fragmento_florestal_ha"] / df["area_florestal_2023_calc_ha"].replace(0, 1)
    print(f"  OK — razao maior_frag / total_flor: media {ratios.mean():.1%}, max {ratios.max():.1%}")

# --- Check 4: area_florestal_2023_calc_ha bate com Floresta do lulc CSV (cross-check fonte) ---
print("\n[4] area_florestal_2023_calc_ha (mascara) ~~ Floresta 2023 (reduceRegions)")
df_lulc = pd.read_csv("output/lulc_municipios_rh3.csv", dtype={"cod_ibge": str})
flor_2023 = df_lulc[(df_lulc["ano"] == 2023) & (df_lulc["classe"] == "Floresta")].set_index("cod_ibge")["area_ha"]
df_check = df.set_index("cod_ibge")[["municipio", "area_florestal_2023_calc_ha"]].copy()
df_check["floresta_2023_lulc"] = flor_2023
df_check["diff_ha"] = df_check["area_florestal_2023_calc_ha"] - df_check["floresta_2023_lulc"]
df_check["diff_pct"] = df_check["diff_ha"] / df_check["floresta_2023_lulc"].replace(0, 1) * 100
max_diff_pct = df_check["diff_pct"].abs().max()
if max_diff_pct > 5:
    warnings.append(("Diff fontes floresta > 5%", df_check[df_check["diff_pct"].abs() > 5]))
    print(f"  WARN — max diff {max_diff_pct:.1f}% (tolerancia <5%)")
    print(df_check[df_check["diff_pct"].abs() > 5][["municipio", "area_florestal_2023_calc_ha", "floresta_2023_lulc", "diff_pct"]].to_string())
else:
    print(f"  OK — max diff {max_diff_pct:.2f}% entre mascara e reduceRegions")

# --- Check 5: num_fragmentos > 0 quando ha floresta ---
print("\n[5] num_fragmentos > 0 se area_florestal > 0")
mask = (df["area_florestal_2023_calc_ha"] > 0) & (df["num_fragmentos_florestais"] == 0)
if mask.any():
    falhas.append(("Fragmentos 0 com area >0", df[mask][["municipio", "area_florestal_2023_calc_ha", "num_fragmentos_florestais"]]))
    print("  FAIL:", df[mask]["municipio"].tolist())
else:
    print(f"  OK — todos os municipios com floresta tem >= 1 fragmento")

# --- Check 6: tamanho medio dos fragmentos = total/n ---
print("\n[6] Sanity check: tamanho medio = area total / num fragmentos")
df["tam_medio_calc"] = df["area_florestal_2023_calc_ha"] / df["num_fragmentos_florestais"].replace(0, 1)
print(df[["municipio", "area_florestal_2023_calc_ha", "num_fragmentos_florestais",
         "maior_fragmento_florestal_ha", "tam_medio_calc"]].sort_values(
         "maior_fragmento_florestal_ha", ascending=False).head(10).to_string(index=False))

# --- Resumo ---
print("\n" + "=" * 70)
if falhas:
    print(f"AUDITORIA: {len(falhas)} FALHA(S) ENCONTRADA(S)")
    for nome, sub in falhas:
        print(f"\n>>> {nome}:")
        print(sub.to_string(index=False))
elif warnings:
    print(f"AUDITORIA: PASSOU com {len(warnings)} WARNING(S) — verificar contexto")
else:
    print("AUDITORIA: PASSOU em todas as checagens de coerencia interna")
print("=" * 70)
