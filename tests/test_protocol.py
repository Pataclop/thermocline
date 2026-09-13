"""Tests du protocole Mares, sur de faux ordinateurs en memoire.

`FakeFlashTransport` rejoue le dialogue octet par octet des familles IconHD et
Smart: entete de commande, acquittement, charge utile, donnees, octet de fin.
La memoire flash est un `bytearray` dans lequel on place de vraies trames de
plongee fabriquees par `simulator.encode_dive`.

`FakeObjectTransport` fait la meme chose pour la famille Genius / Sirius, qui
ne donne pas acces a sa memoire et repond par objets numerotes.
"""

from __future__ import annotations

import datetime as _dt
import unittest

from thermocline import device as dev
from thermocline.models import DiveMode
from thermocline.simulator import encode_dive, encode_genius_dive, make_profile

SERIAL = 1234567


class FakeFlashTransport:
    """Transport en memoire qui parle le protocole a lecture de flash."""

    def __init__(self, flash: bytearray, model: bytes = b"Quad") -> None:
        self.flash = flash
        self.model = model
        self.out = bytearray()
        self.pending: int | None = None
        self.commands: list[int] = []

    # -- interface attendue par MaresDevice --------------------------------

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def purge(self) -> None:
        self.out.clear()

    def sleep(self, seconds: float) -> None:
        return None

    def write(self, data: bytes) -> None:
        if self.pending is None:
            command, checksum = data
            assert checksum == command ^ dev.XOR, "octet de contrôle invalide"
            self.commands.append(command)
            self.pending = command
            if command == dev.CMD_VERSION:
                self.out += bytes([dev.ACK]) + self._version() + bytes([dev.END])
                self.pending = None
            elif command == dev.CMD_FLASHSIZE:
                self.out += (
                    bytes([dev.ACK])
                    + len(self.flash).to_bytes(4, "little")
                    + bytes([dev.END])
                )
                self.pending = None
            elif command == dev.CMD_READ:
                self.out += bytes([dev.ACK])  # la charge utile suit
            else:  # pragma: no cover - commande non utilisee par les tests
                raise AssertionError(f"commande inattendue 0x{command:02X}")
            return

        assert self.pending == dev.CMD_READ
        address = int.from_bytes(data[0:4], "little")
        size = int.from_bytes(data[4:8], "little")
        assert address + size <= len(self.flash), "lecture hors mémoire"
        self.out += self.flash[address : address + size] + bytes([dev.END])
        self.pending = None

    def read(self, size: int) -> bytes:
        assert len(self.out) >= size, "l'hôte lit plus que ce qui a été émis"
        chunk = bytes(self.out[:size])
        del self.out[:size]
        return chunk

    def _version(self) -> bytes:
        packet = bytearray(dev.VERSION_SIZE)
        packet[dev.MODEL_NAME_OFFSET : dev.MODEL_NAME_OFFSET + len(self.model)] = (
            self.model
        )
        return bytes(packet)


