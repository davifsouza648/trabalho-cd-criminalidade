"""Paleta e estilo dos graficos do trabalho.

Cores validadas para daltonismo e para contraste em fundo claro (a saida final
e impressa no relatorio).
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
from matplotlib.colors import LinearSegmentedColormap

RAIZ = Path(__file__).resolve().parents[1]
FIGURAS = RAIZ / "figuras"

TINTA = {
    "fundo": "#fcfcfb",
    "primaria": "#0b0b0b",
    "secundaria": "#52514e",
    "suave": "#898781",
    "grade": "#e1e0d9",
    "eixo": "#c3c2b7",
}

# Ordem fixa; a partir da 9a serie, agrupar em OUTROS.
SERIES = [
    "#2a78d6",  # 1 azul
    "#eb6834",  # 2 laranja
    "#1baf7a",  # 3 verde-agua
    "#eda100",  # 4 amarelo
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 verde
    "#4a3aa7",  # 7 violeta
    "#e34948",  # 8 vermelho
]

# Em dispersao todos os pares de cor competem entre si; so os 3 primeiros slots
# passam no teste de daltonismo nessa condicao. Acima disso, variar o marcador.
SERIES_DISPERSAO = SERIES[:3]
MARCADORES = ["o", "s", "^", "D", "v", "P"]

# Rampa sequencial para heatmaps.
RAMPA = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
CMAP = LinearSegmentedColormap.from_list("azul_seq", RAMPA)

# Divergente, para residuos padronizados (o cinza central marca o zero).
CMAP_DIVERGENTE = LinearSegmentedColormap.from_list(
    "div", ["#184f95", "#6da7ec", "#f0efec", "#e87ba4", "#d03b3b"]
)

DESTAQUE = "#eb6834"
NEUTRO = "#c3c2b7"

# Cor fixa por macrocategoria, para nao mudar de figura para figura.
CORES_MACRO = {
    "ROUBO_RUA": SERIES[0],
    "FURTO_OUTROS": SERIES[1],
    "LESAO": SERIES[2],
    "FRAUDE": SERIES[3],
    "AMEACA_VD": SERIES[4],
    "DROGAS": SERIES[5],
    "FURTO_VEICULO": SERIES[6],
    "ROUBO_VEICULO": SERIES[7],
}

ORDEM_TURNO = ["madrugada", "manha", "tarde", "noite"]
ORDEM_DIA = ["Segunda", "Terca", "Quarta", "Quinta", "Sexta", "Sabado", "Domingo"]


def cor_macro(nome: str) -> str:
    return CORES_MACRO.get(nome, NEUTRO)


def aplicar_estilo() -> None:
    mpl.rcParams.update({
        "figure.facecolor": TINTA["fundo"],
        "axes.facecolor": TINTA["fundo"],
        "savefig.facecolor": TINTA["fundo"],
        "figure.dpi": 110,
        "savefig.dpi": 200,
        "savefig.bbox": "tight",

        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 9,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.titlecolor": TINTA["primaria"],
        "axes.titlelocation": "left",
        "axes.titlepad": 10,
        "axes.labelsize": 9,
        "axes.labelcolor": TINTA["secundaria"],

        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.spines.left": False,
        "axes.edgecolor": TINTA["eixo"],
        "axes.linewidth": 0.8,

        "xtick.color": TINTA["suave"],
        "ytick.color": TINTA["suave"],
        "xtick.labelcolor": TINTA["secundaria"],
        "ytick.labelcolor": TINTA["secundaria"],
        "xtick.major.size": 0,
        "ytick.major.size": 0,

        "axes.grid": True,
        "axes.grid.axis": "y",
        "grid.color": TINTA["grade"],
        "grid.linewidth": 0.8,
        "axes.axisbelow": True,

        "legend.frameon": False,
        "legend.fontsize": 8.5,
        "legend.labelcolor": TINTA["secundaria"],

        "lines.linewidth": 2.0,
        "lines.markersize": 5,
        "axes.prop_cycle": mpl.cycler(color=SERIES),
    })


def titular(ax, titulo: str, subtitulo: str | None = None) -> None:
    ax.set_title(titulo, loc="left", pad=16 if subtitulo else 10)
    if subtitulo:
        ax.text(0, 1.02, subtitulo, transform=ax.transAxes, fontsize=8.5,
                color=TINTA["suave"], va="bottom")


def titular_figura(fig, titulo: str, subtitulo: str | None = None,
                   topo: float = 0.90) -> None:
    """Titulo e subtitulo para figuras com varios paineis.

    Nao usa suptitle: com dois textos na mesma faixa eles se sobrepoem.
    """
    fig.text(0.005, 0.985, titulo, ha="left", va="top", fontsize=11,
             fontweight="bold", color=TINTA["primaria"])
    if subtitulo:
        fig.text(0.005, 0.938, subtitulo, ha="left", va="top", fontsize=8.5,
                 color=TINTA["suave"])
    fig.tight_layout(rect=[0, 0, 1, topo])


def rotular_barras(ax, formato: str = "{:.0f}", horizontal: bool = False,
                   deslocamento: int = 4) -> None:
    """Escreve o valor na ponta da barra e dispensa o eixo correspondente."""
    for cont in ax.containers:
        ax.bar_label(cont, fmt=formato, padding=deslocamento, fontsize=8,
                     color=TINTA["secundaria"])
    if horizontal:
        ax.set_xticks([])
    else:
        ax.set_yticks([])


def limpar_grade(ax) -> None:
    ax.grid(False)


def salvar(fig, nome: str) -> Path:
    """Salva PNG para os slides e PDF vetorial para o relatorio."""
    FIGURAS.mkdir(parents=True, exist_ok=True)
    caminho = FIGURAS / f"{nome}.png"
    fig.savefig(caminho)
    fig.savefig(FIGURAS / f"{nome}.pdf")
    return caminho
