from pathlib import Path
import unicodedata

import matplotlib.font_manager as fm
from matplotlib.ft2font import FT2Font
import matplotlib.pyplot as plt


def print_glyphs(path):
    if path is None:
        path = fm.findfont(fm.FontProperties())  # The default font.

    font = FT2Font(path)

    charmap = font.get_charmap()
    max_indices_len = len(str(max(charmap.values())))

    for char_code, glyph_index in charmap.items():
        char = chr(char_code)
        name = unicodedata.name(
            char,
            f"{char_code:#x} ({font.get_glyph_name(glyph_index)})")
        print(f"{glyph_index:>{max_indices_len}} {char} {name}")


def draw_font_table(path, labelr, labelc):
    if path is None:
        path = fm.findfont(fm.FontProperties())  # The default font.

    fig, ax = plt.subplots(figsize=(6, 3))
    ax.set_axis_off()

    table = ax.table(
        # cellText=[labelc] * 1,
        rowLabels=[labelc] * 1,
        colLabels=[labelr] * 1,
        # rowColours=["palegreen"],
        # colColours=[["palegreen"] * 4],
        cellColours=[[".95" for c in range(1)] for r in range(1)],
        # cellText='palegreen',
        cellLoc='center',
        loc='upper center',
    )

    for key, cell in table.get_celld().items():
        row, col = key
        if row > 0 and col > -1:  # Beware of table's idiosyncratic indexing...
            cell.set_text_props(font=Path(path))

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Display a font table.")
    parser.add_argument("path", nargs="?", help="Path to the font file.")
    parser.add_argument("--print-all", action="store_true",
                        help="Additionally, print all chars to stdout.")
    args = parser.parse_args()