class FakeObjectTransport:
    """Transport en memoire qui parle le protocole par objets (Genius)."""

    def __init__(self, objects: dict[tuple[int, int], bytes], model: bytes = b"Quad2"):
        self.objects = objects
        self.model = model
        self.out = bytearray()
        self.pending: int | None = None
        self.commands: list[int] = []
        self._stream = bytearray()
        self._toggle = 0

    def open(self) -> None:
        return None

    def close(self) -> None:
        return None

    def purge(self) -> None:
        self.out.clear()

    def sleep(self, seconds: float) -> None:
        return None

    def write(self, data: bytes) -> None:
        if self.pending is None:
            command, checksum = data
            assert checksum == command ^ dev.XOR, "octet de contrôle invalide"
            self.commands.append(command)
            self.pending = command
            if command == dev.CMD_VERSION:
                packet = bytearray(dev.VERSION_SIZE)
                packet[dev.MODEL_NAME_OFFSET : dev.MODEL_NAME_OFFSET + len(self.model)] = (
                    self.model
                )
                self.out += bytes([dev.ACK]) + bytes(packet) + bytes([dev.END])
                self.pending = None
            elif command == dev.CMD_OBJ_INIT:
                self.out += bytes([dev.ACK])  # la charge utile suit
            elif command in (dev.CMD_OBJ_EVEN, dev.CMD_OBJ_ODD):
                self._send_segment(command)
                self.pending = None
            else:  # pragma: no cover
                raise AssertionError(f"commande inattendue 0x{command:02X}")
            return

        assert self.pending == dev.CMD_OBJ_INIT
        assert data[0] == 0x40, "en-tête d'objet inattendue"
        index = int.from_bytes(data[1:3], "little")
        subindex = data[3]
        payload = self.objects[(index, subindex)]

        answer = bytearray(16)
        answer[1:4] = data[1:4]
        if len(payload) <= 12:
            answer[0] = 0x42
            answer[4 : 4 + len(payload)] = payload
            self._stream.clear()
        else:
            answer[0] = 0x41
            answer[4:8] = len(payload).to_bytes(4, "little")
            self._stream = bytearray(payload)
        self._toggle = 0
        self.out += bytes(answer) + bytes([dev.END])
        self.pending = None

    def _send_segment(self, command: int) -> None:
        expected = dev.CMD_OBJ_EVEN if self._toggle == 0 else dev.CMD_OBJ_ODD
        assert command == expected, "segment demandé hors séquence"
        size = min(len(self._stream), dev.OBJECT_PACKET_SIZE)
        chunk = bytes(self._stream[:size])
        del self._stream[:size]
        header = self._toggle << 4
        self.out += bytes([dev.ACK, header]) + chunk + bytes([dev.END])
        self._toggle ^= 1

    def read(self, size: int) -> bytes:
        assert len(self.out) >= size, "l'hôte lit plus que ce qui a été émis"
        chunk = bytes(self.out[:size])
        del self.out[:size]
        return chunk


def build_flash(
    records: list[bytes],
    layout: dev.MemoryLayout = dev.LAYOUT_ICONHD,
    start: int | None = None,
) -> bytearray:
    """Place les enregistrements et cale le pointeur de fin du buffer.

    Les trames sont ecrites du plus ancien au plus recent, comme le fait
    l'ordinateur; le pointeur de fin designe l'octet qui suit la plus recente.
    """
    flash = bytearray(b"\xff" * layout.memsize)
    flash[0x0C:0x10] = SERIAL.to_bytes(4, "little")

    cursor = layout.profile_begin if start is None else start
    for record in records:
        end = cursor + len(record)
        if end <= layout.profile_end:
            flash[cursor:end] = record
        else:  # bouclage du buffer circulaire
            head = layout.profile_end - cursor
            flash[cursor : layout.profile_end] = record[:head]
            tail = len(record) - head
            flash[layout.profile_begin : layout.profile_begin + tail] = record[head:]
            end = layout.profile_begin + tail
        cursor = (
            end
            if end < layout.profile_end
            else layout.profile_begin + (end - layout.profile_end)
        )

    flash[0x2001:0x2005] = cursor.to_bytes(4, "little")
    return flash


def sample_records(count: int = 3, model_id: int = dev.QUAD) -> list[bytes]:
    """Quelques trames de plongee, de la plus ancienne a la plus recente."""
    base = _dt.datetime(2025, 6, 1, 9, 30)
    records = []
    for index in range(count):
        profile = make_profile(20.0 + index * 5, 12 + index, interval=5)
        records.append(
            encode_dive(
                base + _dt.timedelta(days=index),
                profile,
                interval=5,
                mode=DiveMode.NITROX,
                gasmixes=(32,),
                model_id=model_id,
            )
        )
    return records


