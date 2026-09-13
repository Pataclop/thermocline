"""Point d'entree de l'interface graphique."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from . import config
from .storage import Database

log = logging.getLogger(__name__)

APP_TITLE = "Thermocline"

#: Polices essayees dans l'ordre; la premiere presente gagne. Fixer la police
#: evite qu'un poste au theme exotique rende l'interface illisible.
FONT_CANDIDATES = (
    "Segoe UI",
    "SF Pro Text",
    "Helvetica Neue",
    "Inter",
    "Noto Sans",
    "DejaVu Sans",
    "Cantarell",
    "Liberation Sans",
)


def run_gui(
    db_path: Path | str | None = None, demo: bool = False, *, verbose: int = 0
) -> int:
    """Ouvre la fenetre principale et rend le code de sortie de Qt."""
    settings = config.apply(config.settings())

    try:
        from PyQt6 import QtGui, QtWidgets
    except ImportError as exc:  # pragma: no cover - depend de l'installation
        print(
            "PyQt6 est introuvable : l'interface graphique ne peut pas démarrer.\n"
            f"  {exc}\n\n"
            "Installez les dépendances avec :  pip install -r requirements.txt\n"
            "Sans interface, la ligne de commande reste utilisable :\n"
            "  python -m thermocline list",
            file=sys.stderr,
        )
        return 2

    from .ui import theme
    from .ui.main_window import MainWindow

    theme.use(settings.theme)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_TITLE)
    app.setApplicationDisplayName(APP_TITLE)
    app.setOrganizationName(APP_TITLE)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.STYLESHEET)
    _apply_font(QtGui, app, settings.font_size)
    _apply_icon(QtGui, app)

    database = Database(Path(db_path) if db_path else settings.database)
    window = MainWindow(database, demo=demo, settings=settings)
    window.show()
    return app.exec()


def _apply_font(QtGui, app, size: int) -> None:
    """Choisit une police lisible presente sur la machine."""
    try:
        families = set(QtGui.QFontDatabase.families())
    except Exception as exc:  # noqa: BLE001 - serveur de polices capricieux
        log.warning("Liste des polices indisponible (%s).", exc)
        return
    for family in FONT_CANDIDATES:
        if family in families:
            app.setFont(QtGui.QFont(family, size))
            return
    app.setFont(QtGui.QFont(app.font().family(), size))


def _apply_icon(QtGui, app) -> None:
    """Pose l'icone de l'application si elle est presente."""
    for name in ("thermocline.png", "thermocline.ico"):
        candidate = Path(__file__).resolve().parent / "resources" / name
        if candidate.exists():
            app.setWindowIcon(QtGui.QIcon(str(candidate)))
            return
