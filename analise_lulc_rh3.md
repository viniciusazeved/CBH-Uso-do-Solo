# Análise de Uso e Cobertura do Solo - RH3 (Médio Paraíba do Sul)

## Objetivo

Realizar uma análise completa de uso e cobertura do solo dos municípios inseridos (total ou parcialmente) na **Região Hidrográfica 3 (RH3) — Médio Paraíba do Sul**, utilizando dados do **MapBiomas Coleção 9** (1985–2023). O resultado final será um **ranking municipal** com diversos índices ambientais para premiação do **Comitê de Bacias (CEIVAP)**.

---

## Regra Fundamental de Recorte

- O limite mandatório é o da **RH3**, não o do município.
- Municípios parcialmente inseridos devem ter sua geometria **recortada (clipped)** pelo limite da RH3.
- Toda a análise deve considerar apenas a **porção do município dentro da RH3**.

---

## Etapa 1 — Obtenção e Preparação dos Dados Vetoriais

### 1.1 Limite da RH3

Obter o shapefile da Região Hidrográfica 3 (Médio Paraíba do Sul). Fontes possíveis:

1. **CEIVAP / ANA**: Buscar no GeoNetwork da ANA ou site do CEIVAP
2. **Google Earth Engine**: Asset `projects/mapbiomas-workspace/AUXILIAR/regioes-hidrograficas` (verificar disponibilidade)
3. **Download direto da ANA**: https://metadados.snirh.gov.br/ — buscar "Regiões Hidrográficas Estaduais" ou "Ottobacias"
4. **IGBP / IBGE**: Regiões hidrográficas do estado do RJ/SP

> **Se nenhuma fonte automática estiver disponível**: O operador deve fornecer o shapefile da RH3 manualmente. Coloque o arquivo em `./data/rh3/` com nome `rh3_limite.shp` (e arquivos auxiliares .dbf, .shx, .prj).

**Alternativa prática via GEE:** Usar a base de ottobacias nível 2 da ANA e filtrar pela região do Médio Paraíba do Sul, ou usar o asset:
```
ANA_ottobacia_nivel_2 → filtrar por nome "Médio Paraíba do Sul"
```

### 1.2 Municípios (IBGE)

```python
# No GEE, usar o asset oficial do IBGE:
municipios = ee.FeatureCollection("projects/mapbiomas-workspace/AUXILIAR/municipios-2022")
# Alternativa:
municipios = ee.FeatureCollection("FAO/GAUL/2015/level2")  # menos preciso
```

Ou baixar do IBGE: https://www.ibge.gov.br/geociencias/organizacao-do-territorio/malhas-territoriais.html

### 1.3 Clip dos Municípios pela RH3

```python
import geopandas as gpd

# Carregar dados
rh3 = gpd.read_file("./data/rh3/rh3_limite.shp")
municipios = gpd.read_file("./data/municipios/municipios.shp")

# Garantir mesmo CRS
municipios = municipios.to_crs(rh3.crs)

# Identificar municípios que intersectam a RH3
munic_rh3 = gpd.overlay(municipios, rh3, how="intersection")

# Calcular área dentro da RH3 para cada município (em km²)
munic_rh3 = munic_rh3.to_crs(epsg=31983)  # SIRGAS 2000 / UTM 23S
munic_rh3["area_na_rh3_km2"] = munic_rh3.geometry.area / 1e6

# Salvar
munic_rh3.to_file("./data/municipios_clipped_rh3.shp")
print(f"Total de municípios na RH3: {len(munic_rh3)}")
```

---

## Etapa 2 — Extração de Dados MapBiomas via Google Earth Engine

### 2.1 Setup do GEE

```python
import ee
import geemap
import pandas as pd
import numpy as np

ee.Authenticate()
ee.Initialize(project='SEU_PROJETO_GEE')
```

### 2.2 Carregar Assets

```python
# MapBiomas Coleção 9
mapbiomas = ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1")

# Verificar bandas disponíveis (classification_1985 até classification_2023)
print(mapbiomas.bandNames().getInfo())
```

### 2.3 Definir Classes MapBiomas (Coleção 9)

```python
# Agrupamento de classes MapBiomas para análise
CLASSES = {
    "Floresta": [3, 4, 5, 6, 49],          # Formação Florestal, Savânica, Mangue, Floresta Alagada, Restinga Arbórea
    "Vegetacao_Natural_Nao_Florestal": [10, 11, 12, 13, 32, 50],  # Campo, Área Úmida, etc.
    "Silvicultura": [9],                     # Floresta Plantada
    "Pastagem": [15],                        # Pastagem
    "Agricultura": [18, 19, 20, 39, 40, 41, 46, 47, 48, 35, 36],  # Todas as culturas
    "Mosaico_Agropecuario": [21],            # Mosaico de Agricultura e Pastagem
    "Area_Urbana": [24],                     # Infraestrutura Urbana
    "Mineracao": [30],                       # Mineração
    "Agua": [26, 33],                        # Corpos d'água
    "Area_Nao_Vegetada": [22, 23, 25, 29],  # Praia, Dunas, Outros
    "Aquicultura": [31],                     # Aquicultura
    "Nao_Observado": [27]                    # Não Observado
}

# Classes de vegetação nativa (para índices de cobertura vegetal)
VEGETACAO_NATIVA = [3, 4, 5, 6, 10, 11, 12, 13, 32, 49, 50]

# Classes de uso antrópico
USO_ANTROPICO = [9, 15, 18, 19, 20, 21, 24, 30, 31, 35, 36, 39, 40, 41, 46, 47, 48]

# Classes florestais (mata)
FLORESTA = [3, 4, 5, 6, 49]
```