def genius_objects(count: int = 3) -> dict[tuple[int, int], bytes]:
    """Les objets qu'un Genius exposerait pour `count` plongees."""
    base = _dt.datetime(2025, 6, 1, 9, 30)
    objects: dict[tuple[int, int], bytes] = {
        (dev.OBJ_DEVICE, dev.OBJ_DEVICE_MODEL): (0x32).to_bytes(4, "little"),
        (dev.OBJ_DEVICE, dev.OBJ_DEVICE_SERIAL): b"\x00" * 10 + b"123456",
        (dev.OBJ_LOGBOOK, dev.OBJ_LOGBOOK_COUNT): count.to_bytes(2, "little"),
    }
    # L'ordinateur restitue ses plongees de la plus recente a la plus ancienne.
    for index in range(count):
        profile = make_profile(20.0 + index * 5, 10 + index, interval=5)
        record = encode_genius_dive(
            base - _dt.timedelta(days=index), profile, tank=(12.0, 200.0, 70.0)
        )
        header_size = 0xB8
        objects[(dev.OBJ_DIVE + index, dev.OBJ_DIVE_HEADER)] = record[:header_size]
        objects[(dev.OBJ_DIVE + index, dev.OBJ_DIVE_DATA)] = record[header_size:]
    return objects


class ConnectTests(unittest.TestCase):
    def test_identifies_quad_and_reads_serial(self) -> None:
        transport = FakeFlashTransport(build_flash(sample_records(1)))
        computer = dev.MaresDevice(transport)
        info = computer.connect()

        self.assertEqual(info.model_name, "Quad")
        self.assertEqual(info.model_id, dev.QUAD)
        self.assertEqual(info.serial, str(SERIAL))
        self.assertEqual(info.memory_size, dev.LAYOUT_ICONHD.memsize)
        self.assertEqual(computer.layout, dev.LAYOUT_ICONHD)
        self.assertEqual(computer.packet_size, 256)
        # Version, taille de flash, puis lecture du numero de serie.
        self.assertEqual(
            transport.commands[:3],
            [dev.CMD_VERSION, dev.CMD_FLASHSIZE, dev.CMD_READ],
        )

    def test_small_flash_selects_the_other_layout(self) -> None:
        flash = build_flash(sample_records(1))
        transport = FakeFlashTransport(bytearray(flash[:0x40000]))
        # Le pointeur de fin doit rester dans les bornes du petit plan memoire.
        transport.flash[0x2001:0x2005] = (0x0B000).to_bytes(4, "little")
        computer = dev.MaresDevice(transport)
        computer.connect()
        self.assertEqual(computer.layout, dev.LAYOUT_NEMOWIDE2)

    def test_each_family_is_recognised(self) -> None:
        for name, family in (
            ("Quad", dev.Family.ICONHD),
            ("Smart", dev.Family.SMART),
            ("Quad2", dev.Family.GENIUS),
        ):
            self.assertIs(dev.MODELS[name].family, family, name)

    def test_unknown_model_is_rejected(self) -> None:
        transport = FakeFlashTransport(build_flash([]), model=b"Perdix")
        with self.assertRaises(dev.ProtocolError) as caught:
            dev.MaresDevice(transport).connect()
        self.assertIn("non reconnu", str(caught.exception))

    def test_forced_model_overrides_detection(self) -> None:
        """Un ordinateur qui s'annonce mal reste lisible si on le nomme."""
        transport = FakeFlashTransport(build_flash(sample_records(1)), model=b"Inconnu")
        computer = dev.MaresDevice(transport, force_model="Quad")
        info = computer.connect()
        self.assertEqual(info.model_id, dev.QUAD)

    def test_forced_model_must_exist(self) -> None:
        transport = FakeFlashTransport(build_flash([]))
        with self.assertRaises(dev.ProtocolError):
            dev.MaresDevice(transport, force_model="Perdix").connect()

    def test_bad_trailer_is_retried_then_fails(self) -> None:
        transport = FakeFlashTransport(build_flash([]))
        original = transport.write

        def corrupt(data: bytes) -> None:
            original(data)
            if transport.out:  # remplace l'octet de fin
                transport.out[-1] = 0x00

        transport.write = corrupt  # type: ignore[method-assign]
        with self.assertRaises(dev.TransportError):
            dev.MaresDevice(transport, retry_delay=0.0).connect()
        # Une tentative initiale, puis MAX_RETRIES reprises.
        self.assertEqual(
            transport.commands.count(dev.CMD_VERSION), dev.MAX_RETRIES + 1
        )

    def test_retry_count_is_configurable(self) -> None:
        """Un ordinateur capricieux doit pouvoir etre relance plus souvent."""
        transport = FakeFlashTransport(build_flash([]))
        original = transport.write

        def corrupt(data: bytes) -> None:
            original(data)
            if transport.out:
                transport.out[-1] = 0x00

        transport.write = corrupt  # type: ignore[method-assign]
        with self.assertRaises(dev.TransportError):
            dev.MaresDevice(transport, retries=1, retry_delay=0.0).connect()
        self.assertEqual(transport.commands.count(dev.CMD_VERSION), 2)


