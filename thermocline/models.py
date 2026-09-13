"""Modeles de donnees partages entre le protocole, la base et l'interface."""

from __future__ import annotations

import datetime as _dt
import hashlib
from dataclasses import dataclass, field
from enum import IntEnum


class DiveMode(IntEnum):
    """Mode de plongee.

    Les quatre premieres valeurs sont celles codees sur 2 bits dans l'entete
    des familles IconHD et Smart. Les deux dernieres n'existent que sur la
    famille Genius, qui code son mode sur 4 bits.
    """

    AIR = 0
    GAUGE = 1
    NITROX = 2
    FREEDIVE = 3
    TRIMIX = 4
    SCR = 5

    @property
    def label(self) -> str:
        from .i18n import T

        return T(
            {
                DiveMode.AIR: "Air",
                DiveMode.GAUGE: "Profondimètre",
                DiveMode.NITROX: "Nitrox",
                DiveMode.FREEDIVE: "Apnée",
                DiveMode.TRIMIX: "Trimix",
                DiveMode.SCR: "Recycleur semi-fermé",
            }[self]
        )


@dataclass(frozen=True)
class GasMix:
    """Un melange respiratoire configure pour la plongee."""

    oxygen: int = 21
    helium: int = 0

    @property
    def nitrogen(self) -> int:
        return 100 - self.oxygen - self.helium

    @property
    def label(self) -> str:
        if self.helium:
            return f"Tx {self.oxygen}/{self.helium}"
        if self.oxygen == 21:
            return "Air"
        return f"EAN{self.oxygen}"

    @property
    def mod_1_4(self) -> float:
        """Profondeur max operationnelle a ppO2 = 1.4 bar."""
        return round((1.4 / (self.oxygen / 100.0) - 1.0) * 10.0, 1)

    @property
    def mod_1_6(self) -> float:
        return round((1.6 / (self.oxygen / 100.0) - 1.0) * 10.0, 1)


@dataclass(frozen=True)
class Tank:
    """Un bloc, tel que l'ordinateur l'a enregistre.

    Seuls les modeles a integration d'air (Icon AIR, Quad Air, Smart Air et
    toute la famille Genius) renseignent ces champs; ailleurs ils viennent des
    valeurs saisies par le plongeur ou des valeurs par defaut.
    """

    volume: float = 0.0
    """Volume en litres."""
    work_pressure: float = 0.0
    """Pression de service en bar."""
    begin_pressure: float = 0.0
    end_pressure: float = 0.0

    @property
    def is_measured(self) -> bool:
        return bool(self.begin_pressure or self.end_pressure)

    @property
    def used(self) -> float:
        """Pression consommee en bar."""
        return max(self.begin_pressure - self.end_pressure, 0.0)


@dataclass
class Sample:
    """Un point du profil de plongee."""

    time: int
    """Temps ecoule depuis le debut de la plongee, en secondes."""
    depth: float
    """Profondeur en metres."""
    temperature: float | None = None
    """Temperature en degres Celsius."""
    gasmix: int | None = None
    """Index du melange en cours dans `Dive.gasmixes`."""
    pressure: float | None = None
    """Pression de la bouteille en bar (modeles avec integration d'air)."""
    raw: bytes = b""
    """Octets bruts de l'echantillon, conserves pour analyse ulterieure."""


@dataclass
class Dive:
    """Une plongee complete: entete decodee + profil."""

    datetime: _dt.datetime
    mode: DiveMode
    max_depth: float
    avg_depth: float | None = None
    duration: int = 0
    """Duree de la plongee en secondes (hors palier de surface enregistre)."""
    sample_interval: int = 5
    temperature_min: float | None = None
    temperature_max: float | None = None
    atmospheric: float | None = None
    """Pression atmospherique en bar."""
    salinity: str = "salt"
    units_metric: bool = True
    gasmixes: list[GasMix] = field(default_factory=list)
    tanks: list[Tank] = field(default_factory=list)
    """Blocs lus dans l'entete, sur les modeles a integration d'air."""
    samples: list[Sample] = field(default_factory=list)
    settings: int = 0
    device_serial: str = ""
    device_model: str = "Mares"
    fingerprint: str = ""
    """Cle stable renvoyee par l'ordinateur (date/heure encodee), en hexa."""
    raw: bytes = b""
    number: int | None = None
    """Numero de plongee tel qu'affiche par l'ordinateur, si connu."""

    # -- identite -----------------------------------------------------------

    @property
    def uid(self) -> str:
        """Identifiant stable d'une plongee, independant de l'ordre d'import."""
        if self.fingerprint:
            base = f"{self.device_serial}:{self.fingerprint}"
        else:
            base = f"{self.device_serial}:{self.datetime.isoformat()}:{self.max_depth}"
        return hashlib.sha1(base.encode()).hexdigest()[:16]

    # -- raccourcis d'affichage --------------------------------------------

    @property
    def end_datetime(self) -> _dt.datetime:
        return self.datetime + _dt.timedelta(seconds=self.duration)

    @property
    def duration_label(self) -> str:
        m, s = divmod(max(self.duration, 0), 60)
        return f"{m}:{s:02d}"

    @property
    def gas_label(self) -> str:
        if not self.gasmixes:
            return "-"
        return " / ".join(g.label for g in self.gasmixes)

    @property
    def measured_tank(self) -> Tank | None:
        """Premier bloc effectivement mesure par l'ordinateur, s'il y en a un."""
        return next((tank for tank in self.tanks if tank.is_measured), None)


@dataclass
class DeviceInfo:
    """Ce que l'on apprend de l'ordinateur au moment de la connexion."""

    model_id: int
    model_name: str
    serial: str
    firmware: str = ""
    memory_size: int = 0
    version_raw: bytes = b""

    @property
    def label(self) -> str:
        txt = f"Mares {self.model_name}" if self.model_name else "Mares (inconnu)"
        if self.serial:
            txt += f" - s/n {self.serial}"
        return txt