### 2.4 Extrair Estatísticas Zonais por Município e por Ano

```python
def extrair_lulc_por_municipio(municipios_fc, mapbiomas_img, ano):
    """
    Para cada município (já clippado pela RH3), calcula a área de cada classe LULC.
    """
    banda = f"classification_{ano}"
    classificacao = mapbiomas_img.select(banda)
    
    # Pixel area em hectares
    pixel_area = ee.Image.pixelArea().divide(10000)
    
    resultados = []
    
    for classe_nome, classe_ids in CLASSES.items():
        # Máscara para a classe
        mascara = classificacao.eq(classe_ids[0])
        for cid in classe_ids[1:]:
            mascara = mascara.Or(classificacao.eq(cid))
        
        # Área da classe
        area_classe = pixel_area.updateMask(mascara)
        
        # Estatísticas por município
        stats = area_classe.reduceRegions(
            collection=municipios_fc,
            reducer=ee.Reducer.sum(),
            scale=30,
            crs='EPSG:4326'
        )
        
        # Coletar resultados
        feat_list = stats.getInfo()['features']
        for feat in feat_list:
            resultados.append({
                'municipio': feat['properties'].get('NM_MUN', feat['properties'].get('name', 'NA')),
                'cod_ibge': feat['properties'].get('CD_MUN', feat['properties'].get('code', 'NA')),
                'ano': ano,
                'classe': classe_nome,
                'area_ha': feat['properties'].get('sum', 0) or 0
            })
    
    return resultados

# ============================================================
# EXECUÇÃO: Iterar sobre todos os anos (1985-2023)
# ============================================================
# ATENÇÃO: Esta extração é demorada. Recomenda-se:
# - Executar em lotes (ex: décadas)
# - Usar ee.batch.Export para exportar para Google Drive
# - Ou usar reduceRegions com anos selecionados

anos_analise = list(range(1985, 2024))  # 1985 a 2023

# Para análise simplificada (marcos temporais):
anos_marcos = [1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2023]

todos_resultados = []
for ano in anos_marcos:
    print(f"Processando ano {ano}...")
    res = extrair_lulc_por_municipio(municipios_fc, mapbiomas, ano)
    todos_resultados.extend(res)

df_lulc = pd.DataFrame(todos_resultados)
df_lulc.to_csv("./output/lulc_municipios_rh3.csv", index=False)
print(f"Total de registros: {len(df_lulc)}")
```

### 2.5 Alternativa: Exportação em Lote via GEE Tasks

```python
def exportar_lulc_batch(municipios_fc, mapbiomas_img, anos, pasta_drive="LULC_RH3"):
    """
    Exporta estatísticas zonais como CSV para o Google Drive.
    Mais robusto para grandes volumes de dados.
    """
    for ano in anos:
        banda = f"classification_{ano}"
        classificacao = mapbiomas_img.select(banda)
        pixel_area = ee.Image.pixelArea().divide(10000)
        
        # Criar imagem com uma banda por classe
        imagens_classes = []
        nomes_bandas = []
        for classe_nome, classe_ids in CLASSES.items():
            mascara = classificacao.eq(classe_ids[0])
            for cid in classe_ids[1:]:
                mascara = mascara.Or(classificacao.eq(cid))
            imagens_classes.append(pixel_area.updateMask(mascara).rename(classe_nome))
            nomes_bandas.append(classe_nome)
        
        img_empilhada = ee.Image(imagens_classes)
        
        stats = img_empilhada.reduceRegions(
            collection=municipios_fc,
            reducer=ee.Reducer.sum(),
            scale=30
        )
        
        task = ee.batch.Export.table.toDrive(
            collection=stats,
            description=f"LULC_RH3_{ano}",
            folder=pasta_drive,
            fileNamePrefix=f"lulc_rh3_{ano}",
            fileFormat='CSV'
        )
        task.start()
        print(f"Task exportação {ano} iniciada: {task.id}")
```

---

## Etapa 3 — Análise de Transições (Mudança de Classe)

### 3.1 Matriz de Transição entre Dois Períodos

