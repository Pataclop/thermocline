"""Palette et feuille de style de l'interface.

Deux themes sont fournis. `use()` rebranche les couleurs du module sur l'un ou
l'autre; il faut l'appeler **avant** de construire la fenetre, parce que les
graphiques lisent ces couleurs au moment ou ils sont crees.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

#: Les petites fleches des listes et des compteurs. Qt cesse de dessiner les
#: siennes des qu'une feuille de style touche au widget: on lui fournit donc de
#: vraies images, fabriquees par `tools/make_icon.py`.
RESOURCES = Path(__file__).resolve().parent.parent / "resources"


def _arrow(name: str) -> str:
    """Chemin d'une fleche au format attendu par Qt, ou chaine vide."""
    path = RESOURCES / name
    # Qt veut des barres obliques, y compris sous Windows.
    return path.as_posix() if path.exists() else ""


@dataclass(frozen=True)
class Palette:
    """Un jeu de couleurs complet."""

    name: str
    # Fond et surfaces.
    bg: str
    panel: str
    panel_alt: str
    border: str
    hover: str
    pressed: str
    # Textes.
    text: str
    text_muted: str
    # Couleurs des series.
    depth: str
    depth_fill: str
    temp: str
    ppo2: str
    ascent: str
    descent: str
    warn: str
    good: str
    accent: str
    accent_strong: str
    grid: str
    safety: str
    selection: str
    row_alt: str
    series: tuple[str, ...] = field(
        default=(
            "#38bdf8",
            "#fb923c",
            "#a78bfa",
            "#4ade80",
            "#f472b6",
            "#facc15",
            "#22d3ee",
            "#fb7185",
        )
    )


DARK = Palette(
    name="dark",
    bg="#0f141b",
    panel="#161d27",
    panel_alt="#1d2632",
    border="#2a3542",
    hover="#26313f",
    pressed="#1a2230",
    text="#e6edf3",
    text_muted="#8b98a5",
    depth="#38bdf8",
    depth_fill="#38bdf833",
    temp="#fb923c",
    ppo2="#a78bfa",
    ascent="#22c55e",
    descent="#60a5fa",
    warn="#f87171",
    good="#4ade80",
    accent="#38bdf8",
    accent_strong="#0b6fa4",
    grid="#243040",
    safety="#22c55e22",
    selection="#0b4f75",
    row_alt="#19212c",
)

#: Theme clair, pour les ecrans tres lumineux et les captures d'ecran.
LIGHT = Palette(
    name="light",
    bg="#f5f7fa",
    panel="#ffffff",
    panel_alt="#eef2f7",
    border="#d3dae3",
    hover="#e2e8f0",
    pressed="#d7dee7",
    text="#16202b",
    text_muted="#5b6b7c",
    depth="#0a7ea4",
    depth_fill="#0a7ea433",
    temp="#c2410c",
    ppo2="#6d28d9",
    ascent="#15803d",
    descent="#1d4ed8",
    warn="#b91c1c",
    good="#15803d",
    accent="#0a7ea4",
    accent_strong="#0a7ea4",
    grid="#d3dae3",
    safety="#15803d22",
    selection="#bfdcea",
    row_alt="#f2f6fa",
    series=(
        "#0a7ea4",
        "#c2410c",
        "#6d28d9",
        "#15803d",
        "#be185d",
        "#a16207",
        "#0e7490",
        "#9f1239",
    ),
)

THEMES: dict[str, Palette] = {DARK.name: DARK, LIGHT.name: LIGHT}


