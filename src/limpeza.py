"""Limpeza dos microdados da SSP-RS e criacao dos atributos usados na analise.

Entrada: data/raw/ssp_rs_<ano>.csv (ver src/carga.py)
Saida:   data/interim/<municipio>.parquet e os CSVs de auditoria em data/processed/

Uso:
    python src/limpeza.py
    python src/limpeza.py --municipio "CAXIAS DO SUL" --anos 2024 2025
"""

from __future__ import annotations

import argparse
import re
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
BRUTO = RAIZ / "data" / "raw"
INTERIM = RAIZ / "data" / "interim"
PROCESSADO = RAIZ / "data" / "processed"

COLUNAS = [
    "Sequência", "Data Fato", "Hora Fato", "Grupo Fato", "Tipo Enquadramento",
    "Tipo Fato", "Municipio Fato", "Local Fato", "Bairro", "Quantidade Vítimas",
]

# --- Bairro ---

# Abreviacoes de uma letra (P., M.) ficam de fora por serem ambiguas.
ABREVIACOES = {
    "VL": "VILA", "VLA": "VILA", "JD": "JARDIM", "JRD": "JARDIM", "PQ": "PARQUE",
    "PRQ": "PARQUE", "CJ": "CONJUNTO", "CEL": "CORONEL", "STO": "SANTO",
    "STA": "SANTA", "SR": "SENHOR", "SRA": "SENHORA", "NSRA": "SENHORA",
    "PROF": "PROFESSOR", "DR": "DOUTOR",
}

# Casos que a fusao por similaridade nao resolve com seguranca.
CORRECOES_BAIRRO = {
    # POA nao tem bairro oficial chamado so "CENTRO" (~3,7 mil registros).
    "CENTRO": "CENTRO HISTORICO",
    "PASSO DA AREIA": "PASSO D AREIA",
    "SANTA TERESA": "SANTA TEREZA",
    "M DEUS": "MENINO DEUS",
    "P BELAS": "PRAIA DE BELAS",
}

# Preenchimentos que equivalem a ausencia de bairro.
NAO_INFORMADO = re.compile(
    r"^(ZN INDEFINIDA.*|INDEFINID[OA].*|NAO INFORMADO.*|SEM INFORMACAO.*|"
    r"IGNORADO.*|CASA|OUTROS?|S/?N|NA|\d+)$"
)


def normalizar_texto(valor) -> str | None:
    """Maiusculas, sem acento, sem pontuacao, espacos colapsados."""
    if pd.isna(valor):
        return None
    texto = unicodedata.normalize("NFKD", str(valor)).encode("ascii", "ignore").decode()
    texto = re.sub(r"[^A-Za-z0-9 ]", " ", texto).upper()
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto or None


def expandir_abreviacoes(texto: str | None) -> str | None:
    if texto is None:
        return None
    palavras = [ABREVIACOES.get(p, p) for p in texto.split()]
    return " ".join(palavras)


def normalizar_bairro(valor) -> str | None:
    texto = expandir_abreviacoes(normalizar_texto(valor))
    if texto is None or NAO_INFORMADO.match(texto):
        return None
    return CORRECOES_BAIRRO.get(texto, texto)


def fundir_variantes(
    serie: pd.Series, limite_freq: int = 30, similaridade: float = 0.88
) -> tuple[dict[str, str], pd.DataFrame]:
    """Funde grafias raras em grafias frequentes quase identicas.

    A fusao e sempre no sentido raro -> frequente. Retorna o mapa aplicado e a
    tabela de auditoria correspondente.
    """
    contagem = serie.value_counts()
    frequentes = contagem[contagem >= limite_freq].index.tolist()
    raros = contagem[contagem < limite_freq].index.tolist()

    mapa: dict[str, str] = {}
    registros = []
    for raro in raros:
        melhor, escore = None, 0.0
        for alvo in frequentes:
            # Descarta candidatos de tamanho muito diferente antes do ratio.
            if abs(len(raro) - len(alvo)) > 4:
                continue
            atual = SequenceMatcher(None, raro, alvo).ratio()
            if atual > escore:
                melhor, escore = alvo, atual
        if melhor and escore >= similaridade:
            mapa[raro] = melhor
            registros.append(
                {"grafia_original": raro, "fundido_em": melhor,
                 "similaridade": round(escore, 3), "registros": int(contagem[raro])}
            )

    auditoria = pd.DataFrame(registros).sort_values("registros", ascending=False)
    return mapa, auditoria


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

def carregar_bruto(anos: list[int], municipio: str) -> pd.DataFrame:
    partes = []
    for ano in anos:
        caminho = BRUTO / f"ssp_rs_{ano}.csv"
        if not caminho.exists():
            raise FileNotFoundError(f"{caminho} nao encontrado - rode `python src/carga.py`")
        bruto = pd.read_csv(caminho, sep=";", encoding="latin1", low_memory=False,
                            usecols=lambda c: c in COLUNAS)
        alvo = bruto["Municipio Fato"].map(normalizar_texto) == normalizar_texto(municipio)
        parte = bruto.loc[alvo].copy()
        print(f"  {ano}: {len(bruto):>8,} linhas no estado -> {len(parte):>7,} em {municipio}")
        partes.append(parte)
    return pd.concat(partes, ignore_index=True)


