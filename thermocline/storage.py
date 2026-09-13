"""Persistance des plongees en SQLite.

Une plongee est identifiee par son empreinte materielle (date/heure encodee
dans l'entete) couplee au numero de serie de l'ordinateur: reimporter la meme
plongee ne cree donc jamais de doublon. Les octets bruts sont conserves, ce
qui permet de rejouer le decodage apres correction du parseur.

Masquer une plongee l'inscrit dans la table `ignored`: elle est retiree du
carnet et l'import ne la reprendra plus, meme lors d'une relecture complete.
C'est ce qu'il faut pour un ordinateur d'occasion, dont la memoire contient
les plongees de l'ancien proprietaire.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sqlite3
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import config
from .i18n import T, count_label
from .models import DeviceInfo, Dive, DiveMode, GasMix, Sample

log = logging.getLogger(__name__)

SCHEMA_VERSION = 3

#: Emplacement de la base: dossier de l'application, ou celui de l'ancienne
#: version si un carnet y dort encore.
DEFAULT_DB_PATH = config.default_db_path()

#: Bloc et pressions supposes tant que le plongeur n'a rien saisi et que
#: l'ordinateur ne mesure rien. Ils permettent d'afficher une consommation des
#: le premier import; la fiche signale qu'il s'agit d'une hypothese. Les
#: parametres permettent de les remplacer par celles de son propre bloc.
DEFAULT_TANK_VOLUME = 12.0
DEFAULT_PRESSURE_START = 195.0
DEFAULT_PRESSURE_END = 52.0


class TankSource(str, Enum):
    """D'ou viennent le bloc et les pressions d'une plongee."""

    DEFAULT = "default"
    """Valeurs par defaut: l'ordinateur ne mesure rien, rien n'a ete saisi."""
    DEVICE = "device"
    """Pressions mesurees par un ordinateur a integration d'air."""
    USER = "user"
    """Valeurs saisies par le plongeur, qui priment sur tout le reste."""

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    serial      TEXT PRIMARY KEY,
    model       TEXT NOT NULL,
    memory_size INTEGER DEFAULT 0,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dives (
    uid             TEXT PRIMARY KEY,
    device_serial   TEXT NOT NULL,
    fingerprint     TEXT NOT NULL,
    started_at      TEXT NOT NULL,
    mode            INTEGER NOT NULL,
    duration        INTEGER NOT NULL,
    max_depth       REAL NOT NULL,
    avg_depth       REAL,
    temp_min        REAL,
    temp_max        REAL,
    atmospheric     REAL,
    salinity        TEXT,
    units_metric    INTEGER DEFAULT 1,
    sample_interval INTEGER DEFAULT 5,
    settings        INTEGER DEFAULT 0,
    gasmixes        TEXT DEFAULT '[]',
    site            TEXT DEFAULT '',
    buddy           TEXT DEFAULT '',
    notes           TEXT DEFAULT '',
    rating          INTEGER DEFAULT 0,
    tank_volume     REAL DEFAULT {DEFAULT_TANK_VOLUME},
    pressure_start  REAL DEFAULT {DEFAULT_PRESSURE_START},
    pressure_end    REAL DEFAULT {DEFAULT_PRESSURE_END},
    tank_edited     INTEGER DEFAULT 0,
    tank_source     TEXT DEFAULT 'default',
    imported_at     TEXT NOT NULL,
    raw             BLOB,
    UNIQUE (device_serial, fingerprint)
);

CREATE INDEX IF NOT EXISTS idx_dives_started ON dives (started_at DESC);

CREATE TABLE IF NOT EXISTS samples (
    dive_uid    TEXT NOT NULL REFERENCES dives (uid) ON DELETE CASCADE,
    time        INTEGER NOT NULL,
    depth       REAL NOT NULL,
    temperature REAL,
    gasmix      INTEGER,
    pressure    REAL,
    PRIMARY KEY (dive_uid, time)
) WITHOUT ROWID;

CREATE TABLE IF NOT EXISTS ignored (
    device_serial TEXT NOT NULL,
    fingerprint   TEXT NOT NULL,
    started_at    TEXT,
    max_depth     REAL,
    duration      INTEGER,
    site          TEXT DEFAULT '',
    hidden_at     TEXT NOT NULL,
    PRIMARY KEY (device_serial, fingerprint)
);

