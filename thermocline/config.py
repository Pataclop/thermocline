"""Preferences de l'utilisateur, conservees en JSON.

Tout ce que la boite « Paramètres » propose passe par ici. Le fichier vit a
cote de la base de plongees:

    Windows   C:\\Users\\<nom>\\.thermocline\\settings.json
    macOS     ~/.thermocline/settings.json
    Linux     ~/.thermocline/settings.json

Mode portable — si un fichier nomme `portable.txt` se trouve a cote de
l'executable (ou du depot), la base et les reglages sont ranges dans un
sous-dossier `donnees` au meme endroit. C'est ce qu'il faut pour emporter le
carnet sur une cle USB, ou sur un poste ou le dossier personnel n'est pas
accessible en ecriture.

Un reglage inconnu ou corrompu n'empeche jamais le demarrage: la valeur par
defaut reprend la main et l'incident part dans le journal.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import shutil
import sys
from dataclasses import dataclass, field, fields
from pathlib import Path

log = logging.getLogger(__name__)

APP_NAME = "thermocline"

#: Ancien nom du projet: une base laissee la est reprise au premier demarrage.
LEGACY_APP_NAMES = ("maresquad",)

SETTINGS_FILENAME = "settings.json"
DATABASE_FILENAME = "dives.sqlite"
PORTABLE_MARKER = "portable.txt"


def program_dir() -> Path:
    """Dossier de l'executable (ou du depot quand on lance les sources)."""
    if getattr(sys, "frozen", False):  # pragma: no cover - uniquement une fois gele
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def is_portable() -> bool:
    """Vrai si l'application doit ecrire a cote d'elle-meme."""
    if os.environ.get("THERMOCLINE_PORTABLE"):
        return True
    try:
        return (program_dir() / PORTABLE_MARKER).exists()
    except OSError:  # pragma: no cover - support en lecture seule
        return False


def app_dir() -> Path:
    """Dossier qui contient les reglages et la base, cree au besoin."""
    override = os.environ.get("THERMOCLINE_HOME")
    if override:
        path = Path(override).expanduser()
    elif is_portable():
        path = program_dir() / "donnees"
    else:
        path = Path.home() / f".{APP_NAME}"
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError as exc:  # pragma: no cover - dossier personnel verrouille
        log.warning("Dossier %s inutilisable (%s), repli sur le dossier courant.", path, exc)
        path = Path.cwd() / f".{APP_NAME}"
        path.mkdir(parents=True, exist_ok=True)
    return path


def legacy_dirs() -> list[Path]:
    """Anciens emplacements de donnees, pour reprendre un carnet existant."""
    return [Path.home() / f".{name}" for name in LEGACY_APP_NAMES]


def default_db_path() -> Path:
    """Chemin de la base, en recuperant celle de l'ancien nom si besoin."""
    target = app_dir() / DATABASE_FILENAME
    if target.exists():
        return target
    for old in legacy_dirs():
        candidate = old / DATABASE_FILENAME
        if candidate.exists():
            try:
                shutil.copy2(candidate, target)
                log.info("Carnet repris depuis %s", candidate)
                return target
            except OSError as exc:  # pragma: no cover - depend des droits
                log.warning("Reprise de %s impossible (%s).", candidate, exc)
                return candidate
    return target


def settings_path() -> Path:
    return app_dir() / SETTINGS_FILENAME


@dataclass
class Settings:
    """Toutes les preferences, avec les valeurs d'usine."""

    # -- interface
    language: str = "auto"
    """`auto`, `fr` ou `en`."""
    theme: str = "dark"
    """`dark` ou `light`."""
    font_size: int = 9
    start_tab: int = 0
    remember_geometry: bool = True
    geometry: str = ""
    """Geometrie de la fenetre, encodee en base64 par Qt."""
    confirm_hide: bool = True

    # -- connexion a l'ordinateur
    port: str = ""
    """Port serie force; vide = detection automatique."""
    remember_port: bool = True
    force_model: str = ""
    """Nom exact d'un modele Mares, pour court-circuiter la detection."""
    timeout: float = 3.0
    retries: int = 4
    retry_delay: float = 1.0
    packet_size: int = 0
    """0 = taille conseillee pour le modele detecte."""
    baudrate: int = 115200
    dtr: bool = False
    rts: bool = False
    open_delay: float = 0.1
    """Pause apres l'ouverture du port, avant la premiere commande (s)."""
    demo_model: str = "Quad"
    """Modele imite par le mode demonstration."""

    # -- bloc et consommation
    tank_volume: float = 12.0
    pressure_start: float = 195.0
    pressure_end: float = 52.0
    use_device_tank: bool = True
    """Utilise les pressions mesurees quand l'ordinateur en fournit."""

    # -- analyse
    gradient_factor: int = 100
    ascent_limit: float = 10.0
    ppo2_warn: float = 1.4
    ppo2_max: float = 1.6
    safety_stop_min: float = 2.5
    safety_stop_max: float = 6.5
    safety_stop_target: int = 180
    rate_window: int = 30

    # -- donnees
    db_path: str = ""
    """Vide = base par defaut dans le dossier de l'application."""
    export_dir: str = ""

    # -- champs non exposes dans la boite de dialogue
    last_port: str = ""

    # ------------------------------------------------------------------

    @property
    def database(self) -> Path:
        return Path(self.db_path).expanduser() if self.db_path else default_db_path()

    @property
    def exports(self) -> Path:
        return Path(self.export_dir).expanduser() if self.export_dir else Path.home()

    @property
    def gradient(self) -> float:
        """Facteur de gradient sous forme de fraction."""
        return max(min(self.gradient_factor, 100), 10) / 100.0

    def as_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)

    # -- persistance ----------------------------------------------------

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """Relit les reglages; toute valeur douteuse revient a sa valeur d'usine."""
        target = path or settings_path()
        if not target.exists():
            return cls()
        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("Réglages illisibles (%s), valeurs par défaut.", exc)
            return cls()
        if not isinstance(raw, dict):
            log.warning("Réglages au mauvais format, valeurs par défaut.")
            return cls()

        settings = cls()
        known = {f.name: f for f in fields(cls)}
        for key, value in raw.items():
            spec = known.get(key)
            if spec is None:
                log.debug("Réglage inconnu ignoré : %s", key)
                continue
            try:
                setattr(settings, key, _coerce(value, spec.type))
            except (TypeError, ValueError):
                log.warning("Réglage %s invalide (%r), valeur par défaut.", key, value)
        return settings

    def save(self, path: Path | None = None) -> Path:
        """Ecrit les reglages, par fichier temporaire pour ne rien perdre."""
        target = path or settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.as_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(target)
        log.debug("Réglages enregistrés dans %s", target)
        return target

    def reset(self) -> Settings:
        """Remet tout aux valeurs d'usine, sauf le chemin de la base."""
        fresh = Settings()
        fresh.db_path = self.db_path
        return fresh

    def copy(self) -> Settings:
        return dataclasses.replace(self)