class DownloadTests(unittest.TestCase):
    def _download(self, flash: bytearray, model: bytes = b"Quad", **kwargs) -> list[bytes]:
        computer = dev.MaresDevice(FakeFlashTransport(flash, model=model))
        computer.connect()
        return list(computer.iter_raw_dives(**kwargs))

    def test_returns_dives_newest_first(self) -> None:
        records = sample_records(3)
        got = self._download(build_flash(records))

        self.assertEqual(len(got), 3)
        self.assertEqual(got, list(reversed(records)))

    def test_smart_family_header_is_read_from_the_other_end(self) -> None:
        """Le Smart place type et nombre d'echantillons en fin d'entete."""
        records = sample_records(2, model_id=dev.SMART)
        flash = build_flash(records, dev.LAYOUT_NEMOWIDE2)
        got = self._download(flash, model=b"Smart")
        self.assertEqual(got, list(reversed(records)))

    def test_empty_memory_yields_nothing(self) -> None:
        flash = bytearray(b"\xff" * dev.LAYOUT_ICONHD.memsize)
        flash[0x0C:0x10] = SERIAL.to_bytes(4, "little")
        self.assertEqual(self._download(flash), [])

    def test_limit_stops_early(self) -> None:
        records = sample_records(3)
        got = self._download(build_flash(records), limit=2)
        self.assertEqual(got, [records[2], records[1]])

    def test_fingerprint_stops_at_known_dive(self) -> None:
        records = sample_records(3)
        geometry = dev.dive_geometry(dev.QUAD, 0)
        middle = records[1]
        start = len(middle) - geometry.header_size + geometry.fingerprint_offset
        fingerprint = middle[start : start + 10]

        got = self._download(build_flash(records), fingerprint=fingerprint)
        # On s'arrete des que l'empreinte connue est rencontree.
        self.assertEqual(got, [records[2]])

    def test_wrapped_ringbuffer_is_reassembled(self) -> None:
        records = sample_records(2)
        # La derniere trame chevauche la fin de la zone de profils.
        start = dev.LAYOUT_ICONHD.profile_end - len(records[0]) - len(records[1]) // 2
        got = self._download(build_flash(records, start=start))

        self.assertEqual(len(got), 2)
        self.assertEqual(got[0], records[1])
        self.assertEqual(got[1], records[0])

    def test_reads_only_what_is_needed(self) -> None:
        """Importer la derniere plongee ne doit pas relire toute la flash."""
        records = sample_records(3)
        transport = FakeFlashTransport(build_flash(records))
        computer = dev.MaresDevice(transport)
        computer.connect()
        list(computer.iter_raw_dives(limit=1))

        reads = transport.commands.count(dev.CMD_READ)
        # Quelques paquets de 256 octets, tres loin des 4096 d'une flash entiere.
        self.assertLess(reads, 40)


