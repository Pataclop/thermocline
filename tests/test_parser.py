"""Tests du decodage, par aller-retour encodage / decodage.

Le simulateur fabrique de vraies trames binaires; le decodeur doit en
ressortir la meme plongee, pour chacune des trois familles Mares.
"""

from __future__ import annotations

import datetime as _dt
import unittest

from thermocline import device as dev
from thermocline.models import DiveMode
from thermocline.parser import ParseError, parse_raw_dive
from thermocline.simulator import encode_dive, encode_genius_dive, make_profile

WHEN = _dt.datetime(2025, 6, 14, 10, 25)


def flash_dive(model_id: int = dev.QUAD, **kwargs) -> bytes:
    profile = make_profile(30.0, 20, interval=5)
    return encode_dive(
        WHEN, profile, interval=5, mode=DiveMode.NITROX, gasmixes=(32,),
        model_id=model_id, **kwargs
    )


class FlashFamilyTests(unittest.TestCase):
    """Familles IconHD et Smart: memes champs, entete organisee autrement."""

    def test_iconhd_round_trip(self) -> None:
        dive = parse_raw_dive(flash_dive(), dev.QUAD, "42", "Quad")

        self.assertEqual(dive.datetime, WHEN)
        self.assertIs(dive.mode, DiveMode.NITROX)
        self.assertAlmostEqual(dive.max_depth, 31.2, places=1)
        self.assertEqual(dive.sample_interval, 5)
        self.assertEqual(dive.device_serial, "42")
        self.assertEqual([mix.oxygen for mix in dive.gasmixes], [32])
        self.assertTrue(dive.samples)

    def test_smart_round_trip_matches_iconhd(self) -> None:
        """La meme plongee doit se lire pareil dans les deux dispositions."""
        reference = parse_raw_dive(flash_dive(dev.QUAD), dev.QUAD)
        smart = parse_raw_dive(flash_dive(dev.SMART), dev.SMART)

        self.assertEqual(smart.datetime, reference.datetime)
        self.assertEqual(smart.max_depth, reference.max_depth)
        self.assertEqual(smart.duration, reference.duration)
        self.assertEqual(len(smart.samples), len(reference.samples))
        self.assertEqual(smart.fingerprint, reference.fingerprint)

    def test_fresh_water_is_read_from_the_settings(self) -> None:
        dive = parse_raw_dive(flash_dive(fresh_water=True), dev.QUAD)
        self.assertEqual(dive.salinity, "fresh")
        self.assertEqual(parse_raw_dive(flash_dive(), dev.QUAD).salinity, "salt")

    def test_several_gas_mixes(self) -> None:
        profile = make_profile(35.0, 15, interval=5)
        record = encode_dive(
            WHEN, profile, mode=DiveMode.NITROX, gasmixes=(28, 50), model_id=dev.QUAD
        )
        dive = parse_raw_dive(record, dev.QUAD)
        self.assertEqual([mix.oxygen for mix in dive.gasmixes], [28, 50])

    def test_air_mode_has_a_single_mix(self) -> None:
        profile = make_profile(20.0, 25, interval=5)
        record = encode_dive(WHEN, profile, mode=DiveMode.AIR, model_id=dev.QUAD)
        dive = parse_raw_dive(record, dev.QUAD)
        self.assertEqual([mix.oxygen for mix in dive.gasmixes], [21])

    def test_sample_interval_follows_the_settings(self) -> None:
        for interval in (1, 5, 10, 20):
            profile = make_profile(15.0, 5, interval=interval)
            record = encode_dive(WHEN, profile, interval=interval, model_id=dev.QUAD)
            self.assertEqual(parse_raw_dive(record, dev.QUAD).sample_interval, interval)

    def test_duration_excludes_the_surface_tail(self) -> None:
        record = flash_dive()
        dive = parse_raw_dive(record, dev.QUAD)
        samples = int.from_bytes(record[len(record) - 0x5C + 2 :][:2], "little")
        self.assertEqual(dive.duration, samples * 5 - 180)

    def test_truncated_record_is_rejected(self) -> None:
        with self.assertRaises(ParseError):
            parse_raw_dive(b"\x08\x00\x00\x00", dev.QUAD)

    def test_length_mismatch_is_rejected(self) -> None:
        record = bytearray(flash_dive())
        record[0:4] = (len(record) + 8).to_bytes(4, "little")
        with self.assertRaises(ParseError):
            parse_raw_dive(bytes(record), dev.QUAD)

    def test_impossible_date_is_rejected(self) -> None:
        record = bytearray(flash_dive())
        # Mois 13 dans l'entete: la trame est corrompue.
        head = len(record) - 0x5C + 4
        record[head + 0x08 : head + 0x0A] = (12).to_bytes(2, "little")
        with self.assertRaises(ParseError):
            parse_raw_dive(bytes(record), dev.QUAD)