```python
def calcular_transicao(mapbiomas_img, municipios_fc, ano_inicio, ano_fim):
    """
    Calcula a matriz de transição de LULC entre dois anos para cada município.
    Identifica: mata→pasto, pasto→mata, mata→urbano, etc.
    """
    class_ini = mapbiomas_img.select(f"classification_{ano_inicio}")
    class_fim = mapbiomas_img.select(f"classification_{ano_fim}")
    
    pixel_area = ee.Image.pixelArea().divide(10000)
    
    transicoes_interesse = {
        "Floresta_para_Pastagem": {"de": FLORESTA, "para": [15]},
        "Pastagem_para_Floresta": {"de": [15], "para": FLORESTA},
        "Floresta_para_Agricultura": {"de": FLORESTA, "para": [18, 19, 20, 39, 40, 41, 46, 47, 48, 35, 36]},
        "Floresta_para_Urbano": {"de": FLORESTA, "para": [24]},
        "Pastagem_para_Urbano": {"de": [15], "para": [24]},
        "Agricultura_para_Urbano": {"de": [18, 19, 20, 21, 39, 40, 41], "para": [24]},
        "VegNativa_para_Antropico": {"de": VEGETACAO_NATIVA, "para": USO_ANTROPICO},
        "Antropico_para_VegNativa": {"de": USO_ANTROPICO, "para": VEGETACAO_NATIVA},
        "Pastagem_para_Agricultura": {"de": [15], "para": [18, 19, 20, 39, 40, 41, 46, 47, 48, 35, 36]},
        "Silvicultura_para_Floresta": {"de": [9], "para": FLORESTA},
        "Floresta_para_Silvicultura": {"de": FLORESTA, "para": [9]},
    }
    
    resultados = []
    for trans_nome, trans_def in transicoes_interesse.items():
        # Máscara: pixel era classe X no ano_inicio E virou classe Y no ano_fim
        mascara_de = class_ini.eq(trans_def["de"][0])
        for c in trans_def["de"][1:]:
            mascara_de = mascara_de.Or(class_ini.eq(c))
        
        mascara_para = class_fim.eq(trans_def["para"][0])
        for c in trans_def["para"][1:]:
            mascara_para = mascara_para.Or(class_fim.eq(c))
        
        transicao = mascara_de.And(mascara_para)
        area_transicao = pixel_area.updateMask(transicao)
        
        stats = area_transicao.reduceRegions(
            collection=municipios_fc,
            reducer=ee.Reducer.sum(),
            scale=30
        )
        
        feat_list = stats.getInfo()['features']
        for feat in feat_list:
            resultados.append({
                'municipio': feat['properties'].get('NM_MUN', 'NA'),
                'cod_ibge': feat['properties'].get('CD_MUN', 'NA'),
                'transicao': trans_nome,
                'periodo': f"{ano_inicio}-{ano_fim}",
                'area_ha': feat['properties'].get('sum', 0) or 0
            })
    
    return pd.DataFrame(resultados)

# Períodos de análise
periodos = [
    (1985, 2000),   # Período histórico
    (2000, 2010),   # Década 2000
    (2010, 2020),   # Década 2010
    (2020, 2023),   # Período recente
    (1985, 2023),   # Período completo
]

df_transicoes = pd.DataFrame()
for ini, fim in periodos:
    print(f"Calculando transições {ini}-{fim}...")
    df_t = calcular_transicao(mapbiomas, municipios_fc, ini, fim)
    df_transicoes = pd.concat([df_transicoes, df_t], ignore_index=True)

df_transicoes.to_csv("./output/transicoes_municipios_rh3.csv", index=False)
```

---

## Etapa 4 — Cálculo dos Índices Municipais

### 4.1 Definição dos Índices

