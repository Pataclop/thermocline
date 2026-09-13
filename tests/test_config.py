"""Tests des preferences et de la traduction.

Les reglages sont le premier endroit ou un poste inconnu peut faire echouer
l'application: fichier absent, illisible, ecrit par une version differente,
dossier personnel verrouille. Rien de tout cela ne doit empecher le demarrage.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from thermocline import analytics, config, i18n
from thermocline.config import Settings


class SettingsFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / "settings.json"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_absent_file_gives_factory_settings(self) -> None:
        settings = Settings.load(self.path)
        self.assertEqual(settings.tank_volume, 12.0)
        self.assertEqual(settings.language, "auto")

    def test_round_trip(self) -> None:
        settings = Settings()
        settings.tank_volume = 15.0
        settings.language = "en"
        settings.force_model = "Puck Pro"
        settings.save(self.path)

        again = Settings.load(self.path)
        self.assertEqual(again.tank_volume, 15.0)
        self.assertEqual(again.language, "en")
        self.assertEqual(again.force_model, "Puck Pro")

    def test_unreadable_file_falls_back(self) -> None:
        self.path.write_text("{ceci n'est pas du JSON", encoding="utf-8")
        self.assertEqual(Settings.load(self.path).tank_volume, 12.0)

    def test_wrong_shape_falls_back(self) -> None:
        self.path.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertEqual(Settings.load(self.path).language, "auto")

    def test_unknown_keys_are_ignored(self) -> None:
        """Un fichier ecrit par une version plus recente reste lisible."""
        self.path.write_text(
            json.dumps({"tank_volume": 18.0, "reglage_du_futur": True}),
            encoding="utf-8",
        )
        self.assertEqual(Settings.load(self.path).tank_volume, 18.0)

    def test_invalid_value_keeps_the_default(self) -> None:
        self.path.write_text(json.dumps({"retries": "beaucoup"}), encoding="utf-8")
        self.assertEqual(Settings.load(self.path).retries, 4)

    def test_types_are_coerced(self) -> None:
        """JSON ne distingue pas toujours 12 de 12.0."""
        self.path.write_text(
            json.dumps({"tank_volume": 12, "retries": 2.0, "dtr": 1}), encoding="utf-8"
        )
        settings = Settings.load(self.path)
        self.assertIsInstance(settings.tank_volume, float)
        self.assertIsInstance(settings.retries, int)
        self.assertIs(settings.dtr, True)

    def test_saving_does_not_destroy_the_file_on_failure(self) -> None:
        Settings().save(self.path)
        self.assertTrue(self.path.exists())
        self.assertFalse(self.path.with_suffix(".tmp").exists())


class SettingsBehaviourTests(unittest.TestCase):
    def test_reset_keeps_the_database_path(self) -> None:
        settings = Settings()
        settings.db_path = "/quelque/part/dives.sqlite"
        settings.tank_volume = 20.0
        fresh = settings.reset()
        self.assertEqual(fresh.db_path, settings.db_path)
        self.assertEqual(fresh.tank_volume, 12.0)

    def test_copy_is_independent(self) -> None:
        settings = Settings()
        clone = settings.copy()
        clone.tank_volume = 24.0
        self.assertEqual(settings.tank_volume, 12.0)

    def test_gradient_is_a_fraction(self) -> None:
        settings = Settings()
        settings.gradient_factor = 85
        self.assertAlmostEqual(settings.gradient, 0.85)

    def test_gradient_is_clamped(self) -> None:
        settings = Settings()
        settings.gradient_factor = 500
        self.assertAlmostEqual(settings.gradient, 1.0)

    def test_apply_pushes_thresholds_into_analytics(self) -> None:
        settings = Settings()
        settings.ascent_limit = 9.0
        settings.ppo2_warn = 1.3
        settings.rate_window = 45
        try:
            config.apply(settings)
            self.assertEqual(analytics.LIMITS.ascent_limit, 9.0)
            self.assertEqual(analytics.LIMITS.ppo2_warn, 1.3)
            self.assertEqual(analytics.LIMITS.rate_window, 45)
        finally:
            config.apply(Settings())


class DiagnosticTests(unittest.TestCase):
    def test_diagnostic_never_raises_and_says_the_essentials(self) -> None:
        text = config.diagnostic().as_text()
        for expected in ("Python", "PyQt6", "pyserial"):
            self.assertIn(expected, text)


class TranslationTests(unittest.TestCase):
    def tearDown(self) -> None:
        i18n.set_language("fr")

    def test_french_is_the_source_language(self) -> None:
        i18n.set_language("fr")
        self.assertEqual(i18n.T("Importer les plongées"), "Importer les plongées")

    def test_english_translates(self) -> None:
        i18n.set_language("en")
        self.assertEqual(i18n.T("Importer les plongées"), "Import dives")

    def test_unknown_string_is_returned_as_is(self) -> None:
        i18n.set_language("en")
        self.assertEqual(i18n.T("phrase jamais traduite"), "phrase jamais traduite")

    def test_auto_resolves_to_a_known_language(self) -> None:
        self.assertIn(i18n.set_language("auto"), i18n.LANGUAGES)

    def test_unknown_language_falls_back_to_french(self) -> None:
        self.assertEqual(i18n.set_language("klingon"), "fr")

    def test_count_label_agrees(self) -> None:
        i18n.set_language("fr")
        self.assertEqual(
            i18n.count_label(1, "{count} plongée", "{count} plongées"), "1 plongée"
        )
        self.assertEqual(
            i18n.count_label(3, "{count} plongée", "{count} plongées"), "3 plongées"
        )

    def test_dates_follow_the_language(self) -> None:
        import datetime as _dt

        from thermocline import dates

        moment = _dt.datetime(2026, 9, 11, 14, 41)
        i18n.set_language("fr")
        self.assertEqual(dates.long_date(moment), "vendredi 11 septembre 2026")
        i18n.set_language("en")
        self.assertEqual(dates.long_date(moment), "Friday 11 September 2026")


if __name__ == "__main__":
    unittest.main()
