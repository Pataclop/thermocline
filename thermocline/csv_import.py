"""Import d'un carnet de plongees depuis un fichier CSV.

Le format nominal est celui produit par « Exporter le carnet » (voir
`ui.main_window.MainWindow.export_csv`), mais l'en-tete est reconnu de
maniere tolerante (accents, casse, quelques alias) pour accepter un fichier
retravaille dans un tableur.
"""

from __future__ import annotations

import csv
import datetime as _dt
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from .i18n import T
from .models import Dive, DiveMode, GasMix
from .storage import ImportResult

if TYPE_CHECKING:
    from .storage import Database

DEVICE_SERIAL = "csv-import"
"""Serial factice des plongees saisies via CSV, pour les distinguer d'un ordinateur reel."""

# Cle normalisee (minuscules, sans accents ni espaces) -> champ interne.
_COLUMN_ALIASES: dict[str, str] = {
    "date": "date",
    "heure": "time",
    "time": "time",
    "mode": "mode",
    "duree_s": "duration_s",
    "duree_sec": "duration_s",
    "duration_s": "duration_s",
    "duree": "duration_label",
    "duration": "duration_label",
    "prof_max_m": "max_depth",
    "profondeur_max": "max_depth",
    "profondeur_max_m": "max_depth",
    "profondeur": "max_depth",
    "max_depth": "max_depth",
    "prof_moy_m": "avg_depth",
    "profondeur_moy": "avg_depth",
    "avg_depth": "avg_depth",
    "temp_min_c": "temp_min",
    "temp_min": "temp_min",
    "temp_max_c": "temp_max",
    "temp_max": "temp_max",
    "melanges": "gas",
    "melange": "gas",
    "gaz": "gas",
    "gas": "gas",
    "eau": "salinity",
    "salinite": "salinity",
    "salinity": "salinity",
    "site": "site",
    "spot": "site",
    "binome": "buddy",
    "buddy": "buddy",
    "note": "rating",
    "notation": "rating",
    "rating": "rating",
    "bloc_l": "tank_volume",
    "bloc": "tank_volume",
    "tank_volume": "tank_volume",
    "pression_depart_bar": "pressure_start",
    "pression_depart": "pressure_start",
    "pressure_start": "pressure_start",
    "pression_fin_bar": "pressure_end",
    "pression_fin": "pressure_end",
    "pressure_end": "pressure_end",
    "commentaire": "notes",
    "commentaires": "notes",
    "notes": "notes",
    "remarque": "notes",
    "remarques": "notes",
}

_MODE_LABELS = {mode.label.lower(): mode for mode in DiveMode}

_GAS_RE = re.compile(r"^(?:ean|nx)\s*(\d{1,3})$", re.IGNORECASE)
_TX_RE = re.compile(r"^tx\s*(\d{1,3})\s*/\s*(\d{1,3})$", re.IGNORECASE)

_DATE_FORMATS = ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y")
_TIME_FORMATS = ("%H:%M:%S", "%H:%M", "%Hh%M")


class CsvFormatError(ValueError):
    """Fichier illisible ou sans colonne reconnaissable."""


@dataclass
class CsvDiveRow:
    """Une ligne de CSV interpretee, prete a etre importee ou rejetee."""

    line: int
    dive: Dive
    site: str = ""
    buddy: str = ""
    notes: str = ""
    rating: int | None = None
    tank_volume: float | None = None
    pressure_start: float | None = None
    pressure_end: float | None = None
    duplicate: bool = False

    @property
    def label(self) -> str:
        bits = [f"{self.dive.datetime:%d/%m/%Y %H:%M}", f"{self.dive.max_depth:.1f} m"]
        if self.dive.duration:
            minutes, seconds = divmod(self.dive.duration, 60)
            bits.append(f"{minutes}:{seconds:02d}")
        if self.site:
            bits.append(self.site)
        return " · ".join(bits)


@dataclass
class CsvParseResult:
    """Bilan de la lecture d'un fichier: lignes exploitables et rejets."""

    rows: list[CsvDiveRow] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _normalize_header(name: str) -> str:
    text = unicodedata.normalize("NFKD", name.strip().lower())
    text = "".join(char for char in text if not unicodedata.combining(char))
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _sniff_delimiter(sample: str) -> str:
    counts = {delim: sample.count(delim) for delim in (";", ",", "\t")}
    return max(counts, key=counts.get) if any(counts.values()) else ";"


def parse_csv_file(path: str | Path) -> CsvParseResult:
    """Lit un carnet CSV et interprete chaque ligne en `CsvDiveRow`.

    Leve `CsvFormatError` si le fichier est vide ou si aucune colonne de
    l'en-tete n'est reconnue ; les erreurs par ligne sont collectees dans
    `CsvParseResult.errors` sans interrompre la lecture.
    """
    raw = Path(path).read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    if not lines:
        raise CsvFormatError(T("Le fichier est vide."))

    delimiter = _sniff_delimiter(lines[0])
    reader = csv.reader(lines, delimiter=delimiter)
    table = [row for row in reader if row]
    if not table:
        raise CsvFormatError(T("Le fichier est vide."))

    fields = [_COLUMN_ALIASES.get(_normalize_header(cell)) for cell in table[0]]
    if not any(fields):
        raise CsvFormatError(
            T("Aucune colonne reconnue dans l'en-tête. Colonnes attendues : "
            "date, prof_max_m, duree_s, site… (voir « Exporter le carnet »).")
        )

    result = CsvParseResult()
    for line_no, raw_row in enumerate(table[1:], start=2):
        values = {
            name: raw_row[i].strip()
            for i, name in enumerate(fields)
            if name and i < len(raw_row) and raw_row[i].strip()
        }
        if not values:
            continue
        try:
            result.rows.append(_row_from_values(line_no, values))
        except ValueError as exc:
            result.errors.append(T("Ligne {line_no} : {exc}").format(line_no=line_no, exc=exc))
    return result