class GeniusFamilyTests(unittest.TestCase):
    """Famille Genius / Sirius: entete d'objet et profil a enregistrements."""

    def setUp(self) -> None:
        self.profile = make_profile(30.0, 20, interval=5)
        self.record = encode_genius_dive(
            WHEN, self.profile, mode=1, gasmixes=((32, 0),), tank=(12.0, 200.0, 60.0)
        )
        self.dive = parse_raw_dive(self.record, dev.QUAD2, "999", "Quad2")

    def test_round_trip(self) -> None:
        self.assertEqual(self.dive.datetime, WHEN)
        self.assertIs(self.dive.mode, DiveMode.NITROX)
        self.assertAlmostEqual(self.dive.max_depth, 31.2, places=1)
        self.assertEqual(self.dive.sample_interval, 5)
        self.assertEqual(len(self.dive.samples), len(self.profile))

    def test_fingerprint_is_the_packed_timestamp(self) -> None:
        self.assertEqual(self.dive.fingerprint, self.record[0x08:0x0C].hex())

    def test_tank_pressures_come_from_the_device(self) -> None:
        tank = self.dive.measured_tank
        self.assertIsNotNone(tank)
        assert tank is not None
        self.assertAlmostEqual(tank.begin_pressure, 200.0, places=1)
        self.assertAlmostEqual(tank.end_pressure, 60.0, places=1)
        self.assertAlmostEqual(tank.volume, 12.0, places=1)

    def test_sampled_pressures_are_decoded(self) -> None:
        pressures = [s.pressure for s in self.dive.samples if s.pressure]
        self.assertTrue(pressures)
        self.assertLess(pressures[-1], pressures[0])

    def test_trimix_keeps_helium(self) -> None:
        record = encode_genius_dive(
            WHEN, self.profile, mode=3, gasmixes=((21, 35),)
        )
        dive = parse_raw_dive(record, dev.GENIUS)
        self.assertIs(dive.mode, DiveMode.TRIMIX)
        self.assertEqual(dive.gasmixes[0].helium, 35)
        self.assertEqual(dive.gasmixes[0].label, "Tx 21/35")

    def test_gauge_mode_is_recognised(self) -> None:
        record = encode_genius_dive(WHEN, self.profile, mode=4, gasmixes=())
        self.assertIs(parse_raw_dive(record, dev.SIRIUS).mode, DiveMode.GAUGE)

    def test_fresh_water(self) -> None:
        record = encode_genius_dive(WHEN, self.profile, fresh_water=True)
        self.assertEqual(parse_raw_dive(record, dev.QUAD2).salinity, "fresh")

    def test_corrupt_record_type_stops_the_profile(self) -> None:
        """Un enregistrement inconnu arrete le profil sans faire tout echouer."""
        record = bytearray(self.record)
        record[0xB8 + 4 : 0xB8 + 8] = b"ZZZZ"
        dive = parse_raw_dive(bytes(record), dev.QUAD2)
        self.assertEqual(dive.samples, [])

    def test_unsupported_header_version_is_rejected(self) -> None:
        record = bytearray(self.record)
        record[3] = 9  # version majeure d'entete hors de ce que l'on sait lire
        with self.assertRaises(ParseError):
            parse_raw_dive(bytes(record), dev.QUAD2)


class DispatchTests(unittest.TestCase):
    def test_family_decides_the_decoder(self) -> None:
        self.assertIs(dev.family_of(dev.QUAD), dev.Family.ICONHD)
        self.assertIs(dev.family_of(dev.SMARTAPNEA), dev.Family.SMART)
        self.assertIs(dev.family_of(dev.SIRIUS_L), dev.Family.GENIUS)

    def test_quad_variants_are_spread_across_families(self) -> None:
        """« Quad » ne doit jamais capturer « Quad Ci » ni « Quad2 »."""
        self.assertIs(dev.MODELS["Quad"].family, dev.Family.ICONHD)
        self.assertIs(dev.MODELS["Quad Air"].family, dev.Family.ICONHD)
        self.assertIs(dev.MODELS["Quad Ci"].family, dev.Family.GENIUS)
        self.assertIs(dev.MODELS["Quad2"].family, dev.Family.GENIUS)


if __name__ == "__main__":
    unittest.main()