CREATE TABLE IF NOT EXISTS imports (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    at            TEXT NOT NULL,
    device_serial TEXT,
    added         INTEGER DEFAULT 0,
    skipped       INTEGER DEFAULT 0,
    message       TEXT DEFAULT ''
);
"""

#: Colonnes ajoutees apres coup, avec leur definition pour les bases anciennes.
MIGRATIONS: tuple[tuple[str, str], ...] = (
    ("tank_volume", f"REAL DEFAULT {DEFAULT_TANK_VOLUME}"),
    ("pressure_start", f"REAL DEFAULT {DEFAULT_PRESSURE_START}"),
    ("pressure_end", f"REAL DEFAULT {DEFAULT_PRESSURE_END}"),
    ("tank_edited", "INTEGER DEFAULT 0"),
    ("tank_source", "TEXT DEFAULT 'default'"),
)


@dataclass
class DiveSummary:
    """Ligne de resume, sans le profil: ce qu'affiche la liste des plongees."""

    uid: str
    number: int
    started_at: _dt.datetime
    mode: DiveMode
    duration: int
    max_depth: float
    avg_depth: float | None
    temp_min: float | None
    temp_max: float | None
    gasmixes: list[GasMix]
    site: str = ""
    buddy: str = ""
    notes: str = ""
    rating: int = 0
    tank_volume: float = DEFAULT_TANK_VOLUME
    pressure_start: float = DEFAULT_PRESSURE_START
    pressure_end: float = DEFAULT_PRESSURE_END
    tank_edited: bool = False
    """Vrai si le plongeur a saisi lui-meme le bloc et les pressions."""
    tank_source: str = TankSource.DEFAULT.value
    """`default`, `device` ou `user`: d'ou viennent le bloc et les pressions."""
    device_serial: str = ""
    fingerprint: str = ""
    salinity: str = "salt"

    @property
    def duration_label(self) -> str:
        m, s = divmod(max(self.duration, 0), 60)
        return f"{m}:{s:02d}"

    @property
    def gas_label(self) -> str:
        return " / ".join(g.label for g in self.gasmixes) if self.gasmixes else "-"

    @property
    def label(self) -> str:
        """Libelle court, pour les messages et la liste des plongees masquees."""
        place = f" · {self.site}" if self.site else ""
        return (
            f"{self.started_at:%d/%m/%Y %H:%M} · {self.max_depth:.1f} m · "
            f"{self.duration_label}{place}"
        )


@dataclass
class HiddenDive:
    """Une plongee masquee, que l'import doit continuer d'ignorer."""

    device_serial: str
    fingerprint: str
    started_at: _dt.datetime | None
    max_depth: float | None
    duration: int | None
    site: str
    hidden_at: _dt.datetime | None

    @property
    def label(self) -> str:
        if self.started_at is None:
            return f"empreinte {self.fingerprint}"
        bits = [f"{self.started_at:%d/%m/%Y %H:%M}"]
        if self.max_depth:
            bits.append(f"{self.max_depth:.1f} m")
        if self.duration:
            minutes, seconds = divmod(self.duration, 60)
            bits.append(f"{minutes}:{seconds:02d}")
        if self.site:
            bits.append(self.site)
        return " · ".join(bits)


@dataclass
class ImportResult:
    """Bilan d'un import."""

    added: list[DiveSummary] = field(default_factory=list)
    skipped: int = 0
    ignored: int = 0
    errors: list[str] = field(default_factory=list)
    device: DeviceInfo | None = None

    @property
    def count(self) -> int:
        return len(self.added)

    @property
    def message(self) -> str:
        if self.count == 0 and not self.errors and not self.ignored:
            return T("Aucune nouvelle plongée : la base est à jour.")
        parts = []
        if self.count:
            parts.append(
                count_label(
                    self.count, "{count} plongée importée", "{count} plongées importées"
                )
            )
        if self.skipped:
            parts.append(
                count_label(
                    self.skipped, "{count} déjà connue", "{count} déjà connues"
                )
            )
        if self.ignored:
            parts.append(
                count_label(
                    self.ignored,
                    "{count} masquée ignorée",
                    "{count} masquées ignorées",
                )
            )
        if self.errors:
            parts.append(
                count_label(
                    len(self.errors), "{count} en erreur", "{count} en erreur"
                )
            )
        return ", ".join(parts) + "." if parts else T("Rien à importer.")