```python
def calcular_indices(df_lulc, df_transicoes):
    """
    Calcula todos os índices ambientais por município.
    Retorna DataFrame com ranking consolidado.
    """
    indices = []
    municipios = df_lulc['municipio'].unique()
    
    for mun in municipios:
        df_m = df_lulc[df_lulc['municipio'] == mun]
        df_t = df_transicoes[df_transicoes['municipio'] == mun]
        cod = df_m['cod_ibge'].iloc[0]
        
        registro = {'municipio': mun, 'cod_ibge': cod}
        
        # ============================================================
        # ÍNDICE 1: ICV — Índice de Cobertura Vegetal Nativa (% em 2023)
        # ============================================================
        # Proporção da área do município (na RH3) coberta por vegetação nativa
        area_total_2023 = df_m[df_m['ano'] == 2023]['area_ha'].sum()
        classes_veg = ['Floresta', 'Vegetacao_Natural_Nao_Florestal']
        area_veg_2023 = df_m[(df_m['ano'] == 2023) & (df_m['classe'].isin(classes_veg))]['area_ha'].sum()
        registro['ICV_2023_pct'] = (area_veg_2023 / area_total_2023 * 100) if area_total_2023 > 0 else 0
        
        # ============================================================
        # ÍNDICE 2: Variação da Cobertura Vegetal (1985–2023)
        # ============================================================
        area_veg_1985 = df_m[(df_m['ano'] == 1985) & (df_m['classe'].isin(classes_veg))]['area_ha'].sum()
        registro['variacao_veg_ha'] = area_veg_2023 - area_veg_1985
        registro['variacao_veg_pct'] = ((area_veg_2023 - area_veg_1985) / area_veg_1985 * 100) if area_veg_1985 > 0 else 0
        
        # ============================================================
        # ÍNDICE 3: Taxa de Recuperação Florestal Recente (2010–2023)
        # ============================================================
        area_flor_2010 = df_m[(df_m['ano'] == 2010) & (df_m['classe'] == 'Floresta')]['area_ha'].sum()
        area_flor_2023 = df_m[(df_m['ano'] == 2023) & (df_m['classe'] == 'Floresta')]['area_ha'].sum()
        registro['recup_florestal_2010_2023_ha'] = area_flor_2023 - area_flor_2010
        registro['recup_florestal_2010_2023_pct'] = (
            (area_flor_2023 - area_flor_2010) / area_flor_2010 * 100
        ) if area_flor_2010 > 0 else 0
        # Taxa anual média (ha/ano)
        registro['taxa_recup_florestal_ha_ano'] = (area_flor_2023 - area_flor_2010) / 13
        
        # ============================================================
        # ÍNDICE 4: Conversão Pasto → Mata (Regeneração)
        # ============================================================
        # Período completo
        t_pm = df_t[(df_t['transicao'] == 'Pastagem_para_Floresta') & (df_t['periodo'] == '1985-2023')]
        registro['pasto_para_mata_total_ha'] = t_pm['area_ha'].sum() if len(t_pm) > 0 else 0
        # Período recente
        t_pm_rec = df_t[(df_t['transicao'] == 'Pastagem_para_Floresta') & (df_t['periodo'] == '2010-2023')]  
        registro['pasto_para_mata_recente_ha'] = t_pm_rec['area_ha'].sum() if len(t_pm_rec) > 0 else 0
        
        # ============================================================
        # ÍNDICE 5: Conversão Mata → Pasto (Desmatamento para pastagem)
        # ============================================================
        t_mp = df_t[(df_t['transicao'] == 'Floresta_para_Pastagem') & (df_t['periodo'] == '1985-2023')]
        registro['mata_para_pasto_total_ha'] = t_mp['area_ha'].sum() if len(t_mp) > 0 else 0
        t_mp_rec = df_t[(df_t['transicao'] == 'Floresta_para_Pastagem') & (df_t['periodo'] == '2010-2023')]
        registro['mata_para_pasto_recente_ha'] = t_mp_rec['area_ha'].sum() if len(t_mp_rec) > 0 else 0
        
        # ============================================================
        # ÍNDICE 6: Saldo Líquido Florestal (Regeneração - Desmatamento)
        # ============================================================
        registro['saldo_florestal_total_ha'] = registro['pasto_para_mata_total_ha'] - registro['mata_para_pasto_total_ha']
        registro['saldo_florestal_recente_ha'] = registro['pasto_para_mata_recente_ha'] - registro['mata_para_pasto_recente_ha']
        
        # ============================================================
        # ÍNDICE 7: Crescimento Urbano
        # ============================================================
        area_urb_1985 = df_m[(df_m['ano'] == 1985) & (df_m['classe'] == 'Area_Urbana')]['area_ha'].sum()
        area_urb_2023 = df_m[(df_m['ano'] == 2023) & (df_m['classe'] == 'Area_Urbana')]['area_ha'].sum()
        registro['cresc_urbano_ha'] = area_urb_2023 - area_urb_1985
        registro['cresc_urbano_pct'] = (
            (area_urb_2023 - area_urb_1985) / area_urb_1985 * 100
        ) if area_urb_1985 > 0 else 0
        registro['area_urbana_2023_ha'] = area_urb_2023
        
        # ============================================================
        # ÍNDICE 8: Pressão Antrópica (% da área com uso antrópico)
        # ============================================================
        classes_antrop = ['Pastagem', 'Agricultura', 'Mosaico_Agropecuario', 'Area_Urbana', 
                          'Mineracao', 'Silvicultura']
        area_antrop_2023 = df_m[(df_m['ano'] == 2023) & (df_m['classe'].isin(classes_antrop))]['area_ha'].sum()
        registro['pressao_antropica_2023_pct'] = (area_antrop_2023 / area_total_2023 * 100) if area_total_2023 > 0 else 0
        
        area_antrop_1985 = df_m[(df_m['ano'] == 1985) & (df_m['classe'].isin(classes_antrop))]['area_ha'].sum()
        area_total_1985 = df_m[df_m['ano'] == 1985]['area_ha'].sum()
        registro['pressao_antropica_1985_pct'] = (area_antrop_1985 / area_total_1985 * 100) if area_total_1985 > 0 else 0
        registro['variacao_pressao_antropica_pp'] = registro['pressao_antropica_2023_pct'] - registro['pressao_antropica_1985_pct']
        
        # ============================================================
        # ÍNDICE 9: Índice de Diversidade de Uso do Solo (Shannon)
        # ============================================================
        areas_2023 = df_m[df_m['ano'] == 2023].groupby('classe')['area_ha'].sum()
        total = areas_2023.sum()
        if total > 0:
            props = areas_2023 / total
            props = props[props > 0]
            registro['shannon_2023'] = -np.sum(props * np.log(props))
        else:
            registro['shannon_2023'] = 0
        
        # ============================================================
        # ÍNDICE 10: Eficiência de Regeneração
        # ============================================================
        # Razão entre área regenerada (pasto→mata) e área desmatada (mata→pasto)
        if registro['mata_para_pasto_total_ha'] > 0:
            registro['eficiencia_regeneracao'] = (
                registro['pasto_para_mata_total_ha'] / registro['mata_para_pasto_total_ha']
            )
        else:
            registro['eficiencia_regeneracao'] = float('inf') if registro['pasto_para_mata_total_ha'] > 0 else 1.0
        
        # ============================================================
        # ÍNDICE 11: Conversão Líquida Veg. Nativa ↔ Antrópico
        # ============================================================
        t_va = df_t[(df_t['transicao'] == 'VegNativa_para_Antropico') & (df_t['periodo'] == '1985-2023')]
        t_av = df_t[(df_t['transicao'] == 'Antropico_para_VegNativa') & (df_t['periodo'] == '1985-2023')]
        veg_para_antrop = t_va['area_ha'].sum() if len(t_va) > 0 else 0
        antrop_para_veg = t_av['area_ha'].sum() if len(t_av) > 0 else 0
        registro['saldo_veg_nativa_total_ha'] = antrop_para_veg - veg_para_antrop
        
        # ============================================================
        # ÍNDICE 12: Intensidade de Uso Agropecuário
        # ============================================================
        area_agro_2023 = df_m[(df_m['ano'] == 2023) & (df_m['classe'].isin(['Pastagem', 'Agricultura', 'Mosaico_Agropecuario']))]['area_ha'].sum()
        area_agro_1985 = df_m[(df_m['ano'] == 1985) & (df_m['classe'].isin(['Pastagem', 'Agricultura', 'Mosaico_Agropecuario']))]['area_ha'].sum()
        registro['variacao_agropecuaria_ha'] = area_agro_2023 - area_agro_1985
        registro['variacao_agropecuaria_pct'] = (
            (area_agro_2023 - area_agro_1985) / area_agro_1985 * 100
        ) if area_agro_1985 > 0 else 0
        
        # ============================================================
        # ÍNDICE 13: Taxa de Desmatamento Recente (últimos 5 anos)
        # ============================================================
        t_desm_rec = df_t[(df_t['transicao'] == 'VegNativa_para_Antropico') & (df_t['periodo'] == '2020-2023')]
        registro['desmatamento_recente_ha'] = t_desm_rec['area_ha'].sum() if len(t_desm_rec) > 0 else 0
        registro['taxa_desmatamento_recente_ha_ano'] = registro['desmatamento_recente_ha'] / 3
        
        # ============================================================
        # ÍNDICE 14: Área de Água (variação — indicador de recursos hídricos)
        # ============================================================
        area_agua_1985 = df_m[(df_m['ano'] == 1985) & (df_m['classe'] == 'Agua')]['area_ha'].sum()
        area_agua_2023 = df_m[(df_m['ano'] == 2023) & (df_m['classe'] == 'Agua')]['area_ha'].sum()
        registro['variacao_agua_ha'] = area_agua_2023 - area_agua_1985
        registro['area_agua_2023_ha'] = area_agua_2023
        
        # Área total do município na RH3
        registro['area_total_na_rh3_ha'] = area_total_2023
        
        indices.append(registro)
    
    return pd.DataFrame(indices)
```