def limpar(anos: list[int], municipio: str, cobertura: float = 0.80) -> pd.DataFrame:
    print(f"\n[1/5] Carregando {municipio}, anos {anos[0]}-{anos[-1]}")
    df = carregar_bruto(anos, municipio)
    n_inicial = len(df)

    print(f"\n[2/5] Duplicatas")
    df = df.drop_duplicates(subset=["Sequência", "Tipo Enquadramento", "Data Fato"])
    print(f"  removidas: {n_inicial - len(df):,}")

    print(f"\n[3/5] Atributos temporais")
    df = adicionar_features(df)
    sem_data = df["data"].isna().sum()
    sem_hora = df["hora"].isna().sum()
    print(f"  sem data: {sem_data:,} | sem hora: {sem_hora:,}")
    df = df.dropna(subset=["data", "hora"])

    print(f"\n[4/5] Bairro")
    df["bairro"] = df["Bairro"].map(normalizar_bairro)
    brutos = df["Bairro"].nunique()
    normalizados = df["bairro"].nunique()

    mapa, auditoria = fundir_variantes(df["bairro"].dropna())
    df["bairro"] = df["bairro"].replace(mapa)
    fundidos = df["bairro"].nunique()
    print(f"  grafias: {brutos} bruto -> {normalizados} normalizado -> {fundidos} apos fusao")
    print(f"  variantes fundidas: {len(mapa)} ({auditoria['registros'].sum() if len(auditoria) else 0} registros)")
    print(f"  sem bairro: {df['bairro'].isna().sum():,} ({df['bairro'].isna().mean():.1%})")

    # Mantem os bairros que somam `cobertura` dos registros; o resto vira OUTROS.
    contagem = df["bairro"].value_counts()
    acumulado = contagem.cumsum() / contagem.sum()
    principais = acumulado[acumulado <= cobertura].index.tolist()
    if len(principais) < len(contagem):
        principais = contagem.index[: len(principais) + 1].tolist()
    # Bairro ausente continua nulo; bairro raro vai para OUTROS. Sao casos
    # diferentes e a analise espacial trata cada um do seu jeito.
    df["bairro_principal"] = df["bairro"].where(df["bairro"].isin(principais), "OUTROS")
    df.loc[df["bairro"].isna(), "bairro_principal"] = None
    print(f"  top-{len(principais)} bairros = {contagem[principais].sum() / contagem.sum():.1%} dos registros com bairro")

    print(f"\n[5/5] Macrocategorias")
    df["macro"] = df["Tipo Enquadramento"].map(classificar_macro)
    df["crime_de_rua"] = df["macro"].isin(CRIMES_DE_RUA)
    df["local"] = df["Local Fato"].map(normalizar_texto)
    print(f"  {df['Tipo Enquadramento'].nunique()} tipos -> {df['macro'].nunique()} macrocategorias")
    print(f"  classificados como OUTROS: {(df['macro'] == 'OUTROS').mean():.1%}")
    print(f"  crimes de rua: {df['crime_de_rua'].mean():.1%} dos registros")

    df = df.rename(columns={"Tipo Enquadramento": "tipo", "Grupo Fato": "grupo",
                            "Tipo Fato": "consumado", "Quantidade Vítimas": "vitimas"})
    colunas = ["data", "ano", "mes", "dia_semana", "nome_dia", "fim_de_semana",
               "hora", "turno", "bairro", "bairro_principal", "macro", "tipo",
               "grupo", "consumado", "local", "crime_de_rua", "vitimas"]

    print(f"\nRESULTADO: {n_inicial:,} -> {len(df):,} registros ({len(df) / n_inicial:.1%} retidos)")

    PROCESSADO.mkdir(parents=True, exist_ok=True)
    if len(auditoria):
        auditoria.to_csv(PROCESSADO / "auditoria_fusao_bairros.csv", index=False)
    pd.DataFrame(
        {"tipo": df["tipo"].value_counts().index,
         "registros": df["tipo"].value_counts().values}
    ).assign(macro=lambda d: d["tipo"].map(classificar_macro)).to_csv(
        PROCESSADO / "auditoria_macrocategorias.csv", index=False
    )
    return df[colunas]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--municipio", default="PORTO ALEGRE")
    p.add_argument("--anos", nargs="+", type=int, default=[2022, 2023, 2024, 2025])
    p.add_argument("--cobertura", type=float, default=0.80)
    args = p.parse_args()

    df = limpar(args.anos, args.municipio, args.cobertura)

    INTERIM.mkdir(parents=True, exist_ok=True)
    saida = INTERIM / f"{normalizar_texto(args.municipio).lower().replace(' ', '_')}.parquet"
    df.to_parquet(saida, index=False)
    print(f"\nSalvo: {saida} ({saida.stat().st_size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