def _coerce(value: object, annotation: object) -> object:
    """Convertit une valeur relue vers le type attendu par le champ."""
    text = str(annotation)
    if "bool" in text:
        return bool(value)
    if "int" in text:
        return int(value)
    if "float" in text:
        return float(value)
    return str(value)


# -- reglage courant, partage par toute l'application -----------------------

_settings: Settings | None = None


def settings() -> Settings:
    """Reglages courants, relus au premier appel."""
    global _settings
    if _settings is None:
        _settings = Settings.load()
    return _settings


def set_settings(new: Settings) -> Settings:
    """Remplace les reglages courants et les applique aux modules concernes."""
    global _settings
    _settings = new
    apply(new)
    return new


def apply(current: Settings | None = None) -> Settings:
    """Repercute les reglages sur les modules qui en dependent."""
    current = current or settings()

    from . import analytics
    from .i18n import set_language

    set_language(current.language)
    analytics.LIMITS = analytics.Thresholds(
        ascent_limit=current.ascent_limit,
        ppo2_warn=current.ppo2_warn,
        ppo2_max=current.ppo2_max,
        safety_stop_band=(current.safety_stop_min, current.safety_stop_max),
        safety_stop_target=current.safety_stop_target,
        rate_window=current.rate_window,
    )
    return current


@dataclass
class Diagnostic:
    """Ce qu'il faut savoir pour comprendre un poste qui ne marche pas."""

    lines: list[tuple[str, str]] = field(default_factory=list)

    def add(self, key: str, value: object) -> None:
        self.lines.append((key, str(value)))

    def as_text(self) -> str:
        width = max((len(key) for key, _ in self.lines), default=0)
        return "\n".join(f"{key.ljust(width)}  {value}" for key, value in self.lines)


def diagnostic() -> Diagnostic:
    """Rassemble versions, chemins et ports: la premiere chose a demander."""
    import platform

    from .i18n import T, language

    report = Diagnostic()
    report.add(T("Version"), _version())
    report.add(T("Python"), sys.version.split()[0])
    report.add(T("Système"), f"{platform.system()} {platform.release()} ({platform.machine()})")
    report.add(T("Exécutable gelé"), T("oui") if getattr(sys, "frozen", False) else T("non"))
    report.add(T("Mode portable"), T("oui") if is_portable() else T("non"))
    report.add(T("Langue"), language())
    report.add(T("Dossier de données"), app_dir())
    report.add(T("Base de plongées"), settings().database)
    report.add(T("Réglages"), settings_path())

    for name, module in (("PyQt6", "PyQt6.QtCore"), ("pyqtgraph", "pyqtgraph"),
                         ("numpy", "numpy"), ("pyserial", "serial")):
        report.add(name, _module_version(module))

    try:
        from .transport import list_serial_ports

        ports = list_serial_ports()
        report.add(T("Ports série"), len(ports))
        for port in ports:
            report.add(f"  {port.device}", port.description)
    except Exception as exc:  # noqa: BLE001 - le diagnostic ne doit jamais echouer
        report.add(T("Ports série"), f"{type(exc).__name__}: {exc}")
    return report


def _version() -> str:
    from . import __version__

    return __version__


def _module_version(dotted: str) -> str:
    import importlib

    try:
        module = importlib.import_module(dotted)
    except Exception as exc:  # noqa: BLE001 - absence signalee, pas fatale
        return f"absent ({type(exc).__name__})"
    for attribute in ("__version__", "VERSION", "PYQT_VERSION_STR"):
        value = getattr(module, attribute, None)
        if value:
            return str(value)
    return "installé"
