# Deploy do Painel Streamlit — Ranking Ambiental RH3

Instruções para rodar o painel no PC servidor.

## Arquivos necessários

Copie a seguinte estrutura de pastas para o servidor:

```
CBH_Uso_do_Solo/
├── painel.py
├── pyproject.toml
├── uv.lock
├── data/
│   ├── municipios_clipped_rh3.cpg
│   ├── municipios_clipped_rh3.dbf
│   ├── municipios_clipped_rh3.prj
│   ├── municipios_clipped_rh3.shp
│   └── municipios_clipped_rh3.shx
├── output/
│   ├── lulc_municipios_rh3.csv
│   ├── transicoes_municipios_rh3.csv
│   └── tabelas/
│       └── indices_municipais_rh3.csv
└── logo/
    ├── LOGO - CBH MPS - Branca.png
    └── LOGO - CBH MPS_colorida.png
```

Os demais arquivos (`main.py`, `shp/`, `output/graficos/`, `output/ranking_ambiental_rh3.xlsx`, etc.) não são necessários para o painel, apenas para a análise.

## Instalação

### 1. Instalar o UV (gerenciador de pacotes Python)

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Feche e reabra o terminal após a instalação.

### 2. Instalar Python 3.11+

```powershell
uv python install 3.11
```

### 3. Criar ambiente virtual e instalar dependências

Na pasta do projeto:

```powershell
cd C:\caminho\para\CBH_Uso_do_Solo
uv venv --python 3.11
```

O painel precisa de pacotes que não estão no `pyproject.toml` (streamlit, folium, openpyxl). Instale tudo de uma vez:

```powershell
uv pip install streamlit streamlit-folium geopandas pandas numpy plotly folium openpyxl
```

### 4. Rodar o painel

```powershell
$env:PYTHONUTF8=1
.venv\Scripts\python -m streamlit run painel.py --server.headless true
```

O painel sobe em `http://localhost:8501`.

Para acessar de outros PCs na rede local, use o endereço que aparece como "Network URL" no terminal (ex: `http://192.168.x.x:8501`).

## Rodar como serviço (iniciar automaticamente)

Para o painel iniciar junto com o Windows, crie um arquivo `iniciar_painel.bat`:

```bat
@echo off
set PYTHONUTF8=1
cd /d C:\caminho\para\CBH_Uso_do_Solo
.venv\Scripts\python -m streamlit run painel.py --server.headless true
```

Coloque um atalho desse `.bat` na pasta de inicialização do Windows:
`Win + R` → `shell:startup` → cole o atalho ali.

## Expor na internet (opcional)

Para acesso externo sem IP fixo, use ngrok:

```powershell
# Instalar
winget install ngrok.ngrok

# Criar túnel (após o painel estar rodando)
ngrok http 8501
```

O ngrok gera uma URL pública temporária. Para URL fixa, é necessário conta paga ou deploy no Streamlit Community Cloud.
