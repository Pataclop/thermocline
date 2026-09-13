"""Tests de l'import de carnet CSV: en-tetes tolerants, doublons, rejets."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from thermocline.csv_import import (
    CsvFormatError,
    annotate_known,
    import_rows,
    parse_csv_file,
)
from thermocline.storage import Database

CARNET_EXPORT = (
    "numero;date;heure;mode;duree_s;duree;prof_max_m;prof_moy_m;temp_min_c;"
    "temp_max_c;melanges;eau;site;binome;note;bloc_l;pression_depart_bar;"
    "pression_fin_bar;commentaire\n"
    "1;2026-08-01;09:30;Air;2400;40:00;22.5;12.0;18.0;22.0;Air;mer;Calanque;"
    "Marie;4;12.0;200;60;Belle visibilité\n"
    "2;2026-08-02;10:15;Nitrox;1800;30:00;18.0;10.0;19.0;23.0;EAN32;mer;"
    "Ile Verte;;;;;\n"
    "x;bad-date;;;;;;;;;;;;;;;;;\n"
)


class CsvImportTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.db = Database(self.dir / "dives.sqlite")

    def tearDown(self) -> None:
        self.db.close()
        self._tmp.cleanup()

    def write_csv(self, text: str, name: str = "carnet.csv") -> Path:
        path = self.dir / name
        path.write_text(text, encoding="utf-8-sig")
        return path

    def test_parses_the_apps_own_export_format(self) -> None:
        result = parse_csv_file(self.write_csv(CARNET_EXPORT))
        self.assertEqual(len(result.rows), 2)
        self.assertEqual(len(result.errors), 1)
        self.assertIn("Ligne 4", result.errors[0])

        first = result.rows[0]
        self.assertEqual(first.dive.max_depth, 22.5)
        self.assertEqual(first.dive.duration, 2400)
        self.assertEqual(first.site, "Calanque")
        self.assertEqual(first.buddy, "Marie")
        self.assertEqual(first.rating, 4)
        self.assertEqual(first.tank_volume, 12.0)
        self.assertEqual(first.dive.gas_label, "Air")

        second = result.rows[1]
        self.assertEqual(second.dive.gas_label, "EAN32")

    def test_tolerates_alternate_headers_and_comma_delimiter(self) -> None:
        text = "Date,Heure,Prof Max (m),Site,Binome\n01/09/2026,08:00,15.2,Épave,Jean\n"
        result = parse_csv_file(self.write_csv(text, "alt.csv"))
        self.assertEqual(len(result.rows), 1)
        row = result.rows[0]
        self.assertEqual(row.dive.max_depth, 15.2)
        self.assertEqual(row.site, "Épave")
        self.assertEqual(row.buddy, "Jean")

    def test_rejects_a_file_with_no_recognizable_column(self) -> None:
        path = self.write_csv("foo;bar\n1;2\n", "bad.csv")
        with self.assertRaises(CsvFormatError):
            parse_csv_file(path)

    def test_import_then_reparse_marks_duplicates(self) -> None:
        path = self.write_csv(CARNET_EXPORT)
        result = parse_csv_file(path)
        annotate_known(self.db, result)
        self.assertTrue(all(not row.duplicate for row in result.rows))

        imported = import_rows(self.db, result.rows)
        self.assertEqual(imported.count, 2)

        rows = {row.site: row for row in self.db.list_dives()}
        self.assertEqual(rows["Calanque"].buddy, "Marie")
        self.assertEqual(rows["Calanque"].rating, 4)
        self.assertEqual(rows["Calanque"].pressure_start, 200.0)

        reparsed = parse_csv_file(path)
        annotate_known(self.db, reparsed)
        self.assertTrue(all(row.duplicate for row in reparsed.rows))

    def test_only_selected_rows_are_imported(self) -> None:
        result = parse_csv_file(self.write_csv(CARNET_EXPORT))
        imported = import_rows(self.db, result.rows[:1])
        self.assertEqual(imported.count, 1)
        self.assertEqual(len(self.db.list_dives()), 1)


if __name__ == "__main__":
    unittest.main()