---

## Etapa 5 — Geração do Ranking

### 5.1 Categorias de Premiação

```python
def gerar_rankings(df_indices):
    """
    Gera rankings por categoria de premiação.
    """
    rankings = {}
    
    # ============================================================
    # PRÊMIO 1: Município mais Verde
    # Maior % de cobertura vegetal nativa em 2023
    # ============================================================
    rankings['municipio_mais_verde'] = df_indices.nlargest(10, 'ICV_2023_pct')[
        ['municipio', 'ICV_2023_pct', 'area_total_na_rh3_ha']
    ].reset_index(drop=True)
    
    # ============================================================
    # PRÊMIO 2: Maior Recuperação Florestal
    # Maior aumento absoluto de floresta (2010-2023)
    # ============================================================
    rankings['maior_recuperacao_florestal'] = df_indices.nlargest(10, 'recup_florestal_2010_2023_ha')[
        ['municipio', 'recup_florestal_2010_2023_ha', 'recup_florestal_2010_2023_pct', 'taxa_recup_florestal_ha_ano']
    ].reset_index(drop=True)
    
    # ============================================================
    # PRÊMIO 3: Maior Regeneração (Pasto → Mata)
    # Maior conversão de pastagem em floresta
    # ============================================================
    rankings['maior_regeneracao'] = df_indices.nlargest(10, 'pasto_para_mata_recente_ha')[
        ['municipio', 'pasto_para_mata_recente_ha', 'pasto_para_mata_total_ha']
    ].reset_index(drop=True)
    
    # ============================================================
    # PRÊMIO 4: Melhor Saldo Florestal
    # Maior saldo líquido (regeneração - desmatamento)
    # ============================================================
    rankings['melhor_saldo_florestal'] = df_indices.nlargest(10, 'saldo_florestal_recente_ha')[
        ['municipio', 'saldo_florestal_recente_ha', 'saldo_florestal_total_ha', 'eficiencia_regeneracao']
    ].reset_index(drop=True)
    
    # ============================================================
    # PRÊMIO 5: Menor Pressão Antrópica
    # Menor variação (ou redução) da pressão antrópica
    # ============================================================
    rankings['menor_pressao_antropica'] = df_indices.nsmallest(10, 'variacao_pressao_antropica_pp')[
        ['municipio', 'pressao_antropica_2023_pct', 'pressao_antropica_1985_pct', 'variacao_pressao_antropica_pp']
    ].reset_index(drop=True)
    
    # ============================================================
    # PRÊMIO 6: Menor Desmatamento Recente
    # Menor taxa de desmatamento nos últimos 3 anos
    # ============================================================
    rankings['menor_desmatamento_recente'] = df_indices.nsmallest(10, 'desmatamento_recente_ha')[
        ['municipio', 'desmatamento_recente_ha', 'taxa_desmatamento_recente_ha_ano']
    ].reset_index(drop=True)
    
    # ============================================================
    # DIAGNÓSTICO: Crescimento Urbano
    # Ranking de expansão urbana (informativo, não premiação)
    # ============================================================
    rankings['crescimento_urbano'] = df_indices.nlargest(10, 'cresc_urbano_ha')[
        ['municipio', 'cresc_urbano_ha', 'cresc_urbano_pct', 'area_urbana_2023_ha']
    ].reset_index(drop=True)
    
    # ============================================================
    # DIAGNÓSTICO: Maior Variação de Cobertura Vegetal (histórico)
    # ============================================================
    rankings['maior_variacao_veg_historica'] = df_indices.nlargest(10, 'variacao_veg_ha')[
        ['municipio', 'variacao_veg_ha', 'variacao_veg_pct']
    ].reset_index(drop=True)
    
    # ============================================================
    # ÍNDICE COMPOSTO: Score Ambiental Municipal
    # ============================================================
    df_score = df_indices.copy()
    
    # Normalizar indicadores (0-100, onde 100 = melhor desempenho ambiental)
    def normalizar(serie, inverter=False):
        """Min-max normalization. Se inverter=True, valores menores recebem score maior."""
        min_val = serie.min()
        max_val = serie.max()
        if max_val == min_val:
            return pd.Series([50] * len(serie), index=serie.index)
        normalizado = (serie - min_val) / (max_val - min_val) * 100
        return (100 - normalizado) if inverter else normalizado
    
    df_score['score_cobertura'] = normalizar(df_score['ICV_2023_pct'])
    df_score['score_recuperacao'] = normalizar(df_score['recup_florestal_2010_2023_ha'])
    df_score['score_regeneracao'] = normalizar(df_score['pasto_para_mata_recente_ha'])
    df_score['score_saldo'] = normalizar(df_score['saldo_florestal_recente_ha'])
    df_score['score_pressao'] = normalizar(df_score['variacao_pressao_antropica_pp'], inverter=True)
    df_score['score_desmatamento'] = normalizar(df_score['desmatamento_recente_ha'], inverter=True)
    
    # Score composto (pesos ajustáveis)
    pesos = {
        'score_cobertura': 0.20,
        'score_recuperacao': 0.20,
        'score_regeneracao': 0.15,
        'score_saldo': 0.15,
        'score_pressao': 0.15,
        'score_desmatamento': 0.15,
    }
    
    df_score['score_ambiental'] = sum(
        df_score[col] * peso for col, peso in pesos.items()
    )
    
    rankings['ranking_geral'] = df_score.nlargest(len(df_score), 'score_ambiental')[
        ['municipio', 'score_ambiental', 'score_cobertura', 'score_recuperacao',
         'score_regeneracao', 'score_saldo', 'score_pressao', 'score_desmatamento',
         'ICV_2023_pct', 'area_total_na_rh3_ha']
    ].reset_index(drop=True)
    
    return rankings, df_score
```

