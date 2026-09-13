#!/usr/bin/env python3
"""Lanceur: ouvre directement l'interface graphique.

    python run.py              # interface
    python run.py --demo       # interface, import de donnees simulees
    python run.py --lang en    # interface en anglais, sans toucher aux reglages

C'est aussi le point d'entree de l'executable: ce qui est ecrit ici vaut pour
la version compilee.
"""

from __future__ import annotations

import argparse
import logging
import sys

from thermocline import __version__, config
from thermocline.app import run_gui


def attach_console() -> None:
    """Rebranche la sortie texte sur le terminal qui a lance l'application.

    L'executable Windows est compile en mode fenetre pour ne pas ouvrir de
    console noire au demarrage; l'effet de bord est que `--version`,
    `--help` et les messages d'erreur n'ont plus ou aller. S'il existe une
    console parente, on s'y raccroche: lance depuis un terminal, le programme
    parle; lance depuis l'Explorateur, il reste muet, comme attendu.
    """
    if not sys.platform.startswith("win") or sys.stdout is not None:
        return
    try:
        import ctypes

        attach_parent_process = -1  # ATTACH_PARENT_PROCESS, dans l'API Windows
        if not ctypes.windll.kernel32.AttachConsole(attach_parent_process):
            return
        sys.stdout = open("CONOUT$", "w", encoding="utf-8", errors="replace")
        sys.stderr = open("CONOUT$", "w", encoding="utf-8", errors="replace")
    except (ImportError, OSError, AttributeError):  # pragma: no cover
        pass


def main() -> int:
    attach_console()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", default=None, help="chemin de la base SQLite (défaut : celui des réglages)"
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="coche le mode démo au démarrage (aucun matériel requis)",
    )
    parser.add_argument(
        "--lang",
        choices=("auto", "fr", "en"),
        help="langue de cette session, sans modifier les réglages",
    )
    parser.add_argument(
        "--reset-settings",
        action="store_true",
        help="repart des réglages d'usine (la base de plongées n'est pas touchée)",
    )
    parser.add_argument("-v", "--verbose", action="count", default=0)
    parser.add_argument("--version", action="version", version=f"Thermocline {__version__}")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING - min(args.verbose, 2) * 10,
        format="%(levelname)-7s %(name)s: %(message)s",
    )

    settings = config.settings()
    if args.reset_settings:
        settings = config.set_settings(settings.reset())
        settings.save()
    if args.lang:
        settings.language = args.lang
    config.apply(settings)

    return run_gui(db_path=args.db, demo=args.demo, verbose=args.verbose)


if __name__ == "__main__":
    sys.exit(main())