def _row_from_values(line_no: int, values: dict[str, str]) -> CsvDiveRow:
    moment = _parse_datetime(values)
    if moment is None:
        raise ValueError(T("date illisible ou manquante"))
    max_depth = _parse_float(values.get("max_depth"))
    if max_depth is None:
        raise ValueError(T("profondeur maximale illisible ou manquante"))

    gasmixes = _parse_gasmixes(values.get("gas"))
    site = values.get("site", "")
    fingerprint = hashlib.sha1(
        f"{moment.isoformat()}:{max_depth}:{site}".encode()
    ).hexdigest()[:20]

    dive = Dive(
        datetime=moment,
        mode=_parse_mode(values.get("mode"), gasmixes),
        max_depth=max_depth,
        avg_depth=_parse_float(values.get("avg_depth")),
        duration=_parse_duration(values),
        temperature_min=_parse_float(values.get("temp_min")),
        temperature_max=_parse_float(values.get("temp_max")),
        salinity=_parse_salinity(values.get("salinity")),
        gasmixes=gasmixes,
        device_serial=DEVICE_SERIAL,
        device_model="Carnet CSV",
        fingerprint=fingerprint,
    )
    return CsvDiveRow(
        line=line_no,
        dive=dive,
        site=site,
        buddy=values.get("buddy", ""),
        notes=values.get("notes", ""),
        rating=_clamp_rating(_parse_int(values.get("rating"))),
        tank_volume=_parse_float(values.get("tank_volume")),
        pressure_start=_parse_float(values.get("pressure_start")),
        pressure_end=_parse_float(values.get("pressure_end")),
    )


def _parse_float(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text.replace(",", "."))
    except ValueError:
        return None


def _parse_int(text: str | None) -> int | None:
    value = _parse_float(text)
    return int(value) if value is not None else None


def _clamp_rating(rating: int | None) -> int | None:
    return None if rating is None else max(0, min(5, rating))


def _parse_duration(values: dict[str, str]) -> int:
    seconds = _parse_float(values.get("duration_s"))
    if seconds is not None:
        return int(seconds)
    label = values.get("duration_label")
    if not label:
        return 0
    try:
        parts = [int(part) for part in label.split(":")]
    except ValueError:
        return 0
    while len(parts) < 3:
        parts.insert(0, 0)
    hours, minutes, secs = parts[-3:]
    return hours * 3600 + minutes * 60 + secs


def _parse_datetime(values: dict[str, str]) -> _dt.datetime | None:
    date_text = values.get("date")
    if not date_text:
        return None
    date_value: _dt.date | None = None
    for fmt in _DATE_FORMATS:
        try:
            date_value = _dt.datetime.strptime(date_text, fmt).date()
            break
        except ValueError:
            continue
    if date_value is None:
        return None

    time_value = _dt.time(0, 0)
    time_text = values.get("time")
    if time_text:
        for fmt in _TIME_FORMATS:
            try:
                time_value = _dt.datetime.strptime(time_text, fmt).time()
                break
            except ValueError:
                continue
    return _dt.datetime.combine(date_value, time_value)


def _parse_salinity(text: str | None) -> str:
    if text and text.strip().lower().startswith(("douce", "fresh", "lac")):
        return "fresh"
    return "salt"


def _parse_one_gasmix(text: str) -> GasMix | None:
    text = text.strip()
    if not text or text == "-":
        return None
    if text.lower() == "air":
        return GasMix()
    match = _TX_RE.match(text)
    if match:
        return GasMix(oxygen=int(match.group(1)), helium=int(match.group(2)))
    match = _GAS_RE.match(text)
    if match:
        return GasMix(oxygen=int(match.group(1)))
    return None


def _parse_gasmixes(text: str | None) -> list[GasMix]:
    if not text:
        return []
    return [
        mix
        for chunk in text.split(" / ")
        if (mix := _parse_one_gasmix(chunk)) is not None
    ]


def _parse_mode(text: str | None, gasmixes: list[GasMix]) -> DiveMode:
    if text:
        mode = _MODE_LABELS.get(text.strip().lower())
        if mode is not None:
            return mode
    if any(mix.helium or mix.oxygen != 21 for mix in gasmixes):
        return DiveMode.NITROX
    return DiveMode.AIR


def annotate_known(db: Database, result: CsvParseResult) -> None:
    """Marque les lignes deja presentes en base (ou masquees) comme doublons."""
    known = db.known_fingerprints(DEVICE_SERIAL)
    ignored = db.ignored_fingerprints(DEVICE_SERIAL)
    for row in result.rows:
        row.duplicate = row.dive.fingerprint in known or row.dive.fingerprint in ignored


def import_rows(db: Database, rows: list[CsvDiveRow]) -> ImportResult:
    """Insere les lignes choisies et reporte les champs saisis (binome, notes…)."""
    pending = [(row.dive, row.site) for row in rows]
    result = db.import_dives(pending)
    rows_by_uid = {row.dive.uid: row for row in rows}
    for summary in result.added:
        row = rows_by_uid.get(summary.uid)
        if row is None:
            continue
        if any(
            value is not None
            for value in (
                row.buddy or None,
                row.notes or None,
                row.rating,
                row.tank_volume,
                row.pressure_start,
                row.pressure_end,
            )
        ):
            db.update_annotations(
                summary.uid,
                buddy=row.buddy or None,
                notes=row.notes or None,
                rating=row.rating,
                tank_volume=row.tank_volume,
                pressure_start=row.pressure_start,
                pressure_end=row.pressure_end,
            )
    return result