---

## Etapa 6 — Visualizações e Outputs

### 6.1 Gráficos

```python
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

def gerar_graficos(df_lulc, df_indices, rankings):
    """Gera todos os gráficos para o relatório."""
    
    # 1. Evolução temporal da cobertura florestal (RH3 inteira)
    fig, ax = plt.subplots(figsize=(14, 6))
    df_flor = df_lulc[df_lulc['classe'] == 'Floresta'].groupby('ano')['area_ha'].sum()
    ax.plot(df_flor.index, df_flor.values / 1000, 'g-o', linewidth=2, markersize=8)
    ax.set_xlabel('Ano', fontsize=12)
    ax.set_ylabel('Área Florestal (mil ha)', fontsize=12)
    ax.set_title('Evolução da Cobertura Florestal na RH3 — Médio Paraíba do Sul', fontsize=14)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    plt.savefig('./output/graficos/evolucao_florestal_rh3.png', dpi=200)
    plt.close()
    
    # 2. Top 10 municípios — Score Ambiental
    fig, ax = plt.subplots(figsize=(12, 8))
    top10 = rankings['ranking_geral'].head(10)
    colors = plt.cm.Greens(np.linspace(0.4, 0.9, 10))[::-1]
    bars = ax.barh(range(10), top10['score_ambiental'], color=colors)
    ax.set_yticks(range(10))
    ax.set_yticklabels(top10['municipio'], fontsize=11)
    ax.set_xlabel('Score Ambiental Composto', fontsize=12)
    ax.set_title('Top 10 Municípios — Ranking Ambiental RH3', fontsize=14)
    ax.invert_yaxis()
    for bar, val in zip(bars, top10['score_ambiental']):
        ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2, 
                f'{val:.1f}', va='center', fontsize=10)
    plt.tight_layout()
    plt.savefig('./output/graficos/ranking_ambiental_top10.png', dpi=200)
    plt.close()
    
    # 3. Composição LULC por município em 2023 (stacked bar)
    fig, ax = plt.subplots(figsize=(16, 10))
    df_2023 = df_lulc[df_lulc['ano'] == 2023].pivot_table(
        index='municipio', columns='classe', values='area_ha', fill_value=0
    )
    # Normalizar para %
    df_2023_pct = df_2023.div(df_2023.sum(axis=1), axis=0) * 100
    # Ordenar por % floresta
    df_2023_pct = df_2023_pct.sort_values('Floresta', ascending=True)
    
    cores_classes = {
        'Floresta': '#1f8d49',
        'Vegetacao_Natural_Nao_Florestal': '#7dc975',
        'Silvicultura': '#7a5900',
        'Pastagem': '#ffd966',
        'Agricultura': '#e974ed',
        'Mosaico_Agropecuario': '#ffefc3',
        'Area_Urbana': '#d4271e',
        'Mineracao': '#9c0027',
        'Agua': '#0000ff',
        'Area_Nao_Vegetada': '#d89f5c',
    }
    
    cols_plot = [c for c in cores_classes.keys() if c in df_2023_pct.columns]
    df_2023_pct[cols_plot].plot(
        kind='barh', stacked=True, ax=ax,
        color=[cores_classes[c] for c in cols_plot],
        figsize=(16, max(10, len(df_2023_pct) * 0.35))
    )
    ax.set_xlabel('Cobertura (%)', fontsize=12)
    ax.set_title('Composição do Uso e Cobertura do Solo por Município (2023) — RH3', fontsize=14)
    ax.legend(bbox_to_anchor=(1.02, 1), loc='upper left', fontsize=9)
    plt.tight_layout()
    plt.savefig('./output/graficos/composicao_lulc_municipios_2023.png', dpi=200, bbox_inches='tight')
    plt.close()
    
    # 4. Saldo florestal por município (barra divergente)
    fig, ax = plt.subplots(figsize=(14, 10))
    df_saldo = df_indices[['municipio', 'saldo_florestal_total_ha']].sort_values('saldo_florestal_total_ha')
    colors = ['#d4271e' if x < 0 else '#1f8d49' for x in df_saldo['saldo_florestal_total_ha']]
    ax.barh(range(len(df_saldo)), df_saldo['saldo_florestal_total_ha'], color=colors)
    ax.set_yticks(range(len(df_saldo)))
    ax.set_yticklabels(df_saldo['municipio'], fontsize=8)
    ax.axvline(x=0, color='black', linewidth=0.8)
    ax.set_xlabel('Saldo Florestal (ha) — Regeneração - Desmatamento', fontsize=12)
    ax.set_title('Saldo Florestal por Município (1985–2023) — RH3', fontsize=14)
    plt.tight_layout()
    plt.savefig('./output/graficos/saldo_florestal_municipios.png', dpi=200)
    plt.close()
    
    print("Gráficos salvos em ./output/graficos/")
```

