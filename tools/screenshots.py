"""Fabrique les captures d'ecran du README.

Tout part du **mode demonstration**: les plongees sont inventees par le
simulateur, aucune donnee personnelle ne peut se retrouver dans les images.

    python tools/screenshots.py              # docs/, en francais
    python tools/screenshots.py --lang en    # docs/en/
    python tools/screenshots.py --theme light

Le script ouvre vraiment la fenetre: il sert donc aussi de test de bout en
bout, puisqu'il echoue si un onglet ne se construit pas.
"""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thermocline import config, i18n  # noqa: E402
from thermocline.importer import import_dives  # noqa: E402
from thermocline.simulator import DEMO_SITES, SimulatedDevice  # noqa: E402
from thermocline.storage import Database  # noqa: E402

#: Onglets a capturer: index, nom de fichier.
TABS: tuple[tuple[int, str], ...] = (
    (0, "profil"),
    (1, "analyse"),
    (2, "oxygene"),
    (3, "details"),
    (4, "statistiques"),
    (5, "carnet"),
)

BUDDIES = ("Camille", "Jonas", "Maya", "Thomas", "Inès", "Léa", "Hugo", "Sofia")

NOTES = (
    "Belle visibilité, un mérou sur le tombant.",
    "Courant sur la fin, remontée le long du bout.",
    "Eau claire, sable blanc, plongée tranquille.",
    "Lac froid : combinaison étanche obligatoire.",
    "Nudibranches partout dans la faille.",
    "Descente rapide, palier confortable.",
    "Belle lumière l'après-midi dans la calanque.",
    "Première plongée du club, tout s'est bien passé.",
)


def populate(db: Database, model: str) -> None:
    """Remplit une base neuve avec le carnet de demonstration."""
    source = SimulatedDevice(model=model)
    import_dives(db, source)
    for index, summary in enumerate(db.list_dives(order="asc")):
        db.update_annotations(
            summary.uid,
            site=DEMO_SITES[index % len(DEMO_SITES)],
            buddy=BUDDIES[index % len(BUDDIES)],
            notes=NOTES[index % len(NOTES)],
            rating=3 + index % 3,
        )


def capture(args: argparse.Namespace) -> int:
    from PyQt6 import QtCore, QtWidgets

    from thermocline.ui import theme
    from thermocline.ui.main_window import MainWindow

    i18n.set_language(args.lang)
    theme.use(args.theme)

    settings = config.Settings()
    settings.language = args.lang
    settings.theme = args.theme
    settings.remember_geometry = False
    config.set_settings(settings)

    workspace = Path(tempfile.mkdtemp(prefix="thermocline-shots-"))
    database = Database(workspace / "demo.sqlite")
    populate(database, args.model)

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(theme.STYLESHEET)

    window = MainWindow(database, settings=settings)
    window.resize(args.width, args.height)
    window.show()

    def settle(rounds: int = 8) -> None:
        """Laisse Qt terminer la mise en page et le trace des courbes."""
        for _ in range(rounds):
            app.processEvents(QtCore.QEventLoop.ProcessEventsFlag.AllEvents, 120)

    settle(20)
    args.output.mkdir(parents=True, exist_ok=True)

    for index, name in TABS:
        window.tabs.setCurrentIndex(index)
        settle()
        target = args.output / f"{name}.png"
        if not window.grab().save(str(target)):
            print(f"Capture impossible : {target}", file=sys.stderr)
            return 1
        print(f"  {target.relative_to(ROOT) if target.is_relative_to(ROOT) else target}")

    # Une vue des parametres, puisque c'est la premiere chose qu'on cherche.
    from thermocline.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(settings, window)
    dialog.resize(760, 620)
    dialog.show()
    settle()
    for index, name in ((1, "parametres-ordinateur"), (2, "parametres-bloc")):
        dialog.tabs.setCurrentIndex(index)
        settle()
        dialog.grab().save(str(args.output / f"{name}.png"))
        print(f"  {name}.png")
    dialog.close()

    window.close()
    database.close()
    shutil.rmtree(workspace, ignore_errors=True)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lang", default="fr", choices=("fr", "en"))
    parser.add_argument("--theme", default="dark", choices=("dark", "light"))
    parser.add_argument("--model", default="Quad", help="modèle simulé")
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=960)
    parser.add_argument("--output", type=Path, default=ROOT / "docs")
    args = parser.parse_args()
    print(f"Captures {args.lang} / {args.theme} vers {args.output}")
    return capture(args)


if __name__ == "__main__":
    raise SystemExit(main())
