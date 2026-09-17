"""Limpeza dos microdados da SSP-RS e agregacao por municipio.

Recorte: estado inteiro do RS, unidade espacial = municipio (agrupado em
mesorregiao pela tabela do IBGE, ver src/ibge.py).

Entrada:
    data/raw/ssp_rs_<ano>.csv        (ver src/carga.py)
    data/processed/municipios_rs.csv (ver src/ibge.py -- pop. e mesorregiao)
Saida:
    data/interim/ocorrencias_rs.parquet   (nivel ocorrencia, estado todo)
    data/processed/municipios_taxa.csv     (agregado por municipio, com taxa/100k)
    data/processed/auditoria_macrocategorias.csv

Uso:
    python src/limpeza.py
    python src/limpeza.py --anos 2024 2025
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
BRUTO = RAIZ / "data" / "raw"
INTERIM = RAIZ / "data" / "interim"
PROCESSADO = RAIZ / "data" / "processed"
REF_MUNICIPIOS = PROCESSADO / "municipios_rs.csv"

COLUNAS = [
    "Sequência", "Data Fato", "Hora Fato", "Grupo Fato", "Tipo Enquadramento",
    "Tipo Fato", "Municipio Fato", "Local Fato", "Quantidade Vítimas",
]


# Grafias da SSP-RS que divergem do IBGE (aplicadas apos normalizar, antes do join).
CORRECOES_MUNICIPIO = {
    "SANTANA DO LIVRAMENTO": "SANT ANA DO LIVRAMENTO",
    "DR MAURICIO CARDOSO": "DOUTOR MAURICIO CARDOSO",
    "FAZENDA VILA NOVA": "FAZENDA VILANOVA",
    "PINTO BANDEIRA BENTO GONC": "PINTO BANDEIRA",
}


def normalizar_texto(valor) -> str | None:
    """Maiusculas, sem acento, sem pontuacao, espacos colapsados."""
    if pd.isna(valor):
        return None
    texto = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^A-Za-z0-9 ]", " ", texto).upper()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto or None


# --- Macrocategorias ---

# A primeira regra que casar define a categoria.
REGRAS_MACRO: list[tuple[str, str]] = [
    (r"LATROCINIO|HOMICIDIO DOLOSO|FEMINICIDIO", "CVLI"),
    (r"ROUBO.*VEICULO|ROUBO.*CARGA", "ROUBO_VEICULO"),
    (r"ROUBO A PEDESTRE|ROUBO DE CELULAR|ROUBO A TRANSPORTE", "ROUBO_RUA"),
    (r"ROUBO|EXTORSAO", "ROUBO_OUTROS"),
    (r"FURTO DE VEICULO|FURTO EM VEICULO|FURTO.*ESTEPE", "FURTO_VEICULO"),
    (r"ARROMBAMENTO", "FURTO_ARROMBAMENTO"),
    (r"FURTO", "FURTO_OUTROS"),
    (r"ENTORPECENTES", "DROGAS"),
    (r"ARMA DE FOGO|ARMA BRANCA", "ARMAS"),
    (r"CULPOSA DIRECAO|FUGA DE LOCAL|EMBRIAGUEZ|HABILITACAO|ART\. 30|ART 30", "TRANSITO"),
    (r"LESAO CORPORAL|VIAS DE FATO", "LESAO"),
    (r"AMEACA|MEDIDA PROTETIVA|VIOLENCIA PSICOLOGICA|PERSEGUICAO|MAUS TRATOS", "AMEACA_VD"),
    (r"ESTUPRO|IMPORTUNACAO SEXUAL|ASSEDIO", "SEXUAL"),
    (r"ESTELIONATO|FRAUDE|INVASAO DE DISPOSITIVO|APROPRIACAO|RECEPTACAO|FALSID|FALSA", "FRAUDE"),
    (r"INJURIA|CALUNIA|DIFAMACAO|PRECONCEITO|HOMOFOBIA|RACA COR", "HONRA_DISCRIM"),
    (r"DANO|INCENDIO|PATRIMONIO", "DANO"),
    (r"PERTURBACAO|DESACATO|DESOBEDIENCIA", "ORDEM_PUBLICA"),
]
REGRAS_COMPILADAS = [(re.compile(p), nome) for p, nome in REGRAS_MACRO]

# Categorias sensiveis a patrulhamento ostensivo. Fraude, crimes contra a honra
# e transito sao registrados na delegacia mas nao dependem de onde esta a viatura.
CRIMES_DE_RUA = {
    "CVLI", "ROUBO_VEICULO", "ROUBO_RUA", "ROUBO_OUTROS",
    "FURTO_VEICULO", "FURTO_ARROMBAMENTO", "FURTO_OUTROS", "LESAO", "DROGAS",
}


def classificar_macro(tipo) -> str:
    texto = normalizar_texto(tipo) or ""
    for padrao, nome in REGRAS_COMPILADAS:
        if padrao.search(texto):
            return nome
    return "OUTROS"


# --- Atributos temporais ---

DIAS = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]
TURNOS = ["madrugada", "manha", "tarde", "noite"]


def adicionar_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["data"] = pd.to_datetime(df["Data Fato"], format="%d/%m/%Y", errors="coerce")
    hora = pd.to_datetime(df["Hora Fato"], format="%H:%M:%S", errors="coerce")
    df["hora"] = hora.dt.hour

    df["ano"] = df["data"].dt.year
    df["mes"] = df["data"].dt.month
    df["dia_semana"] = df["data"].dt.dayofweek
    df["nome_dia"] = pd.Categorical(
        df["dia_semana"].map(dict(enumerate(DIAS))), categories=DIAS, ordered=True
    )
    df["fim_de_semana"] = df["dia_semana"] >= 5
    df["turno"] = pd.cut(
        df["hora"], bins=[-1, 5, 11, 17, 23], labels=TURNOS, ordered=True
    )
    return df


# --- Pipeline ---

def carregar_bruto(anos: list[int]) -> pd.DataFrame:
    """Carrega os anos pedidos (RS inteiro, sem filtro de municipio)."""
    partes = []
    for ano in anos:
        caminho = BRUTO / f"ssp_rs_{ano}.csv"
        if not caminho.exists():
            raise FileNotFoundError(f"{caminho} nao encontrado - rode `python src/carga.py`")
        bruto = pd.read_csv(caminho, sep=";", encoding="latin1", low_memory=False,
                            usecols=lambda c: c in COLUNAS)
        print(f"  {ano}: {len(bruto):>9,} linhas")
        partes.append(bruto)
    return pd.concat(partes, ignore_index=True)


def carregar_referencia() -> pd.DataFrame:
    if not REF_MUNICIPIOS.exists():
        raise FileNotFoundError(f"{REF_MUNICIPIOS} nao encontrado - rode `python src/ibge.py`")
    return pd.read_csv(REF_MUNICIPIOS)


def limpar(anos: list[int]) -> pd.DataFrame:
    print(f"\n[1/4] Carregando RS, anos {anos[0]}-{anos[-1]}")
    df = carregar_bruto(anos)
    n_inicial = len(df)

    print(f"\n[2/4] Duplicatas")
    df = df.drop_duplicates(subset=["Sequência", "Tipo Enquadramento", "Data Fato"])
    print(f"  removidas: {n_inicial - len(df):,}")

    print(f"\n[3/4] Atributos temporais")
    df = adicionar_features(df)
    sem_data = df["data"].isna().sum()
    sem_hora = df["hora"].isna().sum()
    print(f"  sem data: {sem_data:,} | sem hora: {sem_hora:,}")
    df = df.dropna(subset=["data", "hora"])

    print(f"\n[4/4] Municipio e macrocategorias")
    df["municipio"] = df["Municipio Fato"].map(normalizar_texto).replace(CORRECOES_MUNICIPIO)

    # Junta mesorregiao e populacao do IBGE pela grafia normalizada.
    ref = carregar_referencia()
    df = df.merge(
        ref[["municipio_norm", "cod_municipio", "mesorregiao", "populacao"]],
        left_on="municipio", right_on="municipio_norm", how="left",
    ).drop(columns="municipio_norm")

    sem_match = df["cod_municipio"].isna()
    nao_casados = sorted(df.loc[sem_match, "municipio"].dropna().unique())
    print(f"  municipios distintos: {df['municipio'].nunique()} | "
          f"sem match no IBGE: {len(nao_casados)} "
          f"({sem_match.mean():.2%} das ocorrencias)")
    if nao_casados:
        print(f"  nao casados: {', '.join(nao_casados[:15])}"
              f"{' ...' if len(nao_casados) > 15 else ''}")

    df["macro"] = df["Tipo Enquadramento"].map(classificar_macro)
    df["crime_de_rua"] = df["macro"].isin(CRIMES_DE_RUA)
    df["local"] = df["Local Fato"].map(normalizar_texto)
    print(f"  {df['Tipo Enquadramento'].nunique()} tipos -> {df['macro'].nunique()} macrocategorias"
          f" | OUTROS: {(df['macro'] == 'OUTROS').mean():.1%}"
          f" | crimes de rua: {df['crime_de_rua'].mean():.1%}")

    df = df.rename(columns={"Tipo Enquadramento": "tipo", "Grupo Fato": "grupo",
                            "Tipo Fato": "consumado", "Quantidade Vítimas": "vitimas"})
    colunas = ["data", "ano", "mes", "dia_semana", "nome_dia", "fim_de_semana",
               "hora", "turno", "municipio", "cod_municipio", "mesorregiao",
               "populacao", "macro", "tipo", "grupo", "consumado", "local",
               "crime_de_rua", "vitimas"]

    print(f"\nRESULTADO: {n_inicial:,} -> {len(df):,} registros ({len(df) / n_inicial:.1%} retidos)")
    return df[colunas]


def agregar_municipios(df: pd.DataFrame) -> pd.DataFrame:
    """Uma linha por municipio: contagens e taxa MEDIA ANUAL por 100 mil hab.

    Contagem bruta nao e comparavel entre municipios (o maior sempre lidera);
    a taxa por habitante e o que sustenta a priorizacao de recursos. A taxa e
    dividida pelo numero de anos do recorte para virar media anual -- assim o
    numerador (ocorrencias somadas de varios anos) fica na mesma escala do
    denominador (populacao de um ano) e o valor independe de quantos anos entram.
    """
    n_anos = df["ano"].nunique()
    casados = df[df["cod_municipio"].notna()]
    agg = casados.groupby(
        ["cod_municipio", "municipio", "mesorregiao", "populacao"], observed=True
    ).agg(
        n_ocorrencias=("macro", "size"),
        n_crime_rua=("crime_de_rua", "sum"),
    ).reset_index()

    agg["taxa_100k"] = agg["n_ocorrencias"] / agg["populacao"] / n_anos * 100_000
    agg["taxa_crime_rua_100k"] = agg["n_crime_rua"] / agg["populacao"] / n_anos * 100_000
    return agg.sort_values("taxa_100k", ascending=False)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--anos", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    args = p.parse_args()

    df = limpar(args.anos)
    municipios = agregar_municipios(df)

    INTERIM.mkdir(parents=True, exist_ok=True)
    PROCESSADO.mkdir(parents=True, exist_ok=True)

    saida = INTERIM / "ocorrencias_rs.parquet"
    df.to_parquet(saida, index=False)
    municipios.to_csv(PROCESSADO / "municipios_taxa.csv", index=False)
    pd.DataFrame(
        {"tipo": df["tipo"].value_counts().index,
         "registros": df["tipo"].value_counts().values}
    ).assign(macro=lambda d: d["tipo"].map(classificar_macro)).to_csv(
        PROCESSADO / "auditoria_macrocategorias.csv", index=False
    )

    print(f"\nSalvo: {saida} ({saida.stat().st_size / 1e6:.1f} MB)")
    print(f"Salvo: {PROCESSADO / 'municipios_taxa.csv'} ({len(municipios)} municipios)")
    print("\nTop 5 taxa/100k:")
    print(municipios.head(5)[["municipio", "mesorregiao", "populacao",
                              "n_ocorrencias", "taxa_100k"]].to_string(index=False))


if __name__ == "__main__":
    main()