class ObjectProtocolTests(unittest.TestCase):
    """Famille Genius / Sirius: plus de flash, des objets numerotes."""

    def _connect(self, count: int = 3) -> tuple[dev.MaresDevice, FakeObjectTransport]:
        transport = FakeObjectTransport(genius_objects(count))
        computer = dev.MaresDevice(transport)
        computer.connect()
        return computer, transport

    def test_connects_and_reads_serial_from_an_object(self) -> None:
        computer, transport = self._connect(1)
        self.assertEqual(computer.model_id, dev.QUAD2)
        self.assertIs(computer.family, dev.Family.GENIUS)
        self.assertEqual(computer.serial, "123456")
        # Aucune lecture de memoire: ce modele n'en propose pas.
        self.assertNotIn(dev.CMD_READ, transport.commands)

    def test_dive_count_comes_from_the_logbook_object(self) -> None:
        computer, _ = self._connect(4)
        self.assertEqual(computer.dive_count(), 4)

    def test_downloads_every_dive(self) -> None:
        computer, _ = self._connect(3)
        dives = list(computer.iter_raw_dives())
        self.assertEqual(len(dives), 3)
        for record in dives:
            self.assertGreater(len(record), 0xB8)

    def test_long_objects_are_reassembled_from_segments(self) -> None:
        """Un profil depasse largement un segment: il arrive en morceaux."""
        computer, transport = self._connect(1)
        dives = list(computer.iter_raw_dives())
        self.assertGreater(len(dives[0]), dev.OBJECT_PACKET_SIZE)
        # Les segments alternent entre les deux commandes de lecture.
        self.assertIn(dev.CMD_OBJ_EVEN, transport.commands)
        self.assertIn(dev.CMD_OBJ_ODD, transport.commands)

    def test_fingerprint_stops_the_download(self) -> None:
        computer, _ = self._connect(3)
        first = list(computer.iter_raw_dives(limit=1))[0]
        fingerprint = first[0x08:0x0C]

        computer, _ = self._connect(3)
        self.assertEqual(list(computer.iter_raw_dives(fingerprint=fingerprint)), [])

    def test_memory_dump_is_refused_with_an_explanation(self) -> None:
        computer, _ = self._connect(1)
        with self.assertRaises(dev.UnsupportedModel):
            computer.dump_memory()


class GeometryTests(unittest.TestCase):
    """Les dimensions d'un enregistrement dependent du modele et du mode."""

    def test_iconhd_defaults(self) -> None:
        geometry = dev.dive_geometry(dev.QUAD, 0)
        self.assertEqual(geometry.header_size, 0x5C)
        self.assertEqual(geometry.sample_size, 8)
        self.assertEqual(geometry.fields_offset, 4)

    def test_air_integrated_models_have_larger_samples(self) -> None:
        for model in (dev.ICONHDNET, dev.QUADAIR):
            self.assertEqual(dev.dive_geometry(model, 0).sample_size, 12)

    def test_smart_fields_start_at_the_beginning(self) -> None:
        geometry = dev.dive_geometry(dev.SMART, 0)
        self.assertEqual(geometry.fields_offset, 0)
        self.assertEqual(geometry.fingerprint_offset, 2)

    def test_freedive_uses_a_shorter_header(self) -> None:
        self.assertEqual(dev.dive_geometry(dev.SMART, 3).header_size, 0x2E)
        self.assertEqual(dev.dive_geometry(dev.SMARTAIR, 3).header_size, 0x30)

    def test_air_integration_adds_pressure_blocks(self) -> None:
        geometry = dev.dive_geometry(dev.QUADAIR, 0)
        size = dev.record_size(dev.QUADAIR, geometry, 8, b"\x00" * geometry.header_size)
        # 8 echantillons de 12 octets, plus deux blocs de pression de 8 octets.
        self.assertEqual(size, 4 + geometry.header_size + 8 * 12 + 2 * 8)

    def test_type_and_sample_count_are_swapped_on_smart(self) -> None:
        header = (7).to_bytes(2, "little") + (2).to_bytes(2, "little")
        self.assertEqual(dev.read_type_and_samples(header, dev.QUAD), (7, 2))
        self.assertEqual(dev.read_type_and_samples(header, dev.SMART), (2, 7))


class ChecksumTests(unittest.TestCase):
    def test_crc16_ccitt_matches_the_reference_vector(self) -> None:
        # Vecteur classique du CRC-16/XMODEM.
        self.assertEqual(dev.crc16_ccitt(b"123456789"), 0x31C3)


if __name__ == "__main__":
    unittest.main()
