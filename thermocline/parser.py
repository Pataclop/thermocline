"""Decodage d'un enregistrement de plongee brut en objets `Dive`.

Trois formats coexistent chez Mares, decrits dans `device.py`.

**Familles IconHD et Smart** — l'enregistrement vient de la memoire flash:

    +0x0000             longueur totale de l'enregistrement (u32)
    +0x0004             echantillons
    +len-taille_entete  bloc d'entete

Sur IconHD le bloc d'entete commence par `[type][nb_echantillons]` et les
champs suivent 4 octets plus loin. Sur Smart ce couple est rejete a la fin du
bloc: les champs commencent des le premier octet.

**Famille Genius** — l'enregistrement est la concatenation de deux objets:
une entete de taille variable (0xB8 octets, plus 8 sur Horizon, plus 16 a
partir de la version 1 du format), puis un profil decoupe en enregistrements
typees (`DSTR`, `DPRS`, `AIRS`, `DEND`...) proteges par un CRC.

L'ordinateur continue d'enregistrer pendant les minutes de surface qui
cloturent la plongee: la duree reelle vaut donc `nsamples * intervalle` moins
ce temps de surface.
"""

from __future__ import annotations

import datetime as _dt
import logging
from dataclasses import dataclass

from .device import (
    GENIUS_FAMILY,
    ICONHDNET,
    QUADAIR,
    SMART,
    SMART_FAMILY,
    SMARTAIR,
    SMARTAPNEA,
    Family,
    crc16_ccitt,
    dive_geometry,
    family_of,
    probe_size,
    read_type_and_samples,
    record_size,
)
from .models import Dive, DiveMode, GasMix, Sample, Tank

log = logging.getLogger(__name__)

#: Intervalle d'echantillonnage selon les bits 10-11 des reglages.
SAMPLE_INTERVALS = (1, 5, 10, 20)

#: Duree de surface enregistree apres la remontee (s), familles flash.
SURFACE_TAIL = 3 * 60

#: Intervalle d'echantillonnage de la famille Genius (s).
GENIUS_INTERVAL = 5

MAX_GASMIXES_ICONHD = 3
MAX_GASMIXES_GENIUS = 5
MAX_TANKS_ICONHD = 3

#: Valeur des champs absents d'une disposition d'entete.
UNSUPPORTED = -1

#: Pression « bloc absent » renvoyee par les modeles a integration d'air.
NO_TANK_PRESSURE = 36000


class ParseError(ValueError):
    """Enregistrement incoherent ou tronque."""


@dataclass(frozen=True)
class HeaderLayout:
    """Position des champs dans le bloc d'entete d'une plongee.

    Les offsets sont relatifs au debut des champs, c'est-a-dire apres le
    couple `[type][nb_echantillons]` sur la famille IconHD.
    """

    settings: int
    datetime: int
    maxdepth: int
    atmospheric: int
    atmospheric_divisor: int
    temperature_min: int
    temperature_max: int
    divetime: int = UNSUPPORTED
    avgdepth: int = UNSUPPORTED
    gasmixes: int = UNSUPPORTED
    tanks: int = UNSUPPORTED


LAYOUT_ICONHD = HeaderLayout(
    settings=0x0C,
    datetime=0x02,
    maxdepth=0x00,
    avgdepth=0x26,
    atmospheric=0x22,
    atmospheric_divisor=8,
    temperature_min=0x42,
    temperature_max=0x44,
    gasmixes=0x10,
)

LAYOUT_ICONHDNET = HeaderLayout(
    settings=0x0C,
    datetime=0x02,
    maxdepth=0x00,
    avgdepth=0x26,
    atmospheric=0x22,
    atmospheric_divisor=8,
    temperature_min=0x42,
    temperature_max=0x44,
    gasmixes=0x10,
    tanks=0x58,
)

#: Utilisee par le Smart Air et par le Quad Air: memes champs, blocs ailleurs.
LAYOUT_SMARTAIR = HeaderLayout(
    settings=0x0C,
    datetime=0x02,
    maxdepth=0x00,
    avgdepth=0x26,
    atmospheric=0x22,
    atmospheric_divisor=8,
    temperature_min=0x42,
    temperature_max=0x44,
    gasmixes=0x10,
    tanks=0x5C,
)

LAYOUT_SMARTAPNEA = HeaderLayout(
    settings=0x1C,
    datetime=0x40,
    divetime=0x24,
    maxdepth=0x3A,
    atmospheric=0x38,
    atmospheric_divisor=1,
    temperature_min=0x3E,
    temperature_max=0x3C,
)