### 6.2 Exportar Relatório Final

```python
def exportar_resultados(df_indices, rankings, df_lulc, df_transicoes):
    """Exporta todos os resultados em formato organizado."""
    
    import os
    os.makedirs('./output/graficos', exist_ok=True)
    os.makedirs('./output/tabelas', exist_ok=True)
    
    # Tabela completa de índices
    df_indices.to_csv('./output/tabelas/indices_municipais_rh3.csv', index=False, encoding='utf-8-sig')
    
    # Rankings individuais
    for nome, df_rank in rankings.items():
        df_rank.to_csv(f'./output/tabelas/ranking_{nome}.csv', index=False, encoding='utf-8-sig')
    
    # Dados brutos
    df_lulc.to_csv('./output/tabelas/lulc_completo_rh3.csv', index=False, encoding='utf-8-sig')
    df_transicoes.to_csv('./output/tabelas/transicoes_completas_rh3.csv', index=False, encoding='utf-8-sig')
    
    # Excel consolidado
    with pd.ExcelWriter('./output/ranking_ambiental_rh3.xlsx', engine='openpyxl') as writer:
        df_indices.to_excel(writer, sheet_name='Indices_Completos', index=False)
        rankings['ranking_geral'].to_excel(writer, sheet_name='Ranking_Geral', index=False)
        rankings['municipio_mais_verde'].to_excel(writer, sheet_name='Mais_Verde', index=False)
        rankings['maior_recuperacao_florestal'].to_excel(writer, sheet_name='Recuperacao_Florestal', index=False)
        rankings['maior_regeneracao'].to_excel(writer, sheet_name='Regeneracao', index=False)
        rankings['melhor_saldo_florestal'].to_excel(writer, sheet_name='Saldo_Florestal', index=False)
        rankings['menor_pressao_antropica'].to_excel(writer, sheet_name='Menor_Pressao', index=False)
        rankings['menor_desmatamento_recente'].to_excel(writer, sheet_name='Menor_Desmatamento', index=False)
        rankings['crescimento_urbano'].to_excel(writer, sheet_name='Cresc_Urbano', index=False)
    
    print("Resultados exportados em ./output/")
    print(f"  - Excel consolidado: ./output/ranking_ambiental_rh3.xlsx")
    print(f"  - CSVs individuais: ./output/tabelas/")
```

---