def build_stylesheet(p: Palette) -> str:
    """Feuille de style Qt derivee d'une palette."""
    down, up = _arrow("arrow-down.png"), _arrow("arrow-up.png")
    arrows = (
        f"""
QComboBox::down-arrow, QSpinBox::down-arrow, QDoubleSpinBox::down-arrow {{
    image: url("{down}");
    width: 10px;
    height: 10px;
}}
QSpinBox::up-arrow, QDoubleSpinBox::up-arrow {{
    image: url("{up}");
    width: 10px;
    height: 10px;
}}
"""
        if down and up
        else ""
    )
    return arrows + f"""
QWidget {{
    background-color: {p.bg};
    color: {p.text};
    font-size: 13px;
}}
QMainWindow, QDialog {{ background-color: {p.bg}; }}

QToolBar {{
    background-color: {p.panel};
    border: none;
    border-bottom: 1px solid {p.border};
    padding: 6px 8px;
    spacing: 8px;
}}

QWidget#toolbarSpacer {{ background: transparent; }}

QMenuBar {{
    background-color: {p.panel};
    border-bottom: 1px solid {p.border};
}}
QMenuBar::item {{ background: transparent; padding: 6px 10px; }}
QMenuBar::item:selected {{ background: {p.hover}; }}
QMenu {{
    background-color: {p.panel_alt};
    border: 1px solid {p.border};
    padding: 4px;
}}
QMenu::item {{ padding: 6px 24px 6px 14px; border-radius: 4px; }}
QMenu::item:selected {{ background: {p.accent_strong}; color: #ffffff; }}
QMenu::separator {{ height: 1px; background: {p.border}; margin: 4px 8px; }}

QPushButton {{
    background-color: {p.panel_alt};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 6px 14px;
    color: {p.text};
}}
QPushButton:hover {{ background-color: {p.hover}; }}
QPushButton:pressed {{ background-color: {p.pressed}; }}
QPushButton:disabled {{ color: {p.text_muted}; background-color: {p.bg}; }}
QPushButton#primary {{
    background-color: {p.accent_strong};
    border-color: {p.accent};
    color: #ffffff;
    font-weight: 600;
}}
QPushButton#primary:hover {{ background-color: {p.accent}; }}
QPushButton#primary:disabled {{ background-color: {p.panel_alt}; color: {p.text_muted}; }}

QComboBox, QLineEdit, QTextEdit, QSpinBox, QDoubleSpinBox {{
    background-color: {p.panel_alt};
    border: 1px solid {p.border};
    border-radius: 6px;
    padding: 5px 8px;
    selection-background-color: {p.accent_strong};
}}
/* Les fleches sont posees plus haut, a partir d'images: Qt cesse de dessiner
   les siennes des que la feuille de style touche au widget. */
QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: center right;
    border: none;
    width: 22px;
}}
QComboBox QAbstractItemView {{
    background-color: {p.panel_alt};
    border: 1px solid {p.border};
    selection-background-color: {p.accent_strong};
}}

QSpinBox::up-button, QDoubleSpinBox::up-button {{
    subcontrol-origin: border;
    subcontrol-position: top right;
    width: 18px;
    margin: 2px 3px 0 0;
    border: none;
    background: transparent;
}}
QSpinBox::down-button, QDoubleSpinBox::down-button {{
    subcontrol-origin: border;
    subcontrol-position: bottom right;
    width: 18px;
    margin: 0 3px 2px 0;
    border: none;
    background: transparent;
}}
QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
    background-color: {p.hover};
}}

QTableView {{
    background-color: {p.panel};
    alternate-background-color: {p.row_alt};
    border: 1px solid {p.border};
    border-radius: 8px;
    gridline-color: {p.border};
    selection-background-color: {p.selection};
    selection-color: {p.text};
}}
QTableView::item {{ padding: 4px 6px; }}
QHeaderView::section {{
    background-color: {p.panel_alt};
    color: {p.text_muted};
    border: none;
    border-right: 1px solid {p.border};
    border-bottom: 1px solid {p.border};
    padding: 6px;
    font-weight: 600;
}}

QTabWidget::pane {{ border: 1px solid {p.border}; border-radius: 8px; top: -1px; }}
QTabBar::tab {{
    background: transparent;
    color: {p.text_muted};
    padding: 8px 16px;
    border-bottom: 2px solid transparent;
}}
QTabBar::tab:selected {{ color: {p.text}; border-bottom: 2px solid {p.accent}; }}
QTabBar::tab:hover {{ color: {p.text}; }}

QGroupBox {{
    border: 1px solid {p.border};
    border-radius: 8px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    left: 10px;
    padding: 0 6px;
    color: {p.text_muted};
}}

QStatusBar {{
    background-color: {p.panel};
    border-top: 1px solid {p.border};
    color: {p.text_muted};
}}
QProgressBar {{
    background-color: {p.panel_alt};
    border: 1px solid {p.border};
    border-radius: 6px;
    text-align: center;
    height: 16px;
}}
QProgressBar::chunk {{ background-color: {p.accent}; border-radius: 5px; }}

QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {p.border}; border-radius: 5px; min-height: 30px; }}
QScrollBar::handle:vertical:hover {{ background: {p.text_muted}; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {p.border}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line, QScrollBar::sub-line {{ height: 0; width: 0; }}

QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid {p.border};
    border-radius: 4px;
    background: {p.panel_alt};
}}
QCheckBox::indicator:checked {{ background: {p.accent}; border-color: {p.accent}; }}

QSplitter::handle {{ background: {p.border}; width: 1px; }}
QToolTip {{
    background-color: {p.panel_alt};
    color: {p.text};
    border: 1px solid {p.border};
    padding: 4px;
}}

QLabel#statValue {{ font-size: 21px; font-weight: 600; color: {p.text}; }}
QLabel#statLabel {{ font-size: 11px; color: {p.text_muted}; text-transform: uppercase; }}
QLabel#statHint {{ font-size: 11px; color: {p.text_muted}; }}
QLabel#title {{ font-size: 17px; font-weight: 600; }}
QLabel#subtitle {{ color: {p.text_muted}; }}
QFrame#card {{
    background-color: {p.panel};
    border: 1px solid {p.border};
    border-radius: 10px;
}}
"""


#: Palette active. Les noms en majuscules juste en dessous en decoulent.
PALETTE = DARK


def use(name: str) -> Palette:
    """Active un theme et republie ses couleurs au niveau du module."""
    global PALETTE, STYLESHEET
    global BG, PANEL, PANEL_ALT, BORDER, TEXT, TEXT_MUTED
    global DEPTH, DEPTH_FILL, TEMP, PPO2, ASCENT, DESCENT
    global WARN, GOOD, ACCENT, GRID, SAFETY, SERIES

    PALETTE = THEMES.get(name, DARK)
    BG = PALETTE.bg
    PANEL = PALETTE.panel
    PANEL_ALT = PALETTE.panel_alt
    BORDER = PALETTE.border
    TEXT = PALETTE.text
    TEXT_MUTED = PALETTE.text_muted
    DEPTH = PALETTE.depth
    DEPTH_FILL = PALETTE.depth_fill
    TEMP = PALETTE.temp
    PPO2 = PALETTE.ppo2
    ASCENT = PALETTE.ascent
    DESCENT = PALETTE.descent
    WARN = PALETTE.warn
    GOOD = PALETTE.good
    ACCENT = PALETTE.accent
    GRID = PALETTE.grid
    SAFETY = PALETTE.safety
    SERIES = PALETTE.series
    STYLESHEET = build_stylesheet(PALETTE)
    return PALETTE


def is_dark() -> bool:
    return PALETTE.name == "dark"


use(DARK.name)