LAYOUT_SMART_FREEDIVE = HeaderLayout(
    settings=0x08,
    datetime=0x20,
    divetime=0x0C,
    maxdepth=0x1A,
    atmospheric=0x18,
    atmospheric_divisor=1,
    temperature_min=0x1C,
    temperature_max=0x1E,
)

LAYOUT_SMARTAIR_FREEDIVE = HeaderLayout(
    settings=0x08,
    datetime=0x22,
    divetime=0x0E,
    maxdepth=0x1C,
    atmospheric=0x1A,
    atmospheric_divisor=1,
    temperature_min=0x20,
    temperature_max=0x1E,
)

LAYOUT_GENIUS = HeaderLayout(
    settings=0x0C,
    datetime=0x08,
    maxdepth=0x22,
    avgdepth=0x24,
    atmospheric=0x3E,
    atmospheric_divisor=1,
    temperature_min=0x28,
    temperature_max=0x26,
    gasmixes=0x54,
    tanks=0x54,
)

#: L'Horizon glisse 8 octets de plus a l'offset 0x18.
LAYOUT_HORIZON = HeaderLayout(
    settings=0x0C,
    datetime=0x08,
    maxdepth=0x22 + 8,
    avgdepth=0x24 + 8,
    atmospheric=0x3E + 8,
    atmospheric_divisor=1,
    temperature_min=0x28 + 8,
    temperature_max=0x26 + 8,
    gasmixes=0x54 + 8,
    tanks=0x54 + 8,
)


def header_layout(model_id: int, mode: int) -> HeaderLayout:
    """Disposition de l'entete pour un modele et un mode donnes."""
    freedive = mode == DiveMode.FREEDIVE
    if model_id == ICONHDNET:
        return LAYOUT_ICONHDNET
    if model_id == QUADAIR:
        return LAYOUT_SMARTAIR
    if model_id == SMART:
        return LAYOUT_SMART_FREEDIVE if freedive else LAYOUT_ICONHD
    if model_id == SMARTAIR:
        return LAYOUT_SMARTAIR_FREEDIVE if freedive else LAYOUT_SMARTAIR
    if model_id == SMARTAPNEA:
        return LAYOUT_SMARTAPNEA
    return LAYOUT_ICONHD


# -- petits accesseurs binaires ---------------------------------------------


def _u16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _s16(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 2], "little", signed=True)


