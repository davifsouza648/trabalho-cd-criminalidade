
from __future__ import annotations

import sys
import zipfile
from pathlib import Path

import requests

BASE = "https://www.ssp.rs.gov.br/upload/arquivos/"

# Cada ano publicado como um ZIP unico contendo um CSV (;, latin-1, CRLF).
ARQUIVOS = {
    2021: "202201/25080213-dados-abertos-ocorrencias-2022-01-ajustado-publicacao.csv",  # out-dez/2021, CSV solto
    2022: "202607/09152511-spj-dados-abertos-ocorrencias-jan-dez-2022-em-23-06-2026.zip",
    2023: "202501/20100119-2023-janeiro-a-dezembro.zip",
    2024: "202601/16132801-spj-dados-abertos-ocorrencias-jan-dez-2024-em-05-01-2026.zip",
    2025: "202609/10164921-spj-dados-abertos-ocorrencias-jan-dez-2025-em-04-09-2026.zip",
    2026: "202609/10165031-spj-dados-abertos-ocorrencias-jan-ago-2026-em-04-09-2026.zip",  # parcial
}

ANOS_PADRAO = [2022, 2023, 2024, 2025]
DESTINO = Path(__file__).resolve().parents[1] / "data" / "raw"


def baixar(ano: int, destino: Path = DESTINO) -> Path:
    """Baixa (se ainda nao existir) e descompacta o arquivo do ano. Retorna o caminho do CSV."""
    if ano not in ARQUIVOS:
        raise ValueError(f"ano {ano} nao disponivel; opcoes: {sorted(ARQUIVOS)}")

    destino.mkdir(parents=True, exist_ok=True)
    url = BASE + ARQUIVOS[ano]
    bruto = destino / f"ssp_rs_{ano}{Path(url).suffix}"

    if not bruto.exists():
        print(f"[{ano}] baixando {url}")
        with requests.get(url, stream=True, timeout=300) as r:
            r.raise_for_status()
            with open(bruto, "wb") as fh:
                for bloco in r.iter_content(chunk_size=1 << 20):
                    fh.write(bloco)
        print(f"[{ano}] salvo em {bruto} ({bruto.stat().st_size / 1e6:.1f} MB)")
    else:
        print(f"[{ano}] ja existe, pulando download")

    if bruto.suffix.lower() != ".zip":
        return bruto

    # O nome do CSV dentro do ZIP varia; padronizamos na extracao.
    csv = destino / f"ssp_rs_{ano}.csv"
    if not csv.exists():
        with zipfile.ZipFile(bruto) as z:
            interno = next(n for n in z.namelist() if n.lower().endswith(".csv"))
            with z.open(interno) as origem, open(csv, "wb") as saida:
                saida.write(origem.read())
        print(f"[{ano}] extraido -> {csv} ({csv.stat().st_size / 1e6:.1f} MB)")
    return csv


def main(anos: list[int]) -> None:
    for ano in anos:
        baixar(ano)


if __name__ == "__main__":
    main([int(a) for a in sys.argv[1:]] or ANOS_PADRAO)
