"""Taches longues executees hors du fil de l'interface.

Une connexion SQLite ne peut pas etre partagee entre fils d'execution: le
worker ouvre donc la sienne sur le meme fichier, et l'interface recharge
depuis sa propre connexion quand l'import est fini.
"""

from __future__ import annotations

import logging
import traceback
from pathlib import Path

from PyQt6 import QtCore

from ..config import Settings
from ..i18n import T
from ..importer import NoPortFoundError, import_from_port, open_source
from ..storage import Database, ImportResult

log = logging.getLogger(__name__)

TIMEOUT_ADVICE = (
    "L'ordinateur ne répond pas. Vérifiez que le clip USB est bien enfoncé sur "
    "les contacts et que l'ordinateur est réveillé (appuyez sur un bouton), "
    "puis relancez. Si cela se reproduit, augmentez le délai d'attente dans "
    "Paramètres › Ordinateur."
)


class ImportWorker(QtCore.QThread):
    """Importe les plongees en tache de fond."""

    progress = QtCore.pyqtSignal(str, int, object)
    succeeded = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str, str)

    def __init__(
        self,
        db_path: Path,
        port: str | None,
        *,
        demo: bool = False,
        demo_model: str = "Quad",
        limit: int | None = None,
        full: bool = False,
        settings: Settings | None = None,
        parent: QtCore.QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.db_path = db_path
        self.port = port
        self.demo = demo
        self.demo_model = demo_model
        self.limit = limit
        self.full = full
        self.settings = settings

    def run(self) -> None:  # noqa: D102 - execute dans le fil du worker
        database: Database | None = None
        try:
            database = Database(self.db_path)
            result: ImportResult = import_from_port(
                database,
                self.port,
                demo=self.demo,
                demo_model=self.demo_model,
                limit=self.limit,
                full=self.full,
                settings=self.settings,
                progress=lambda step, done, total: self.progress.emit(step, done, total),
            )
            self.succeeded.emit(result)
        except NoPortFoundError as exc:
            self.failed.emit(str(exc), "")
        except TimeoutError:
            self.failed.emit(T(TIMEOUT_ADVICE), traceback.format_exc())
        except Exception as exc:  # noqa: BLE001 - remonte tel quel a l'interface
            log.exception("Import en échec")
            self.failed.emit(f"{type(exc).__name__}: {exc}", traceback.format_exc())
        finally:
            if database is not None:
                database.close()


class ProbeWorker(QtCore.QThread):
    """Se connecte a l'ordinateur, dit ce qu'il est, puis raccroche.

    C'est le « Tester la connexion » des parametres: il repond a la seule
    question qui compte quand rien ne marche, a savoir si le cable, le pilote
    et le modele sont bons, sans toucher a la base.
    """

    succeeded = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(
        self, settings: Settings, parent: QtCore.QObject | None = None
    ) -> None:
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:  # noqa: D102 - execute dans le fil du worker
        source = None
        try:
            source = open_source(settings=self.settings)
            info = source.connect()
            self.succeeded.emit(info.label)
        except NoPortFoundError as exc:
            self.failed.emit(str(exc))
        except TimeoutError:
            self.failed.emit(T(TIMEOUT_ADVICE))
        except Exception as exc:  # noqa: BLE001 - remonte tel quel a l'interface
            log.exception("Test de connexion en échec")
            self.failed.emit(f"{type(exc).__name__}: {exc}")
        finally:
            if source is not None:
                try:
                    source.close()
                except Exception:  # noqa: BLE001 - fermeture au mieux
                    pass
