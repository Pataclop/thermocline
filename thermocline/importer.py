"""Orchestration de l'import: ordinateur -> decodage -> base SQLite."""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Protocol

from . import config
from .device import MaresDevice
from .models import DeviceInfo, Dive
from .i18n import T
from .parser import ParseError, parse_raw_dive
from .simulator import SimulatedDevice
from .storage import Database, ImportResult
from .transport import SerialTransport, autodetect_port, permission_hint

log = logging.getLogger(__name__)

ProgressFn = Callable[[str, int, int | None], None]
"""Rappel `(etape, nombre_traite, total_attendu)`."""


class DiveSource(Protocol):
    """Ce que l'import attend d'une source de plongees."""

    model_id: int
    model_name: str
    serial: str

    def connect(self) -> DeviceInfo: ...
    def close(self) -> None: ...
    def iter_raw_dives(
        self,
        fingerprint: bytes | None = ...,
        limit: int | None = ...,
        progress: Callable[[int, int | None], None] | None = ...,
    ): ...


class NoPortFound(RuntimeError):
    """Aucun port serie utilisable n'a ete trouve."""


def open_source(
    port: str | None = None,
    demo: bool = False,
    *,
    demo_model: str = "Quad",
    settings: config.Settings | None = None,
) -> DiveSource:
    """Renvoie la source de plongees: l'ordinateur reel ou le simulateur.

    Args:
        port: port serie impose; a defaut on prend celui des reglages, puis la
            detection automatique.
        demo: remplace l'ordinateur par le simulateur.
        demo_model: modele a imiter en mode demonstration.
        settings: preferences a appliquer (vitesse, delais, modele force).
    """
    if demo:
        log.info("Mode demonstration: ordinateur simule (%s).", demo_model)
        return SimulatedDevice(model=demo_model)

    preferences = settings or config.settings()
    target = port or preferences.port or autodetect_port()
    if not target:
        raise NoPortFound(
            T(
                "Aucun port série détecté. Branchez le câble USB Mares, vérifiez "
                "que le pilote du convertisseur est installé, puis réessayez."
            )
            + "\n\n"
            + permission_hint()
        )
    log.info("Ouverture de %s", target)
    return MaresDevice(
        SerialTransport.from_settings(target, preferences),
        retries=preferences.retries,
        retry_delay=preferences.retry_delay,
        force_model=preferences.force_model,
        packet_size=preferences.packet_size,
    )


def import_dives(
    db: Database,
    source: DiveSource,
    *,
    limit: int | None = None,
    full: bool = False,
    progress: ProgressFn | None = None,
) -> ImportResult:
    """Importe les plongees manquantes depuis `source`.

    Args:
        limit: nombre maximum de plongees a lire (None = jusqu'a l'arret).
        full: ignore l'empreinte connue et relit tout l'historique.
        progress: rappel d'avancement pour l'interface.
    """

    def notify(step: str, done: int, total: int | None) -> None:
        if progress:
            progress(step, done, total)

    notify(T("Connexion à l'ordinateur…"), 0, limit)
    info = source.connect()
    log.info("Connecte: %s", info.label)
    notify(T("Connecté : {device}").format(device=info.label), 0, limit)

    fingerprint = None if full else db.last_fingerprint(info.serial)
    if fingerprint:
        log.info("Arret prevu sur l'empreinte %s", fingerprint.hex())

    sites: dict[str, str] = getattr(source, "sites", {})
    known = db.known_fingerprints(info.serial)
    ignored = db.ignored_fingerprints(info.serial)
    if ignored:
        log.info("%d plongee(s) masquee(s) seront ignorees.", len(ignored))

    pending: list[tuple[Dive, str]] = []
    errors: list[str] = []
    read = 0
    skipped_hidden = 0
    for record in source.iter_raw_dives(fingerprint=fingerprint, limit=limit):
        read += 1
        notify(T("Lecture de la plongée {number}…").format(number=read), read, limit)
        try:
            dive = parse_raw_dive(record, info.model_id, info.serial, info.model_name)
        except ParseError as exc:
            log.warning("Plongee illisible ignoree: %s", exc)
            errors.append(f"Enregistrement {read}: {exc}")
            continue
        if dive.fingerprint in ignored:
            # Masquee par le plongeur: typiquement une plongee de l'ancien
            # proprietaire d'un ordinateur d'occasion.
            log.debug("Plongee %s masquee, ignoree.", dive.fingerprint)
            skipped_hidden += 1
            continue
        if dive.fingerprint in known:
            log.debug("Plongee %s deja en base.", dive.fingerprint)
            continue
        pending.append((dive, sites.get(dive.fingerprint, "")))

    notify(T("Enregistrement en base…"), read, limit)
    # Les plus anciennes d'abord, pour que la numerotation suive le temps.
    pending.sort(key=lambda item: item[0].datetime)
    result = db.import_dives(pending, device=info)
    result.errors.extend(errors)
    result.ignored = skipped_hidden
    notify(result.message, read, limit)
    return result


def import_from_port(
    db: Database,
    port: str | None = None,
    *,
    demo: bool = False,
    demo_model: str = "Quad",
    limit: int | None = None,
    full: bool = False,
    progress: ProgressFn | None = None,
    settings: config.Settings | None = None,
) -> ImportResult:
    """Ouvre la source, importe, puis referme proprement."""
    source = open_source(
        port=port, demo=demo, demo_model=demo_model, settings=settings
    )
    try:
        return import_dives(db, source, limit=limit, full=full, progress=progress)
    finally:
        source.close()
