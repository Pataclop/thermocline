"""Ordinateur de plongee simule, au format binaire reel.

Sert a trois choses: faire tourner l'interface sans cable (mode demo),
verifier le decodeur par aller-retour encodage / decodage dans les tests, et
donner a voir les formats des modeles qu'on n'a pas sous la main.

Les trois familles sont fabriquees ici:

* `encode_dive()` produit un enregistrement des familles IconHD et Smart,
  avec le couple `[type][nb_echantillons]` au bon bout de l'entete;
* `encode_genius_dive()` produit une entete d'objet suivie d'un profil
  decoupe en enregistrements typees, CRC compris.
"""

from __future__ import annotations

import datetime as _dt
import math
import random
from collections.abc import Callable, Iterator

from .device import (
    MODELS,
    QUAD,
    SMART_FAMILY,
    Family,
    MemoryLayout,
    crc16_ccitt,
    dive_geometry,
)
from .models import DeviceInfo, DiveMode
from .parser import GENIUS_INTERVAL, LAYOUT_GENIUS, LAYOUT_ICONHD, SURFACE_TAIL

HEADER_SIZE = 0x5C
SAMPLE_SIZE = 8
FIELDS_SIZE = HEADER_SIZE - 4

#: Modeles que le mode demo sait imiter.
DEMO_MODELS: tuple[str, ...] = ("Quad", "Puck Pro", "Smart", "Quad Air", "Quad2", "Sirius")


def _put_u16(buffer: bytearray, offset: int, value: int) -> None:
    buffer[offset : offset + 2] = max(0, int(value)).to_bytes(2, "little")


def _put_s16(buffer: bytearray, offset: int, value: int) -> None:
    buffer[offset : offset + 2] = int(value).to_bytes(2, "little", signed=True)


def _put_u32(buffer: bytearray, offset: int, value: int) -> None:
    buffer[offset : offset + 4] = max(0, int(value)).to_bytes(4, "little")


# -- familles IconHD et Smart ----------------------------------------------


