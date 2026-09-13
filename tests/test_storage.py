"""Tests de la base: doublons, valeurs de bloc par defaut, masquage."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from thermocline.importer import import_dives
from thermocline.simulator import SimulatedDevice
from thermocline.storage import (
    DEFAULT_PRESSURE_END,
    DEFAULT_PRESSURE_START,
    DEFAULT_TANK_VOLUME,
    Database,
)


class DatabaseTestCase(unittest.TestCase):
    """Base neuve dans un dossier temporaire, remplie par le simulateur."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "dives.sqlite"
        self.db = Database(self.path)

    def tearDown(self) -> None:
        self.db.close()
        self._tmp.cleanup()

    def fill(self, count: int | None = None) -> None:
        import_dives(self.db, SimulatedDevice(count=count))


class ImportTests(DatabaseTestCase):
    def test_import_then_reimport_adds_nothing(self) -> None:
        first = import_dives(self.db, SimulatedDevice())
        self.assertGreater(first.count, 0)

        second = import_dives(self.db, SimulatedDevice())
        self.assertEqual(second.count, 0)
        self.assertEqual(len(self.db.list_dives()), first.count)

    def test_numbering_follows_chronology(self) -> None:
        self.fill()
        rows = self.db.list_dives(order="asc")
        self.assertEqual([row.number for row in rows], list(range(1, len(rows) + 1)))
        self.assertEqual(rows, sorted(rows, key=lambda r: r.started_at))


class TankDefaultTests(DatabaseTestCase):
    def test_new_dives_get_default_tank(self) -> None:
        self.fill(count=2)
        row = self.db.list_dives()[0]
        self.assertEqual(row.tank_volume, DEFAULT_TANK_VOLUME)
        self.assertEqual(row.pressure_start, DEFAULT_PRESSURE_START)
        self.assertEqual(row.pressure_end, DEFAULT_PRESSURE_END)
        self.assertFalse(row.tank_edited)

    def test_saving_the_tank_marks_it_as_entered(self) -> None:
        self.fill(count=2)
        row = self.db.list_dives()[0]
        self.db.update_annotations(row.uid, tank_volume=15.0)

        updated = self.db.list_dives()[0]
        self.assertEqual(updated.tank_volume, 15.0)
        self.assertTrue(updated.tank_edited)

    def test_notes_alone_do_not_mark_the_tank(self) -> None:
        self.fill(count=2)
        row = self.db.list_dives()[0]
        self.db.update_annotations(row.uid, site="Les Moyades")

        updated = self.db.list_dives()[0]
        self.assertEqual(updated.site, "Les Moyades")
        self.assertFalse(updated.tank_edited)


class HiddenDiveTests(DatabaseTestCase):
    def test_hidden_dive_leaves_the_logbook(self) -> None:
        self.fill()
        rows = self.db.list_dives()
        target = rows[0]

        self.assertTrue(self.db.hide_dive(target.uid))
        remaining = self.db.list_dives()

        self.assertEqual(len(remaining), len(rows) - 1)
        self.assertNotIn(target.uid, [row.uid for row in remaining])
        self.assertEqual(self.db.hidden_count(), 1)
        self.assertIn(
            target.fingerprint, self.db.ignored_fingerprints(target.device_serial)
        )
        # Le profil part avec la plongee.
        self.assertIsNone(self.db.load_dive(target.uid))

    def test_hidden_dive_is_not_reimported(self) -> None:
        self.fill()
        target = self.db.list_dives()[0]
        self.db.hide_dive(target.uid)
        before = len(self.db.list_dives())

        # Relecture complete: l'ordinateur repropose toutes ses plongees.
        result = import_dives(self.db, SimulatedDevice(), full=True)

        self.assertEqual(result.count, 0)
        self.assertEqual(result.ignored, 1)
        self.assertEqual(len(self.db.list_dives()), before)

    def test_hidden_entry_keeps_a_readable_label(self) -> None:
        self.fill()
        target = self.db.list_dives()[0]
        self.db.update_annotations(target.uid, site="Épave du Donator")
        self.db.hide_dive(target.uid)

        entry = self.db.hidden_dives()[0]
        self.assertEqual(entry.fingerprint, target.fingerprint)
        self.assertIn("Épave du Donator", entry.label)
        self.assertIn(f"{target.max_depth:.1f} m", entry.label)

    def test_restoring_allows_the_dive_back(self) -> None:
        self.fill()
        target = self.db.list_dives()[0]
        self.db.hide_dive(target.uid)
        self.db.restore_hidden(target.device_serial, target.fingerprint)

        self.assertEqual(self.db.hidden_count(), 0)
        result = import_dives(self.db, SimulatedDevice(), full=True)

        self.assertEqual(result.count, 1)
        self.assertIn(target.fingerprint, self.db.known_fingerprints(target.device_serial))

    def test_hiding_the_latest_moves_the_stop_marker(self) -> None:
        """L'import incremental doit repartir de la plongee restante la plus recente."""
        self.fill()
        rows = self.db.list_dives()  # du plus recent au plus ancien
        self.db.hide_dive(rows[0].uid)

        self.assertEqual(
            self.db.last_fingerprint(rows[1].device_serial),
            bytes.fromhex(rows[1].fingerprint),
        )
        # Un import incremental ne ramene pas la plongee masquee.
        result = import_dives(self.db, SimulatedDevice())
        self.assertEqual(result.count, 0)


class MigrationTests(unittest.TestCase):
    def test_old_database_gains_the_new_columns(self) -> None:
        """Une base au format precedent doit s'ouvrir et se completer."""
        import sqlite3

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "old.sqlite"
            conn = sqlite3.connect(path)
            conn.executescript(
                """
                CREATE TABLE dives (
                    uid TEXT PRIMARY KEY,
                    device_serial TEXT NOT NULL,
                    fingerprint TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    mode INTEGER NOT NULL,
                    duration INTEGER NOT NULL,
                    max_depth REAL NOT NULL,
                    imported_at TEXT NOT NULL
                );
                INSERT INTO dives VALUES
                    ('abc', '1', 'ff', '2024-05-01T10:00:00', 0, 1800, 22.0,
                     '2024-05-01T12:00:00');
                """
            )
            conn.commit()
            conn.close()

            db = Database(path)
            try:
                columns = {
                    row["name"] for row in db.conn.execute("PRAGMA table_info(dives)")
                }
                self.assertLessEqual(
                    {"tank_volume", "pressure_start", "pressure_end", "tank_edited"},
                    columns,
                )
                row = db.conn.execute(
                    "SELECT tank_volume, pressure_end FROM dives WHERE uid = 'abc'"
                ).fetchone()
                # La plongee existante recoit les valeurs par defaut.
                self.assertEqual(row["tank_volume"], DEFAULT_TANK_VOLUME)
                self.assertEqual(row["pressure_end"], DEFAULT_PRESSURE_END)
                self.assertEqual(db.hidden_count(), 0)
            finally:
                db.close()


if __name__ == "__main__":
    unittest.main()