def _u32(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _u32be(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ParseError(message)


# -- point d'entree ---------------------------------------------------------


def parse_raw_dive(
    record: bytes,
    model_id: int,
    device_serial: str = "",
    device_model: str = "Mares",
) -> Dive:
    """Decode un enregistrement brut renvoye par `MaresDevice.iter_raw_dives`."""
    if family_of(model_id) is Family.GENIUS:
        return parse_genius_dive(record, model_id, device_serial, device_model)
    return parse_flash_dive(record, model_id, device_serial, device_model)


# -- familles IconHD et Smart -----------------------------------------------


def parse_flash_dive(
    record: bytes,
    model_id: int,
    device_serial: str = "",
    device_model: str = "Mares",
) -> Dive:
    """Decode un enregistrement lu en memoire flash."""
    _require(len(record) >= 4, "Enregistrement trop court.")

    length = _u32(record, 0)
    _require(
        length == len(record),
        f"Longueur annoncée {length} ≠ taille réelle {len(record)}.",
    )

    probe = probe_size(model_id)
    _require(length >= 4 + probe, "Enregistrement plus court que son entête.")

    dive_type, nsamples = read_type_and_samples(record[length - probe :], model_id)
    mode = _flash_mode(dive_type)

    geometry = dive_geometry(model_id, dive_type & 0x03)
    _require(
        length >= 4 + geometry.header_size, "Enregistrement plus court que son entête."
    )

    head_start = length - geometry.header_size
    header_block = record[head_start:]
    fields = record[head_start + geometry.fields_offset :]
    layout = header_layout(model_id, mode)

    settings = _u16(fields, layout.settings)
    interval, samplerate = _sample_rate(model_id, settings)

    expected = record_size(model_id, geometry, nsamples, header_block)
    if expected != length:
        log.warning(
            "Taille calculée (%d) différente de la taille annoncée (%d).",
            expected,
            length,
        )

    dive = Dive(
        datetime=_parse_datetime(fields, layout.datetime),
        mode=mode,
        max_depth=_u16(fields, layout.maxdepth) / 10.0,
        avg_depth=(
            _u16(fields, layout.avgdepth) / 10.0
            if layout.avgdepth != UNSUPPORTED
            else None
        ),
        duration=_flash_duration(fields, layout, nsamples, interval),
        sample_interval=max(int(interval), 1),
        temperature_min=_s16(fields, layout.temperature_min) / 10.0,
        temperature_max=_s16(fields, layout.temperature_max) / 10.0,
        atmospheric=_u16(fields, layout.atmospheric)
        / (1000.0 * layout.atmospheric_divisor),
        salinity=_flash_salinity(model_id, settings),
        units_metric=bool(settings & 0x0100),
        settings=settings,
        gasmixes=_parse_gasmixes(fields, layout, mode),
        tanks=_parse_tanks_iconhd(fields, layout),
        device_serial=device_serial,
        device_model=device_model,
        fingerprint=record[
            head_start
            + geometry.fingerprint_offset : head_start
            + geometry.fingerprint_offset
            + 10
        ].hex(),
        raw=record,
    )

    if model_id == SMARTAPNEA:
        dive.samples = _parse_apnea_samples(
            record, nsamples, geometry.sample_size, samplerate
        )
    elif mode is DiveMode.FREEDIVE:
        dive.samples = _parse_freedive_samples(record, nsamples, geometry.sample_size)
    else:
        dive.samples = _parse_samples(
            record,
            nsamples,
            geometry.sample_size,
            int(interval),
            len(dive.gasmixes),
            has_tanks=layout.tanks != UNSUPPORTED,
        )
    if dive.samples and (mode is DiveMode.FREEDIVE or model_id == SMARTAPNEA):
        dive.duration = dive.samples[-1].time
    return dive


def _flash_mode(dive_type: int) -> DiveMode:
    try:
        return DiveMode(dive_type & 0x03)
    except ValueError:  # pragma: no cover - 2 bits, toujours valide
        return DiveMode.AIR


def _sample_rate(model_id: int, settings: int) -> tuple[float, int]:
    """Renvoie `(intervalle_en_secondes, echantillons_par_seconde)`."""
    if model_id == SMARTAPNEA:
        samplerate = 1 << ((settings & 0x0600) >> 9)
        return 1.0 / samplerate, samplerate
    return float(SAMPLE_INTERVALS[(settings & 0x0C00) >> 10]), 1


def _flash_duration(
    fields: bytes, layout: HeaderLayout, nsamples: int, interval: float
) -> int:
    if layout.divetime != UNSUPPORTED:
        return _u16(fields, layout.divetime)
    return max(int(nsamples * interval) - SURFACE_TAIL, 0)


def _flash_salinity(model_id: int, settings: int) -> str:
    if model_id == SMARTAPNEA:
        # Le Smart Apnea stocke une densite: 0 = eau douce.
        return "fresh" if (settings & 0x003F) == 0 else "salt"
    return "fresh" if settings & 0x0010 else "salt"


def _parse_datetime(fields: bytes, offset: int) -> _dt.datetime:
    hour = _u16(fields, offset + 0)
    minute = _u16(fields, offset + 2)
    day = _u16(fields, offset + 4)
    month = _u16(fields, offset + 6) + 1
    year = _u16(fields, offset + 8) + 1900
    try:
        return _dt.datetime(year, month, day, hour, minute)
    except ValueError as exc:
        raise ParseError(
            f"Date invalide dans l'entête : {year:04d}-{month:02d}-{day:02d} "
            f"{hour:02d}:{minute:02d}"
        ) from exc


def _parse_gasmixes(
    fields: bytes, layout: HeaderLayout, mode: DiveMode
) -> list[GasMix]:
    if layout.gasmixes == UNSUPPORTED:
        return []
    if mode in (DiveMode.GAUGE, DiveMode.FREEDIVE):
        return []
    if mode is DiveMode.AIR:
        return [GasMix(oxygen=21, helium=0)]

    mixes: list[GasMix] = []
    for index in range(MAX_GASMIXES_ICONHD):
        offset = layout.gasmixes + index * 4
        if offset + 1 >= len(fields):
            break
        # Le bit 7 du second octet marque un melange desactive: les melanges
        # actifs sont toujours en tete de liste.
        if fields[offset + 1] & 0x80:
            break
        mixes.append(GasMix(oxygen=fields[offset], helium=0))
    return mixes or [GasMix(oxygen=21, helium=0)]


def _parse_tanks_iconhd(fields: bytes, layout: HeaderLayout) -> list[Tank]:
    """Blocs declares dans l'entete des modeles a integration d'air."""
    if layout.tanks == UNSUPPORTED:
        return []
    tanks: list[Tank] = []
    base = layout.tanks
    for index in range(MAX_TANKS_ICONHD):
        pressures = base + index * 4
        sizes = base + 0x0C + index * 8
        if sizes + 4 > len(fields):
            break
        begin = _u16(fields, pressures + 0)
        end = _u16(fields, pressures + 2)
        if begin == 0 and end in (0, NO_TANK_PRESSURE):
            break
        tanks.append(
            Tank(
                volume=float(_u16(fields, sizes + 0)),
                work_pressure=float(_u16(fields, sizes + 2)),
                begin_pressure=begin / 100.0,
                end_pressure=end / 100.0,
            )
        )
    return tanks


def _parse_samples(
    record: bytes,
    nsamples: int,
    sample_size: int,
    interval: int,
    ngasmixes: int,
    *,
    has_tanks: bool,
) -> list[Sample]:
    """Decode les echantillons reguliers (plongee bouteille)."""
    samples: list[Sample] = []
    offset = 4
    time = 0
    for index in range(nsamples):
        if offset + sample_size > len(record):
            log.warning("Profil tronqué après %d/%d échantillons.", index, nsamples)
            break
        chunk = record[offset : offset + sample_size]
        time += interval
        gasmix = (chunk[3] & 0xF0) >> 4
        samples.append(
            Sample(
                time=time,
                depth=_u16(chunk, 0) / 10.0,
                temperature=(_u16(chunk, 2) & 0x0FFF) / 10.0,
                gasmix=gasmix if gasmix < ngasmixes else None,
                raw=chunk,
            )
        )
        offset += sample_size

        # Les modeles avec integration d'air intercalent un bloc de pression
        # tous les 4 echantillons.
        if has_tanks and (index + 1) % 4 == 0:
            if offset + 8 <= len(record):
                pressure = _u16(record, offset) / 100.0
                if pressure:
                    samples[-1].pressure = pressure
            offset += 8
    return samples


def _parse_freedive_samples(
    record: bytes, nsamples: int, sample_size: int
) -> list[Sample]:
    """Decode les echantillons d'apnee: un bloc par descente."""
    samples: list[Sample] = []
    offset = 4
    time = 0
    for _ in range(nsamples):
        if offset + sample_size > len(record):
            break
        max_depth = _u16(record, offset + 0) / 10.0
        dive_time = _u16(record, offset + 2)
        surface_time = _u16(record, offset + 4)

        time += surface_time
        samples.append(Sample(time=time, depth=0.0, raw=record[offset : offset + 6]))
        time += dive_time
        samples.append(
            Sample(time=time, depth=max_depth, raw=record[offset : offset + 6])
        )
        offset += sample_size
    return samples


def _parse_apnea_samples(
    record: bytes, nsamples: int, sample_size: int, samplerate: int
) -> list[Sample]:
    """Decode le profil detaille du Smart Apnea.

    Chaque descente est decrite par un bloc de resume suivi du profil
    echantillonne, jusqu'a quatre fois par seconde. Le carnet travaille a la
    seconde: on ne garde que le point le plus profond de chaque seconde, ce
    qui preserve la profondeur maximale sans multiplier les points.
    """
    samples: list[Sample] = []
    offset = 4
    time = 0
    for _ in range(nsamples):
        if offset + sample_size > len(record):
            break
        dive_time = _u16(record, offset + 2)
        surface_time = _u16(record, offset + 4)

        time += surface_time
        samples.append(Sample(time=time, depth=0.0, raw=record[offset : offset + 6]))
        offset += sample_size

        deepest = 0.0
        count = dive_time * samplerate
        for index in range(count):
            if offset + 2 > len(record):
                break
            deepest = max(deepest, _u16(record, offset) / 10.0)
            offset += 2
            if (index + 1) % samplerate == 0:
                time += 1
                samples.append(Sample(time=time, depth=deepest))
                deepest = 0.0
    return samples


# -- famille Genius ---------------------------------------------------------

#: Types d'enregistrement du profil Genius et leur taille fixe.
GENIUS_RECORDS: dict[int, int] = {
    0x44535452: 58,  # DSTR: debut de plongee
    0x54495353: 138,  # TISS: etat des tissus
    0x44505253: 34,  # DPRS: echantillon
    0x53445054: 78,  # SDPT: echantillon recycleur
    0x41495253: 16,  # AIRS: pression du bloc
    0x44454E44: 162,  # DEND: fin de plongee
}
DPRS_TYPE = 0x44505253
SDPT_TYPE = 0x53445054
AIRS_TYPE = 0x41495253

#: Mode de plongee Genius -> mode du carnet.
GENIUS_MODES: dict[int, DiveMode] = {
    0: DiveMode.AIR,
    1: DiveMode.NITROX,
    2: DiveMode.NITROX,
    3: DiveMode.TRIMIX,
    4: DiveMode.GAUGE,
    5: DiveMode.FREEDIVE,
    6: DiveMode.SCR,
    7: DiveMode.AIR,
}

GASMIX_OFF = 0

WATER_TYPES = {0: "fresh", 1: "salt", 2: "salt"}


def genius_header_size(record: bytes) -> tuple[int, int, HeaderLayout]:
    """Renvoie `(taille_entete, octets_supplementaires, disposition)`."""
    _require(len(record) >= 20, "Entête Genius trop courte.")
    obj_type = _u16(record, 0)
    minor, major = record[2], record[3]
    _require(
        obj_type == 1 and (major, minor) <= (2, 0),
        f"Format d'entête Genius non géré (type {obj_type}, version {major}.{minor}).",
    )

    logformat = record[0x10]
    extra = 8 if logformat == 1 else 0
    layout = LAYOUT_HORIZON if logformat == 1 else LAYOUT_GENIUS
    # Les entetes de version 1 et au-dela portent 16 octets de plus a la fin.
    more = 16 if major >= 1 else 0
    return 0xB8 + extra + more, extra, layout


def parse_genius_dive(
    record: bytes,
    model_id: int,
    device_serial: str = "",
    device_model: str = "Mares",
) -> Dive:
    """Decode une plongee de la famille Genius / Sirius."""
    header_size, extra, layout = genius_header_size(record)
    _require(header_size <= len(record), "Entête Genius tronquée.")

    nsamples = _u16(record, 0x20 + extra)
    settings = _u32(record, layout.settings)
    mode = GENIUS_MODES.get(settings & 0x0F, DiveMode.AIR)
    surface_tail = _genius_surface_tail(record, header_size, settings)

    gasmixes, tanks = _parse_genius_gasmixes(record, layout)

    dive = Dive(
        datetime=_parse_genius_datetime(_u32(record, layout.datetime)),
        mode=mode,
        max_depth=_u16(record, layout.maxdepth) / 10.0,
        avg_depth=_u16(record, layout.avgdepth) / 10.0,
        duration=max(nsamples * GENIUS_INTERVAL - surface_tail, 0),
        sample_interval=GENIUS_INTERVAL,
        temperature_min=_s16(record, layout.temperature_min) / 10.0,
        temperature_max=_s16(record, layout.temperature_max) / 10.0,
        atmospheric=_u16(record, layout.atmospheric)
        / (1000.0 * layout.atmospheric_divisor),
        salinity=WATER_TYPES.get((settings >> 5) & 0x03, "salt"),
        units_metric=bool(record[0x34 + extra]),
        settings=settings & 0xFFFF,
        gasmixes=gasmixes,
        tanks=tanks,
        device_serial=device_serial,
        device_model=device_model,
        fingerprint=record[0x08:0x0C].hex(),
        raw=record,
    )
    dive.samples = _parse_genius_samples(record, header_size, len(gasmixes))
    if dive.samples and mode is DiveMode.FREEDIVE:
        dive.duration = dive.samples[-1].time
    return dive


def _genius_surface_tail(record: bytes, header_size: int, settings: int) -> int:
    """Temps de surface enregistre apres la remontee, en secondes.

    Fixe a 3 minutes sur les anciens micrologiciels, reglable a partir de la
    version 1 du format de profil.
    """
    minutes = 3
    if header_size + 4 <= len(record):
        profile_type = _u16(record, header_size)
        profile_minor, profile_major = record[header_size + 2], record[header_size + 3]
        if profile_type == 0 and (profile_major, profile_minor) >= (1, 0):
            minutes = (settings >> 13) & 0x3F
    return minutes * 60


def _parse_genius_datetime(timestamp: int) -> _dt.datetime:
    hour = timestamp & 0x1F
    minute = (timestamp >> 5) & 0x3F
    day = (timestamp >> 11) & 0x1F
    month = (timestamp >> 16) & 0x0F
    year = (timestamp >> 20) & 0x0FFF
    try:
        return _dt.datetime(year, month, day, hour, minute)
    except ValueError as exc:
        raise ParseError(
            f"Date invalide dans l'entête : {year:04d}-{month:02d}-{day:02d} "
            f"{hour:02d}:{minute:02d}"
        ) from exc


def _parse_genius_gasmixes(
    record: bytes, layout: HeaderLayout
) -> tuple[list[GasMix], list[Tank]]:
    """Lit les cinq emplacements de melange et de bloc de l'entete Genius."""
    mixes: list[GasMix] = []
    tanks: list[Tank] = []
    for index in range(MAX_GASMIXES_GENIUS):
        offset = layout.gasmixes + index * 20
        if offset + 12 > len(record):
            break
        params = _u32(record, offset + 0)
        begin = _u16(record, offset + 4)
        end = _u16(record, offset + 6)
        volume = _u16(record, offset + 8)
        work_pressure = _u16(record, offset + 10)

        oxygen = params & 0x7F
        nitrogen = (params >> 7) & 0x7F
        helium = (params >> 14) & 0x7F
        state = (params >> 21) & 0x03

        if oxygen + nitrogen + helium != 100:
            log.debug(
                "Mélange %d incohérent (O2 %d, N2 %d, He %d), ignoré.",
                index + 1,
                oxygen,
                nitrogen,
                helium,
            )
        # Les melanges actifs sont toujours en tete de liste.
        if state != GASMIX_OFF and len(mixes) == index:
            mixes.append(GasMix(oxygen=oxygen, helium=helium))

        measured = begin != 0 or end not in (0, NO_TANK_PRESSURE)
        if measured and len(tanks) == index:
            tanks.append(
                Tank(
                    volume=float(volume),
                    work_pressure=float(work_pressure),
                    begin_pressure=begin / 100.0,
                    end_pressure=end / 100.0,
                )
            )
    return mixes, tanks


def _parse_genius_samples(
    record: bytes, header_size: int, ngasmixes: int
) -> list[Sample]:
    """Parcourt le profil Genius, enregistrement typé par enregistrement typé."""
    offset = header_size
    if offset + 4 > len(record):
        return []

    profile_type = _u16(record, offset)
    profile_minor, profile_major = record[offset + 2], record[offset + 3]
    version = (profile_major, profile_minor)
    if profile_type > 1 or (profile_type == 0 and version > (2, 0)) or (
        profile_type == 1 and version > (0, 2)
    ):
        raise ParseError(
            f"Format de profil Genius non géré (type {profile_type}, "
            f"version {profile_major}.{profile_minor})."
        )
    offset += 4

    samples: list[Sample] = []
    marker = 4
    time = 0
    while offset + 10 <= len(record):
        rec_type = _u32be(record, offset)
        length = GENIUS_RECORDS.get(rec_type)
        if length is None:
            log.warning(
                "Type d'enregistrement Genius inconnu (0x%08X), arrêt du profil.",
                rec_type,
            )
            break
        if offset + length > len(record):
            log.warning("Profil Genius tronqué en fin d'enregistrement.")
            break
        if _u32be(record, offset + length - 4) != rec_type:
            raise ParseError(
                f"Fin d'enregistrement Genius incohérente (0x{rec_type:08X})."
            )
        stored = _u16(record, offset + length - 6)
        computed = crc16_ccitt(record[offset + 4 : offset + length - 6])
        if stored != computed:
            log.warning(
                "CRC invalide sur un enregistrement Genius (0x%04X ≠ 0x%04X).",
                stored,
                computed,
            )

        if rec_type in (DPRS_TYPE, SDPT_TYPE):
            base = offset + marker
            if rec_type == SDPT_TYPE:
                depth = _u16(record, base + 2)
                temperature = _u16(record, base + 6)
                misc = _u32(record, base + 0x18)
            else:
                depth = _u16(record, base + 0)
                temperature = _u16(record, base + 4)
                misc = _u32(record, base + 0x14)
            gasmix = (misc >> 6) & 0x0F
            time += GENIUS_INTERVAL
            samples.append(
                Sample(
                    time=time,
                    depth=depth / 10.0,
                    temperature=temperature / 10.0,
                    gasmix=gasmix if gasmix < ngasmixes else None,
                    raw=record[offset : offset + length],
                )
            )
        elif rec_type == AIRS_TYPE and samples:
            pressure = _u16(record, offset + marker) / 100.0
            if pressure:
                samples[-1].pressure = pressure

        offset += length
    return samples
