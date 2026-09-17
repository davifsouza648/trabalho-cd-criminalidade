"""Baixa de dados auxiliares do IBGE para o recorte RS por municipio.

Duas fontes, ambas publicas e sem chave (host servicodados.ibge.gov.br):
  1. API de Localidades  -> municipio -> mesorregiao / regiao intermediaria
  2. API v3 de Agregados -> populacao residente por municipio (Censo 2022)
     (o SIDRA classico esta atras de Cloudflare e bloqueia script; a API v3
      serve o mesmo dado sem esse bloqueio.)

Saida: data/processed/municipios_rs.csv, com uma linha por municipio do RS,
pronta para o join com as ocorrencias da SSP-RS pela coluna `municipio_norm`
(mesma normalizacao de `limpeza.normalizar_texto`).

Uso:
    python src/ibge.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import requests

from limpeza import normalizar_texto  # mesma normalizacao usada nas ocorrencias

RAIZ = Path(__file__).resolve().parents[1]
PROCESSADO = RAIZ / "data" / "processed"

UF_RS = 43
# Censo 2022: agregado 4714, variavel 93 = "Populacao residente (Pessoas)".
POP_TABELA, POP_VARIAVEL, POP_PERIODO = 4714, 93, 2022

LOCALIDADES = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{UF_RS}/municipios"
AGREGADOS = (
    f"https://servicodados.ibge.gov.br/api/v3/agregados/{POP_TABELA}"
    f"/periodos/{POP_PERIODO}/variaveis/{POP_VARIAVEL}?localidades=N6[all]"
)


def baixar_mesorregioes() -> pd.DataFrame:
    """municipio -> mesorregiao e regiao intermediaria (todos os municipios do RS)."""
    dados = requests.get(LOCALIDADES, timeout=120).json()
    linhas = [
        {
            "cod_municipio": m["id"],
            "municipio": m["nome"],
            "mesorregiao": m["microrregiao"]["mesorregiao"]["nome"],
            "regiao_intermediaria": m["regiao-imediata"]["regiao-intermediaria"]["nome"],
        }
        for m in dados
    ]
    return pd.DataFrame(linhas)


def baixar_populacao() -> pd.DataFrame:
    """Populacao residente por municipio (Censo 2022), so os do RS."""
    dados = requests.get(AGREGADOS, timeout=120).json()
    series = dados[0]["resultados"][0]["series"]
    linhas = [
        {"cod_municipio": int(s["localidade"]["id"]),
         "populacao": int(s["serie"][str(POP_PERIODO)])}
        for s in series
        if s["localidade"]["id"].startswith(str(UF_RS))
        and s["serie"][str(POP_PERIODO)].isdigit()
    ]
    return pd.DataFrame(linhas)


def montar() -> pd.DataFrame:
    meso = baixar_mesorregioes()
    pop = baixar_populacao()
    df = meso.merge(pop, on="cod_municipio", how="left")
    df["municipio_norm"] = df["municipio"].map(normalizar_texto)
    df["ano_populacao"] = POP_PERIODO
    return df[["cod_municipio", "municipio", "municipio_norm", "mesorregiao",
               "regiao_intermediaria", "populacao", "ano_populacao"]]


def main() -> None:
    df = montar()

    # Sanidade: o RS tem 497 municipios, todos com mesorregiao e populacao.
    assert len(df) == 497, f"esperava 497 municipios, veio {len(df)}"
    assert df["mesorregiao"].notna().all(), "municipio sem mesorregiao"
    assert df["populacao"].notna().all(), "municipio sem populacao"
    assert df["municipio_norm"].is_unique, "nome normalizado duplicado (quebra o join)"

    PROCESSADO.mkdir(parents=True, exist_ok=True)
    saida = PROCESSADO / "municipios_rs.csv"
    df.to_csv(saida, index=False)

    print(f"Salvo: {saida} ({len(df)} municipios)")
    print(f"  mesorregioes: {df['mesorregiao'].nunique()} | "
          f"pop. total RS: {df['populacao'].sum():,}")
    print(df.groupby("mesorregiao")["populacao"].agg(["count", "sum"]).to_string())


if __name__ == "__main__":
    main()