class Database:
    """Acces SQLite aux plongees."""

    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.path = Path(path)
        if self.path.parent and str(self.path.parent) not in ("", "."):
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, detect_types=0)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA journal_mode = WAL")
        self._migrate()

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> Database:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    def _migrate(self) -> None:
        self.conn.executescript(SCHEMA)
        # Bases creees par une version anterieure: on ajoute les colonnes
        # manquantes plutot que de refuser de les ouvrir.
        existing = {
            row["name"] for row in self.conn.execute("PRAGMA table_info(dives)")
        }
        for column, definition in MIGRATIONS:
            if column not in existing:
                log.info("Migration: ajout de la colonne dives.%s", column)
                self.conn.execute(f"ALTER TABLE dives ADD COLUMN {column} {definition}")
        # Les plongees importees avant l'introduction des valeurs par defaut
        # avaient un bloc a zero, ce qui empechait tout calcul de consommation.
        self.conn.execute(
            """
            UPDATE dives
            SET tank_volume = ?, pressure_start = ?, pressure_end = ?
            WHERE COALESCE(tank_edited, 0) = 0 AND COALESCE(tank_volume, 0) = 0
            """,
            (DEFAULT_TANK_VOLUME, DEFAULT_PRESSURE_START, DEFAULT_PRESSURE_END),
        )
        # Bases anterieures a la colonne `tank_source`: un bloc saisi par le
        # plongeur reste un bloc saisi par le plongeur.
        self.conn.execute(
            """
            UPDATE dives SET tank_source = ?
            WHERE COALESCE(tank_edited, 0) = 1 AND COALESCE(tank_source, '') <> ?
            """,
            (TankSource.USER.value, TankSource.USER.value),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO meta (key, value) VALUES ('schema_version', ?)",
            (str(SCHEMA_VERSION),),
        )
        self.conn.commit()

    # -- ecriture -----------------------------------------------------------

    def upsert_device(self, info: DeviceInfo) -> None:
        now = _dt.datetime.now().isoformat(timespec="seconds")
        self.conn.execute(
            """
            INSERT INTO devices (serial, model, memory_size, first_seen, last_seen)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (serial) DO UPDATE SET
                model = excluded.model,
                memory_size = excluded.memory_size,
                last_seen = excluded.last_seen
            """,
            (info.serial, info.model_name, info.memory_size, now, now),
        )
        self.conn.commit()

    def tank_defaults(self, dive: Dive) -> tuple[float, float, float, str]:
        """Bloc et pressions a inscrire pour une plongee qui arrive.

        Les pressions mesurees par un ordinateur a integration d'air ont la
        priorite; a defaut on reprend le bloc declare dans les parametres.
        """
        preferences = config.settings()
        tank = dive.measured_tank if preferences.use_device_tank else None
        if tank is not None:
            volume = tank.volume or preferences.tank_volume
            return (
                volume,
                tank.begin_pressure,
                tank.end_pressure,
                TankSource.DEVICE.value,
            )
        return (
            preferences.tank_volume,
            preferences.pressure_start,
            preferences.pressure_end,
            TankSource.DEFAULT.value,
        )

    def add_dive(self, dive: Dive, site: str = "") -> bool:
        """Insere une plongee. Renvoie False si elle etait deja en base."""
        if self.has_dive(dive.device_serial, dive.fingerprint):
            return False

        now = _dt.datetime.now().isoformat(timespec="seconds")
        gasmixes = json.dumps([[g.oxygen, g.helium] for g in dive.gasmixes])
        volume, start, end, source = self.tank_defaults(dive)
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO dives (
                    uid, device_serial, fingerprint, started_at, mode, duration,
                    max_depth, avg_depth, temp_min, temp_max, atmospheric,
                    salinity, units_metric, sample_interval, settings, gasmixes,
                    site, tank_volume, pressure_start, pressure_end, tank_edited,
                    tank_source, imported_at, raw
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                          ?, ?, 0, ?, ?, ?)
                """,
                (
                    dive.uid,
                    dive.device_serial,
                    dive.fingerprint,
                    dive.datetime.isoformat(timespec="seconds"),
                    int(dive.mode),
                    dive.duration,
                    dive.max_depth,
                    dive.avg_depth,
                    dive.temperature_min,
                    dive.temperature_max,
                    dive.atmospheric,
                    dive.salinity,
                    int(dive.units_metric),
                    dive.sample_interval,
                    dive.settings,
                    gasmixes,
                    site,
                    volume,
                    start,
                    end,
                    source,
                    now,
                    dive.raw,
                ),
            )
            self.conn.executemany(
                """
                INSERT OR REPLACE INTO samples
                    (dive_uid, time, depth, temperature, gasmix, pressure)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (dive.uid, s.time, s.depth, s.temperature, s.gasmix, s.pressure)
                    for s in dive.samples
                ],
            )
        return True

    def log_import(self, result: ImportResult) -> None:
        self.conn.execute(
            """
            INSERT INTO imports (at, device_serial, added, skipped, message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                _dt.datetime.now().isoformat(timespec="seconds"),
                result.device.serial if result.device else None,
                result.count,
                result.skipped,
                result.message,
            ),
        )
        self.conn.commit()

    def update_annotations(
        self,
        uid: str,
        *,
        site: str | None = None,
        buddy: str | None = None,
        notes: str | None = None,
        rating: int | None = None,
        tank_volume: float | None = None,
        pressure_start: float | None = None,
        pressure_end: float | None = None,
    ) -> None:
        """Met a jour les champs saisis par le plongeur."""
        updates: dict[str, object | None] = {
            "site": site,
            "buddy": buddy,
            "notes": notes,
            "rating": rating,
            "tank_volume": tank_volume,
            "pressure_start": pressure_start,
            "pressure_end": pressure_end,
        }
        pairs = {key: value for key, value in updates.items() if value is not None}
        if not pairs:
            return
        # Des que le bloc est saisi, la fiche cesse d'afficher une hypothese.
        if {"tank_volume", "pressure_start", "pressure_end"} & pairs.keys():
            pairs["tank_edited"] = 1
            pairs["tank_source"] = TankSource.USER.value
        assignments = ", ".join(f"{key} = ?" for key in pairs)
        with self.conn:
            self.conn.execute(
                f"UPDATE dives SET {assignments} WHERE uid = ?", (*pairs.values(), uid)
            )

    # -- masquage -----------------------------------------------------------

    def hide_dive(self, uid: str) -> bool:
        """Retire une plongee du carnet et interdit sa reimportation.

        Utile pour les plongees de l'ancien proprietaire d'un ordinateur
        d'occasion: elles restent dans la memoire de l'appareil, mais l'import
        ne les reprendra plus.
        """
        row = self.conn.execute(
            """
            SELECT device_serial, fingerprint, started_at, max_depth, duration, site
            FROM dives WHERE uid = ?
            """,
            (uid,),
        ).fetchone()
        if row is None:
            return False
        with self.conn:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO ignored (
                    device_serial, fingerprint, started_at, max_depth, duration,
                    site, hidden_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["device_serial"],
                    row["fingerprint"],
                    row["started_at"],
                    row["max_depth"],
                    row["duration"],
                    row["site"] or "",
                    _dt.datetime.now().isoformat(timespec="seconds"),
                ),
            )
            self.conn.execute("DELETE FROM samples WHERE dive_uid = ?", (uid,))
            self.conn.execute("DELETE FROM dives WHERE uid = ?", (uid,))
        return True

    def restore_hidden(self, device_serial: str, fingerprint: str) -> None:
        """Reautorise l'import d'une plongee masquee."""
        with self.conn:
            self.conn.execute(
                "DELETE FROM ignored WHERE device_serial = ? AND fingerprint = ?",
                (device_serial, fingerprint),
            )

    def hidden_dives(self) -> list[HiddenDive]:
        rows = self.conn.execute(
            "SELECT * FROM ignored ORDER BY started_at DESC"
        ).fetchall()
        return [
            HiddenDive(
                device_serial=row["device_serial"],
                fingerprint=row["fingerprint"],
                started_at=_parse_datetime(row["started_at"]),
                max_depth=row["max_depth"],
                duration=row["duration"],
                site=row["site"] or "",
                hidden_at=_parse_datetime(row["hidden_at"]),
            )
            for row in rows
        ]

    def ignored_fingerprints(self, device_serial: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT fingerprint FROM ignored WHERE device_serial = ?", (device_serial,)
        ).fetchall()
        return {row["fingerprint"] for row in rows}

    def hidden_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS n FROM ignored").fetchone()
        return int(row["n"])

    def delete_dive(self, uid: str) -> None:
        """Supprime une plongee sans interdire sa reimportation."""
        with self.conn:
            self.conn.execute("DELETE FROM samples WHERE dive_uid = ?", (uid,))
            self.conn.execute("DELETE FROM dives WHERE uid = ?", (uid,))

    # -- lecture ------------------------------------------------------------

    def has_dive(self, device_serial: str, fingerprint: str) -> bool:
        row = self.conn.execute(
            "SELECT 1 FROM dives WHERE device_serial = ? AND fingerprint = ?",
            (device_serial, fingerprint),
        ).fetchone()
        return row is not None

    def last_fingerprint(self, device_serial: str) -> bytes | None:
        """Empreinte de la plongee la plus recente deja en base.

        Elle sert de point d'arret lors de l'import: l'ordinateur restitue ses
        plongees de la plus recente a la plus ancienne.
        """
        row = self.conn.execute(
            """
            SELECT fingerprint FROM dives
            WHERE device_serial = ?
            ORDER BY started_at DESC LIMIT 1
            """,
            (device_serial,),
        ).fetchone()
        if row is None:
            return None
        try:
            return bytes.fromhex(row["fingerprint"])
        except ValueError:
            return None

    def known_fingerprints(self, device_serial: str) -> set[str]:
        rows = self.conn.execute(
            "SELECT fingerprint FROM dives WHERE device_serial = ?", (device_serial,)
        ).fetchall()
        return {row["fingerprint"] for row in rows}

    def list_dives(self, order: str = "desc") -> list[DiveSummary]:
        """Renvoie les resumes; `number` est le rang chronologique (1 = 1re)."""
        direction = "DESC" if order.lower() == "desc" else "ASC"
        rows = self.conn.execute(
            f"""
            SELECT uid, device_serial, fingerprint, started_at, mode, duration,
                   max_depth, avg_depth, temp_min, temp_max, gasmixes, site,
                   buddy, notes, rating, salinity, tank_volume, pressure_start,
                   pressure_end, tank_edited, tank_source,
                   ROW_NUMBER() OVER (ORDER BY started_at ASC) AS number
            FROM dives
            ORDER BY started_at {direction}
            """
        ).fetchall()
        return [self._summary_from_row(row) for row in rows]

    def load_dive(self, uid: str) -> Dive | None:
        """Recharge une plongee complete, profil inclus."""
        row = self.conn.execute("SELECT * FROM dives WHERE uid = ?", (uid,)).fetchone()
        if row is None:
            return None
        samples = [
            Sample(
                time=s["time"],
                depth=s["depth"],
                temperature=s["temperature"],
                gasmix=s["gasmix"],
                pressure=s["pressure"],
            )
            for s in self.conn.execute(
                "SELECT * FROM samples WHERE dive_uid = ? ORDER BY time", (uid,)
            )
        ]
        return Dive(
            datetime=_dt.datetime.fromisoformat(row["started_at"]),
            mode=DiveMode(row["mode"]),
            max_depth=row["max_depth"],
            avg_depth=row["avg_depth"],
            duration=row["duration"],
            sample_interval=row["sample_interval"],
            temperature_min=row["temp_min"],
            temperature_max=row["temp_max"],
            atmospheric=row["atmospheric"],
            salinity=row["salinity"] or "salt",
            units_metric=bool(row["units_metric"]),
            gasmixes=_decode_gasmixes(row["gasmixes"]),
            samples=samples,
            settings=row["settings"],
            device_serial=row["device_serial"],
            fingerprint=row["fingerprint"],
            raw=row["raw"] or b"",
        )

    def devices(self) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM devices ORDER BY last_seen DESC"
        ).fetchall()

    def import_history(self, limit: int = 20) -> list[sqlite3.Row]:
        return self.conn.execute(
            "SELECT * FROM imports ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()

    def depth_histogram(self, bucket: float = 3.0) -> list[tuple[float, int]]:
        """Temps cumule passe par tranche de profondeur, tous profils confondus.

        Renvoie `(borne_basse_de_tranche, secondes)`. Le pas de temps vient de
        l'intervalle d'echantillonnage propre a chaque plongee.
        """
        rows = self.conn.execute(
            """
            SELECT CAST(s.depth / ? AS INTEGER) AS slot,
                   SUM(d.sample_interval) AS seconds
            FROM samples s
            JOIN dives d ON d.uid = s.dive_uid
            WHERE s.depth >= 0.5
            GROUP BY slot
            ORDER BY slot
            """,
            (bucket,),
        ).fetchall()
        return [(row["slot"] * bucket, int(row["seconds"] or 0)) for row in rows]

    def _summary_from_row(self, row: sqlite3.Row) -> DiveSummary:
        return DiveSummary(
            uid=row["uid"],
            number=row["number"],
            started_at=_dt.datetime.fromisoformat(row["started_at"]),
            mode=DiveMode(row["mode"]),
            duration=row["duration"],
            max_depth=row["max_depth"],
            avg_depth=row["avg_depth"],
            temp_min=row["temp_min"],
            temp_max=row["temp_max"],
            gasmixes=_decode_gasmixes(row["gasmixes"]),
            site=row["site"] or "",
            buddy=row["buddy"] or "",
            notes=row["notes"] or "",
            rating=row["rating"] or 0,
            tank_volume=row["tank_volume"] or 0.0,
            pressure_start=row["pressure_start"] or 0.0,
            pressure_end=row["pressure_end"] or 0.0,
            tank_edited=bool(row["tank_edited"]),
            tank_source=row["tank_source"] or TankSource.DEFAULT.value,
            device_serial=row["device_serial"],
            fingerprint=row["fingerprint"],
            salinity=row["salinity"] or "salt",
        )

    # -- import -------------------------------------------------------------

    def import_dives(
        self, dives: Iterable[tuple[Dive, str]], device: DeviceInfo | None = None
    ) -> ImportResult:
        """Insere une serie de plongees et journalise le bilan."""
        result = ImportResult(device=device)
        if device:
            self.upsert_device(device)
        for dive, site in dives:
            try:
                if self.add_dive(dive, site=site):
                    summary = self._summary_of(dive.uid)
                    if summary:
                        result.added.append(summary)
                else:
                    result.skipped += 1
            except sqlite3.Error as exc:
                result.errors.append(f"{dive.datetime:%Y-%m-%d %H:%M}: {exc}")
        self.log_import(result)
        return result

    def _summary_of(self, uid: str) -> DiveSummary | None:
        row = self.conn.execute(
            """
            SELECT uid, device_serial, fingerprint, started_at, mode, duration,
                   max_depth, avg_depth, temp_min, temp_max, gasmixes, site,
                   buddy, notes, rating, salinity, tank_volume, pressure_start,
                   pressure_end, tank_edited, tank_source,
                   (SELECT COUNT(*) FROM dives d2 WHERE d2.started_at <= d.started_at)
                       AS number
            FROM dives d WHERE uid = ?
            """,
            (uid,),
        ).fetchone()
        return self._summary_from_row(row) if row else None


def _decode_gasmixes(raw: str | None) -> list[GasMix]:
    if not raw:
        return []
    try:
        return [GasMix(oxygen=int(o), helium=int(he)) for o, he in json.loads(raw)]
    except (ValueError, TypeError):
        log.warning("Melanges illisibles en base: %r", raw)
        return []


def _parse_datetime(value: str | None) -> _dt.datetime | None:
    if not value:
        return None
    try:
        return _dt.datetime.fromisoformat(value)
    except ValueError:
        return None


def iter_samples(db: Database, uid: str) -> Iterator[Sample]:
    """Itere les echantillons d'une plongee sans charger tout l'objet."""
    for row in db.conn.execute(
        "SELECT * FROM samples WHERE dive_uid = ? ORDER BY time", (uid,)
    ):
        yield Sample(
            time=row["time"],
            depth=row["depth"],
            temperature=row["temperature"],
            gasmix=row["gasmix"],
            pressure=row["pressure"],
        )