def encode_dive(
    when: _dt.datetime,
    profile: list[tuple[float, float]],
    *,
    interval: int = 5,
    mode: DiveMode = DiveMode.NITROX,
    gasmixes: tuple[int, ...] = (32,),
    atmospheric: float = 1.013,
    fresh_water: bool = False,
    model_id: int = QUAD,
) -> bytes:
    """Fabrique un enregistrement brut a partir d'un profil `(profondeur, temp)`.

    Args:
        when: date et heure de debut de plongee.
        profile: un couple `(profondeur_m, temperature_C)` par echantillon.
        interval: intervalle d'echantillonnage (1, 5, 10 ou 20 s).
        gasmixes: pourcentages d'oxygene des melanges actifs.
        model_id: modele vise, qui decide de la place du couple
            `[type][nb_echantillons]` dans l'entete.
    """
    interval_index = {1: 0, 5: 1, 10: 2, 20: 3}[interval]
    settings = interval_index << 10 | 0x0100  # unites metriques
    if fresh_water:
        settings |= 0x0010

    depths = [d for d, _ in profile]
    temps = [t for _, t in profile]

    samples = bytearray()
    for depth, temp in profile:
        samples += int(round(depth * 10)).to_bytes(2, "little")
        # Le quartet haut du second octet de temperature porte l'index du gaz.
        samples += (int(round(temp * 10)) & 0x0FFF).to_bytes(2, "little")
        samples += b"\x00\x00\x00\x00"  # octets non documentes

    layout = LAYOUT_ICONHD
    fields = bytearray(FIELDS_SIZE)
    _put_u16(fields, layout.maxdepth, round(max(depths) * 10))
    _put_u16(fields, layout.datetime + 0, when.hour)
    _put_u16(fields, layout.datetime + 2, when.minute)
    _put_u16(fields, layout.datetime + 4, when.day)
    _put_u16(fields, layout.datetime + 6, when.month - 1)
    _put_u16(fields, layout.datetime + 8, when.year - 1900)
    _put_u16(fields, layout.settings, settings)
    _put_u16(
        fields,
        layout.atmospheric,
        round(atmospheric * 1000 * layout.atmospheric_divisor),
    )
    # L'ordinateur moyenne sur la plongee, pas sur la queue de surface.
    dive_depths = depths[: max(len(depths) - SURFACE_TAIL // interval, 1)]
    _put_u16(
        fields,
        layout.avgdepth,
        round(sum(dive_depths) / len(dive_depths) * 10) if dive_depths else 0,
    )
    _put_s16(fields, layout.temperature_min, round(min(temps) * 10))
    _put_s16(fields, layout.temperature_max, round(max(temps) * 10))

    if mode is DiveMode.NITROX:
        for index in range(3):
            offset = layout.gasmixes + index * 4
            if index < len(gasmixes):
                fields[offset] = gasmixes[index]
                fields[offset + 1] = 0x00
            else:
                fields[offset + 1] = 0x80  # melange desactive

    marker = bytearray(4)
    if model_id in SMART_FAMILY:
        # Famille Smart: le nombre d'echantillons d'abord, puis le type, et le
        # couple est rejete a la fin de l'entete.
        _put_u16(marker, 0, len(profile))
        _put_u16(marker, 2, int(mode))
        header = fields + marker
    else:
        _put_u16(marker, 0, int(mode))
        _put_u16(marker, 2, len(profile))
        header = marker + fields

    length = 4 + len(samples) + len(header)
    return length.to_bytes(4, "little") + bytes(samples) + bytes(header)


# -- famille Genius ---------------------------------------------------------

GENIUS_HEADER_SIZE = 0xB8
DSTR_TYPE, DSTR_SIZE = 0x44535452, 58
DPRS_TYPE, DPRS_SIZE = 0x44505253, 34
AIRS_TYPE, AIRS_SIZE = 0x41495253, 16
DEND_TYPE, DEND_SIZE = 0x44454E44, 162


def _genius_record(record_type: int, size: int, fill: Callable[[bytearray], None]) -> bytes:
    """Assemble un enregistrement typé: entete, charge utile, CRC, entete."""
    record = bytearray(size)
    record[0:4] = record_type.to_bytes(4, "big")
    fill(record)
    crc = crc16_ccitt(bytes(record[4 : size - 6]))
    record[size - 6 : size - 4] = crc.to_bytes(2, "little")
    record[size - 4 : size] = record_type.to_bytes(4, "big")
    return bytes(record)


def encode_genius_dive(
    when: _dt.datetime,
    profile: list[tuple[float, float]],
    *,
    mode: int = 1,
    gasmixes: tuple[tuple[int, int], ...] = ((32, 0),),
    tank: tuple[float, float, float] = (0.0, 0.0, 0.0),
    atmospheric: float = 1.013,
    fresh_water: bool = False,
) -> bytes:
    """Fabrique une plongee au format objet de la famille Genius / Sirius.

    Args:
        mode: mode Genius (0 air, 1 nitrox, 3 trimix, 4 profondimetre...).
        gasmixes: couples `(oxygene, helium)` des melanges actifs.
        tank: `(volume_l, pression_depart_bar, pression_fin_bar)`; un volume
            nul signifie qu'aucun emetteur n'etait apparie.
    """
    depths = [d for d, _ in profile]
    temps = [t for _, t in profile]
    layout = LAYOUT_GENIUS

    settings = mode & 0x0F
    if not fresh_water:
        settings |= 1 << 5  # eau de mer

    header = bytearray(GENIUS_HEADER_SIZE)
    _put_u16(header, 0x00, 1)  # objet « entete de plongee »
    header[0x02] = 1  # version mineure
    header[0x03] = 0  # version majeure
    timestamp = (
        (when.hour & 0x1F)
        | ((when.minute & 0x3F) << 5)
        | ((when.day & 0x1F) << 11)
        | ((when.month & 0x0F) << 16)
        | ((when.year & 0x0FFF) << 20)
    )
    _put_u32(header, layout.datetime, timestamp)
    _put_u32(header, layout.settings, settings)
    header[0x10] = 0  # format de journal Genius (1 = Horizon)
    _put_u16(header, 0x20, len(profile))
    _put_u16(header, layout.maxdepth, round(max(depths) * 10))
    dive_depths = depths[: max(len(depths) - 3 * 60 // GENIUS_INTERVAL, 1)]
    _put_u16(
        header,
        layout.avgdepth,
        round(sum(dive_depths) / len(dive_depths) * 10) if dive_depths else 0,
    )
    _put_s16(header, layout.temperature_max, round(max(temps) * 10))
    _put_s16(header, layout.temperature_min, round(min(temps) * 10))
    header[0x34] = 1  # unites metriques
    _put_u16(header, layout.atmospheric, round(atmospheric * 1000))

    volume, begin, end = tank
    for index in range(5):
        offset = layout.gasmixes + index * 20
        if index < len(gasmixes):
            oxygen, helium = gasmixes[index]
            nitrogen = 100 - oxygen - helium
            params = (
                (oxygen & 0x7F)
                | ((nitrogen & 0x7F) << 7)
                | ((helium & 0x7F) << 14)
                | (2 << 21)  # melange en service
            )
            _put_u32(header, offset, params)
            if index == 0 and volume:
                _put_u16(header, offset + 4, round(begin * 100))
                _put_u16(header, offset + 6, round(end * 100))
                _put_u16(header, offset + 8, round(volume))
                _put_u16(header, offset + 10, 200)
        else:
            _put_u16(header, offset + 6, 36000)  # emplacement vide

    # Objet « profil », version 0.1, puis l'enregistrement de debut de plongee.
    body = bytearray((0x00, 0x00, 0x01, 0x00))
    body += _genius_record(DSTR_TYPE, DSTR_SIZE, lambda r: None)

    pressure = begin
    step = (begin - end) / max(len(profile), 1) if volume else 0.0
    for index, (depth, temp) in enumerate(profile):
        def fill(record: bytearray, depth=depth, temp=temp) -> None:
            _put_u16(record, 4, round(depth * 10))
            _put_u16(record, 8, round(temp * 10))

        body += _genius_record(DPRS_TYPE, DPRS_SIZE, fill)
        if volume and (index + 1) % 4 == 0:
            pressure = max(pressure - step * 4, 0.0)

            def fill_air(record: bytearray, value=pressure) -> None:
                _put_u16(record, 4, round(value * 100))

            body += _genius_record(AIRS_TYPE, AIRS_SIZE, fill_air)
    body += _genius_record(DEND_TYPE, DEND_SIZE, lambda r: None)
    return bytes(header) + bytes(body)


# -- fabrication d'un profil plausible --------------------------------------


def make_profile(
    max_depth: float,
    bottom_minutes: float,
    *,
    interval: int = 5,
    surface_temp: float = 24.0,
    bottom_temp: float = 16.0,
    safety_stop: bool = True,
    rng: random.Random | None = None,
) -> list[tuple[float, float]]:
    """Genere un profil plausible: descente, palier fond, remontee, surface."""
    rng = rng or random.Random(0)
    profile: list[tuple[float, float]] = []

    def temp_at(depth: float) -> float:
        ratio = min(depth / max(max_depth, 1.0), 1.0)
        return surface_temp + (bottom_temp - surface_temp) * ratio + rng.gauss(0, 0.08)

    def push(depth: float) -> None:
        depth = max(0.0, depth)
        profile.append((round(depth, 1), round(temp_at(depth), 1)))

    # Descente a environ 18 m/min.
    descent_s = max_depth / 18.0 * 60.0
    for step in range(int(descent_s / interval) + 1):
        push(max_depth * (step * interval) / max(descent_s, interval))

    # Temps au fond, avec une derive en dents de scie et une remontee douce.
    bottom_s = bottom_minutes * 60.0
    steps = max(int(bottom_s / interval), 1)
    for step in range(steps):
        progress = step / steps
        drift = max_depth * (1.0 - 0.35 * progress)
        push(drift + math.sin(step / 6.0) * max_depth * 0.04 + rng.gauss(0, 0.25))

    # Remontee a 9 m/min, avec palier de securite a 5 m.
    current = profile[-1][0]
    while current > 5.0:
        current -= 9.0 * interval / 60.0
        push(current)
    if safety_stop:
        for _ in range(int(180 / interval)):
            push(5.0 + rng.gauss(0, 0.2))
    while current > 0.4:
        current -= 6.0 * interval / 60.0
        push(current)

    # Les 3 minutes de surface que l'ordinateur enregistre avant de clore.
    for _ in range(int(SURFACE_TAIL / interval)):
        push(abs(rng.gauss(0, 0.1)))
    return profile


#: Scenarios utilises par le mode demo, du plus ancien au plus recent.
DEMO_SCENARIOS: tuple[dict[str, object], ...] = (
    {"label": "Tombant de la Gabinière", "depth": 38.0, "bottom": 18, "days": 96,
     "mode": DiveMode.NITROX, "gas": (32,), "temp": (23.0, 14.0)},
    {"label": "Épave du Donator", "depth": 47.0, "bottom": 14, "days": 95,
     "mode": DiveMode.NITROX, "gas": (28, 50), "temp": (22.0, 13.0)},
    {"label": "Sec du Sarranier", "depth": 26.0, "bottom": 32, "days": 71,
     "mode": DiveMode.AIR, "gas": (21,), "temp": (24.0, 18.0)},
    {"label": "Lac d'Annecy", "depth": 19.0, "bottom": 40, "days": 44,
     "mode": DiveMode.AIR, "gas": (21,), "temp": (18.0, 8.0), "fresh": True},
    {"label": "Les Moyades", "depth": 33.0, "bottom": 24, "days": 22,
     "mode": DiveMode.NITROX, "gas": (32,), "temp": (25.0, 15.0)},
    {"label": "Pointe Fauconnière", "depth": 41.0, "bottom": 17, "days": 9,
     "mode": DiveMode.NITROX, "gas": (32,), "temp": (24.0, 14.0)},
    {"label": "Calanque de Podestat", "depth": 29.0, "bottom": 35, "days": 2,
     "mode": DiveMode.NITROX, "gas": (32,), "temp": (26.0, 17.0)},
    {"label": "Baptême en carrière", "depth": 12.0, "bottom": 28, "days": 1,
     "mode": DiveMode.AIR, "gas": (21,), "temp": (19.0, 12.0), "fresh": True},
)


class SimulatedDevice:
    """Remplace `MaresDevice` en mode demo: meme interface, donnees inventees.

    Le modele imite se choisit a la construction, ce qui permet de voir a quoi
    ressemble le carnet avec un Quad, un Smart ou un Sirius sans posseder les
    trois.
    """

    def __init__(
        self, seed: int = 1234, count: int | None = None, model: str = "Quad"
    ) -> None:
        self.rng = random.Random(seed)
        spec = MODELS.get(model) or MODELS["Quad"]
        self.spec = spec
        self.model_id = spec.model_id
        self.model_name = spec.name
        self.serial = "9900001"
        self.memory_size = 0x100000
        self.packet_size = 256
        self.layout = MemoryLayout(0x100000, 0x00A000, 0x100000)
        self.version = b"SIMULATEUR"
        self.sites: dict[str, str] = {}
        self._records = self._build_records(count)

    @property
    def family(self) -> Family:
        return self.spec.family

    # -- interface identique a MaresDevice ---------------------------------

    def connect(self) -> DeviceInfo:
        return DeviceInfo(
            model_id=self.model_id,
            model_name=self.model_name,
            serial=self.serial,
            memory_size=self.memory_size,
            version_raw=self.version,
        )

    def close(self) -> None:
        return None

    def __enter__(self) -> SimulatedDevice:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def iter_raw_dives(
        self,
        fingerprint: bytes | None = None,
        limit: int | None = None,
        progress: Callable[[int, int | None], None] | None = None,
    ) -> Iterator[bytes]:
        count = 0
        for record in self._records:  # deja du plus recent au plus ancien
            if fingerprint and self._fingerprint_of(record).startswith(fingerprint):
                break
            count += 1
            yield record
            if progress:
                progress(count, limit)
            if limit is not None and count >= limit:
                break

    # -- fabrication des donnees -------------------------------------------

    def _fingerprint_of(self, record: bytes) -> bytes:
        if self.family is Family.GENIUS:
            return record[0x08:0x0C]
        geometry = dive_geometry(self.model_id, 0)
        start = len(record) - geometry.header_size + geometry.fingerprint_offset
        return record[start : start + 10]

    def _build_records(self, count: int | None) -> list[bytes]:
        today = _dt.datetime.now().replace(second=0, microsecond=0)
        scenarios = list(DEMO_SCENARIOS)
        if count is not None:
            scenarios = scenarios[-count:]

        records: list[bytes] = []
        for scenario in scenarios:
            surface_temp, bottom_temp = scenario["temp"]  # type: ignore[misc]
            when = today - _dt.timedelta(
                days=int(scenario["days"]),  # type: ignore[arg-type]
                hours=self.rng.randint(0, 6),
                minutes=self.rng.randrange(0, 60, 5),
            )
            interval = GENIUS_INTERVAL if self.family is Family.GENIUS else 5
            profile = make_profile(
                float(scenario["depth"]),  # type: ignore[arg-type]
                float(scenario["bottom"]),  # type: ignore[arg-type]
                interval=interval,
                surface_temp=float(surface_temp),
                bottom_temp=float(bottom_temp),
                rng=self.rng,
            )
            record = self._encode(scenario, when, profile, interval)
            self.sites[self._fingerprint_of(record).hex()] = str(scenario["label"])
            records.append(record)
        records.reverse()  # du plus recent au plus ancien, comme l'ordinateur
        return records

    def _encode(
        self,
        scenario: dict[str, object],
        when: _dt.datetime,
        profile: list[tuple[float, float]],
        interval: int,
    ) -> bytes:
        gases: tuple[int, ...] = scenario["gas"]  # type: ignore[assignment]
        fresh = bool(scenario.get("fresh"))
        if self.family is Family.GENIUS:
            # Les modeles recents mesurent la pression du bloc.
            used = min(140.0 + self.rng.random() * 30.0, 150.0)
            return encode_genius_dive(
                when,
                profile,
                mode=1 if gases[0] != 21 else 0,
                gasmixes=tuple((oxygen, 0) for oxygen in gases),
                tank=(12.0, 200.0, 200.0 - used),
                fresh_water=fresh,
            )
        return encode_dive(
            when,
            profile,
            interval=interval,
            mode=scenario["mode"],  # type: ignore[arg-type]
            gasmixes=gases,
            fresh_water=fresh,
            model_id=self.model_id,
        )


#: Noms de site associes aux plongees simulees, dans l'ordre chronologique.
DEMO_SITES: tuple[str, ...] = tuple(str(s["label"]) for s in DEMO_SCENARIOS)