## Etapa 7 — Script Principal (main.py)

```python
"""
=============================================================================
ANÁLISE DE USO E COBERTURA DO SOLO — RH3 MÉDIO PARAÍBA DO SUL
Dados: MapBiomas Coleção 9 (1985–2023)
Objetivo: Ranking Municipal para Premiação CEIVAP
=============================================================================
"""

import ee
import geemap
import geopandas as gpd
import pandas as pd
import numpy as np
import os
import warnings
warnings.filterwarnings('ignore')

# ---- CONFIGURAÇÕES ----
PROJETO_GEE = 'SEU_PROJETO_GEE'  # <-- SUBSTITUIR
USAR_MARCOS_TEMPORAIS = True  # True = anos selecionados; False = todos os anos
SCALE = 30  # resolução em metros

# Criar diretórios
for d in ['./data', './output/graficos', './output/tabelas']:
    os.makedirs(d, exist_ok=True)

# ---- 1. INICIALIZAR GEE ----
ee.Authenticate()
ee.Initialize(project=PROJETO_GEE)
print("GEE inicializado com sucesso.")

# ---- 2. CARREGAR LIMITES ----
# Opção A: Usar asset do GEE (regiões hidrográficas)
# Ajustar conforme asset disponível
# rh3 = ee.FeatureCollection("...").filter(ee.Filter.eq('nome', 'Médio Paraíba do Sul'))

# Opção B: Upload de shapefile local
# rh3_gdf = gpd.read_file("./data/rh3/rh3_limite.shp")
# rh3 = geemap.gdf_to_ee(rh3_gdf)

# Municípios IBGE
municipios = ee.FeatureCollection("projects/mapbiomas-workspace/AUXILIAR/municipios-2022")

# ---- 3. CLIPAR MUNICÍPIOS PELA RH3 ----
# municipios_rh3 = municipios.map(lambda feat: feat.intersection(rh3.geometry()))

# ---- 4. CARREGAR MAPBIOMAS ----
mapbiomas = ee.Image("projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1")

# ---- 5. EXTRAIR DADOS ----
# ... (usar funções definidas nas etapas anteriores)

# ---- 6. CALCULAR ÍNDICES ----
# df_indices = calcular_indices(df_lulc, df_transicoes)

# ---- 7. GERAR RANKINGS ----
# rankings, df_score = gerar_rankings(df_indices)

# ---- 8. GERAR GRÁFICOS ----
# gerar_graficos(df_lulc, df_indices, rankings)

# ---- 9. EXPORTAR ----
# exportar_resultados(df_indices, rankings, df_lulc, df_transicoes)

print("Análise concluída!")
```

---

## Resumo dos Índices Propostos

| # | Índice | Descrição | Premiação |
|---|--------|-----------|-----------|
| 1 | ICV 2023 | % de cobertura vegetal nativa atual | Município Mais Verde |
| 2 | Variação Veg. Nativa | Mudança absoluta e relativa (1985–2023) | Maior Aumento de Cobertura |
| 3 | Recuperação Florestal | Aumento de floresta 2010–2023 (ha e taxa/ano) | Maior Recuperação |
| 4 | Pasto → Mata | Área convertida de pastagem para floresta | Maior Regeneração |
| 5 | Mata → Pasto | Área desmatada para pastagem | Diagnóstico |
| 6 | Saldo Florestal | Regeneração menos desmatamento (líquido) | Melhor Saldo |
| 7 | Crescimento Urbano | Expansão de área urbana | Diagnóstico |
| 8 | Pressão Antrópica | % de uso antrópico e sua variação | Menor Pressão |
| 9 | Shannon | Diversidade de uso do solo | Diagnóstico |
| 10 | Eficiência de Regeneração | Razão regeneração/desmatamento | Diagnóstico |
| 11 | Saldo Veg. Nativa | Conversão líquida (veg. nativa ↔ antrópico) | Diagnóstico |
| 12 | Variação Agropecuária | Mudança na área agropecuária | Diagnóstico |
| 13 | Desmatamento Recente | Taxa nos últimos 3 anos (2020–2023) | Menor Desmatamento |
| 14 | Variação Água | Mudança em corpos d'água | Diagnóstico |
| ** | **Score Composto** | Combinação ponderada dos índices | **Ranking Geral** |

---

## Observações para Execução

1. **Autenticação GEE**: É necessário ter uma conta Google Earth Engine ativa e um projeto GCloud configurado.
2. **Limite da RH3**: O shapefile da RH3 precisa ser obtido (ANA, CEIVAP ou IGBP). Se não houver disponível no GEE, faça upload como asset.
3. **Tempo de processamento**: A extração para todos os municípios e anos pode levar horas. Recomendo começar com os anos-marco (1985, 1990, 1995, 2000, 2005, 2010, 2015, 2020, 2023).
4. **Exportação batch**: Para maior robustez, use `ee.batch.Export` ao invés de `getInfo()` para grandes volumes.
5. **Coleção 9**: O asset correto é `projects/mapbiomas-public/assets/brazil/lulc/collection9/mapbiomas_collection90_integration_v1`. Verificar se há versão mais recente.
6. **Escala**: 30m é a resolução nativa do MapBiomas (Landsat). Não alterar.
