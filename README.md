# Criminalidade urbana no Rio Grande do Sul

Trabalho Final de **Ciência de Dados** (UNESP — Faculdade de Ciências, Bauru).
Tema 6 — *Criminalidade urbana por região*.

**Pergunta central:** no Rio Grande do Sul, os tipos de ocorrência têm padrão
espacial (município / mesorregião) e temporal (dia, horário) identificável, a
ponto de justificar priorização de recursos por região?

**Recorte:** todo o estado do RS, 2022–2025, agregado por município e agrupado
nas mesorregiões do IBGE, com taxa por 100 mil habitantes.

## Estrutura

```
├── src/
│   ├── carga.py      # baixa os microdados de ocorrências da SSP-RS
│   ├── ibge.py       # baixa população (Censo 2022) e mesorregiões do IBGE
│   └── limpeza.py    # limpa, classifica em macrocategorias e agrega por município
├── notebooks/
│   └── analise_criminalidade.ipynb   # EDA, figuras e testes de hipótese
├── figuras/          # figuras geradas (F1–F5), PNG e PDF
├── relatorio/
│   └── relatorio.tex # relatório técnico (LaTeX)
├── data/
│   ├── raw/          # microdados brutos (não versionado — reproduzir com carga.py)
│   ├── interim/      # ocorrências limpas (não versionado)
│   └── processed/    # tabelas auxiliares e agregadas (versionado)
└── requirements.txt
```

## Como rodar

```bash
# 1. Ambiente
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Dados auxiliares do IBGE (população + mesorregião)
python src/ibge.py

# 3. Microdados da SSP-RS (2022–2025) — ~800 MB, alguns minutos
python src/carga.py

# 4. Limpeza + agregação por município (gera o parquet e municipios_taxa.csv)
python src/limpeza.py

# 5. Análise (EDA, figuras, testes)
jupyter lab notebooks/analise_criminalidade.ipynb
# ou, sem interface:
jupyter nbconvert --to notebook --execute --inplace notebooks/analise_criminalidade.ipynb
```

## Fontes de dados

| Fonte | Conteúdo | Link | Acesso |
|---|---|---|---|
| **SSP-RS** — Secretaria da Segurança Pública do RS | Microdados de ocorrências criminais (2022–2025), todo o estado | https://ssp.rs.gov.br | 16/09/2026 |
| **IBGE** — Censo 2022 (API de Agregados) | População residente por município | https://servicodados.ibge.gov.br | 16/09/2026 |
| **IBGE** — API de Localidades | Correspondência município → mesorregião | https://servicodados.ibge.gov.br | 16/09/2026 |

Os dados são públicos e agregados/anonimizados (nenhum dado pessoal identificável).

## Autores

- Mário Masao Mukai
- Davi Ferreira de Souza

## Créditos

Paleta e estilo dos gráficos em `src/viz.py`. Bibliotecas: pandas, scipy,
scikit-learn, matplotlib (ver `requirements.txt`).
