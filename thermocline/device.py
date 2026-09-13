"""Protocole des ordinateurs de plongee Mares.

Portage en Python des backends `mares_iconhd` de libdivecomputer (LGPL 2.1).
Trois familles se partagent le meme transport serie (115200 8E1) mais pas le
meme format de donnees:

* **IconHD** (Quad, Puck Pro, Puck 2, Matrix, Nemo Wide 2, Icon HD, Icon AIR,
  Quad Air): la memoire flash est lue directement, les plongees vivent dans un
  buffer circulaire, l'entete de chaque enregistrement se trouve a la fin.
* **Smart** (Smart, Smart Air, Smart Apnea): meme lecture de flash, mais le
  couple type / nombre d'echantillons est place a la **fin** de l'entete au
  lieu du debut, et la geometrie depend du mode de plongee.
* **Genius / Sirius** (Genius, Horizon, Sirius, Sirius L, Quad Ci, Quad2,
  Puck 4, Puck Air 2): plus de lecture de flash du tout. L'ordinateur expose
  des **objets** numerotes que l'on demande un par un.

Trame d'une commande, identique pour les trois familles:

    hote  -> [cmd, cmd ^ 0xA5]
    hote  <- [0xAA]                 (ACK)
    hote  -> [charge utile]         (si la commande en a une)
    hote  <- [reponse de N octets]
    hote  <- [0xEA]                 (fin de trame)
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import Enum

from .i18n import T
from .models import DeviceInfo
from .transport import SerialTransport, TransportError

log = logging.getLogger(__name__)

# -- constantes du protocole ------------------------------------------------

ACK = 0xAA
END = 0xEA
XOR = 0xA5

CMD_VERSION = 0xC2
CMD_FLASHSIZE = 0xB3
CMD_READ = 0xE7
CMD_OBJ_INIT = 0xBF
CMD_OBJ_EVEN = 0xAC
CMD_OBJ_ODD = 0xFE
CMD_SET_TIME = 0xB0

VERSION_SIZE = 140
MODEL_NAME_OFFSET = 0x46
MODEL_NAME_SIZE = 16
SERIAL_ADDRESS = 0x0C
MAX_RETRIES = 4

#: Taille maximale d'un segment d'objet sur liaison serie (famille Genius).
OBJECT_PACKET_SIZE = 504

# Objets exposes par la famille Genius.
OBJ_DEVICE = 0x2000
OBJ_DEVICE_MODEL = 0x02
OBJ_DEVICE_SERIAL = 0x04
OBJ_LOGBOOK = 0x2008
OBJ_LOGBOOK_COUNT = 0x01
OBJ_DIVE = 0x3000
OBJ_DIVE_HEADER = 0x02
OBJ_DIVE_DATA = 0x03

#: Pointeurs de fin de buffer circulaire, essayes dans cet ordre.
EOP_POINTERS = (0x2001, 0x3001)

# Identifiants modeles (valeurs libdivecomputer).
MATRIX = 0x0F
SMART = 0x000010
SMARTAPNEA = 0x010010
ICONHD = 0x14
ICONHDNET = 0x15
PUCKPRO = 0x18
NEMOWIDE2 = 0x19
GENIUS = 0x1C
PUCK2 = 0x1F
QUADAIR = 0x23
SMARTAIR = 0x24
QUAD = 0x29
HORIZON = 0x2C
PUCKAIR2 = 0x2D
SIRIUS = 0x2F
QUADCI = 0x31
QUAD2 = 0x32
SIRIUS_L = 0x33
PUCK4 = 0x35


class Family(str, Enum):
    """Format de donnees d'un modele."""

    ICONHD = "iconhd"
    """Lecture de flash, entete en fin d'enregistrement."""
    SMART = "smart"
    """Lecture de flash, type et nombre d'echantillons en fin d'entete."""
    GENIUS = "genius"
    """Protocole par objets, plus de lecture de flash."""


@dataclass(frozen=True)
class MemoryLayout:
    """Bornes du buffer circulaire des profils, en memoire flash."""

    memsize: int
    profile_begin: int
    profile_end: int


LAYOUT_ICONHD = MemoryLayout(0x100000, 0x00A000, 0x100000)
LAYOUT_ICONHDNET = MemoryLayout(0x100000, 0x00E000, 0x100000)
LAYOUT_MATRIX = MemoryLayout(0x40000, 0x0A000, 0x3E000)
LAYOUT_NEMOWIDE2 = MemoryLayout(0x40000, 0x0A000, 0x40000)
LAYOUT_GENIUS = MemoryLayout(0x1000000, 0x100000, 0x1000000)


@dataclass(frozen=True)
class ModelSpec:
    """Un modele Mares reconnu, avec ce qu'il faut pour lui parler."""

    name: str
    """Nom exact renvoye par l'ordinateur dans la trame de version."""
    model_id: int
    family: Family
    air_integration: bool = False
    """Vrai si le modele enregistre la pression du bloc."""

    @property
    def label(self) -> str:
        return f"Mares {self.name}"

    @property
    def fingerprint_size(self) -> int:
        return 4 if self.family is Family.GENIUS else 10


#: Tous les modeles reconnus, indexes par le nom exact de la trame de version.
#:
#: Le nom est compare en entier: en simple prefixe, « Quad » capturerait aussi
#: « Quad Ci » et « Quad2 », qui n'ont ni la meme geometrie d'entete ni le meme
#: protocole.
MODELS: dict[str, ModelSpec] = {
    spec.name: spec
    for spec in (
        # -- famille IconHD: lecture de flash
        ModelSpec("Matrix", MATRIX, Family.ICONHD),
        ModelSpec("Icon HD", ICONHD, Family.ICONHD),
        ModelSpec("Icon AIR", ICONHDNET, Family.ICONHD, air_integration=True),
        ModelSpec("Puck Pro", PUCKPRO, Family.ICONHD),
        ModelSpec("Nemo Wide 2", NEMOWIDE2, Family.ICONHD),
        ModelSpec("Puck 2", PUCK2, Family.ICONHD),
        ModelSpec("Quad Air", QUADAIR, Family.ICONHD, air_integration=True),
        ModelSpec("Quad", QUAD, Family.ICONHD),
        # -- famille Smart: lecture de flash, entete organisee autrement
        ModelSpec("Smart", SMART, Family.SMART),
        ModelSpec("Smart Apnea", SMARTAPNEA, Family.SMART),
        ModelSpec("Smart Air", SMARTAIR, Family.SMART, air_integration=True),
        # -- famille Genius / Sirius: protocole par objets
        ModelSpec("Genius", GENIUS, Family.GENIUS, air_integration=True),
        ModelSpec("Horizon", HORIZON, Family.GENIUS, air_integration=True),
        ModelSpec("Puck Air 2", PUCKAIR2, Family.GENIUS, air_integration=True),
        ModelSpec("Sirius", SIRIUS, Family.GENIUS, air_integration=True),
        ModelSpec("Sirius L", SIRIUS_L, Family.GENIUS, air_integration=True),
        ModelSpec("Quad Ci", QUADCI, Family.GENIUS, air_integration=True),
        ModelSpec("Quad2", QUAD2, Family.GENIUS, air_integration=True),
        ModelSpec("Puck4", PUCK4, Family.GENIUS, air_integration=True),
        ModelSpec("Puck Lite", PUCK4, Family.GENIUS, air_integration=True),
        ModelSpec("Puck", PUCK4, Family.GENIUS, air_integration=True),
        ModelSpec("Puck Pro U", PUCK4, Family.GENIUS, air_integration=True),
    )
}

#: Table inverse, pour retrouver la famille a partir d'un identifiant.
SPECS_BY_ID: dict[int, ModelSpec] = {}
for _spec in MODELS.values():
    SPECS_BY_ID.setdefault(_spec.model_id, _spec)

MODEL_NAMES: dict[str, int] = {name: spec.model_id for name, spec in MODELS.items()}
SUPPORTED_MODELS = set(SPECS_BY_ID)

SMART_FAMILY = {SMART, SMARTAPNEA, SMARTAIR}
GENIUS_FAMILY = {
    GENIUS,
    HORIZON,
    PUCKAIR2,
    SIRIUS,
    SIRIUS_L,
    QUADCI,
    QUAD2,
    PUCK4,
}


def family_of(model_id: int) -> Family:
    """Famille de protocole d'un identifiant modele."""
    if model_id in GENIUS_FAMILY:
        return Family.GENIUS
    if model_id in SMART_FAMILY:
        return Family.SMART
    return Family.ICONHD


def model_label(model_id: int) -> str:
    spec = SPECS_BY_ID.get(model_id)
    return spec.name if spec else f"0x{model_id:X}"


class ProtocolError(IOError):
    """Reponse inattendue de l'ordinateur de plongee."""


class UnsupportedModelError(ProtocolError):
    """Modele identifie mais dont le format n'est pas gere."""


def _u16(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset : offset + 2], "little")


def _u32(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset : offset + 4], "little")


def _u32be(data: bytes, offset: int = 0) -> int:
    return int.from_bytes(data[offset : offset + 4], "big")


def crc16_ccitt(data: bytes, init: int = 0x0000, xorout: int = 0x0000) -> int:
    """CRC-16/XMODEM, celui qui protege les enregistrements Genius."""
    crc = init
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc ^ xorout


# -- geometrie des enregistrements a memoire flash --------------------------


@dataclass(frozen=True)
class Geometry:
    """Dimensions d'un enregistrement de plongee en memoire flash."""

    header_size: int
    sample_size: int
    fingerprint_offset: int
    """Position de l'empreinte, relative au debut du bloc d'entete."""
    fields_offset: int
    """Position des champs decodables, relative au debut du bloc d'entete.

    La famille IconHD place `[type][nb_echantillons]` en tete du bloc, les
    champs commencent donc 4 octets plus loin. La famille Smart place ce
    couple a la fin: les champs commencent des le premier octet.
    """


def probe_size(model_id: int) -> int:
    """Nombre d'octets a lire en premier pour connaitre la taille reelle.

    C'est la partie de l'entete qui porte le type de plongee et le nombre
    d'echantillons; elle suffit a calculer tout le reste.
    """
    if model_id == ICONHDNET:
        return 0x80
    if model_id == QUADAIR:
        return 0x84
    if model_id in (SMART, SMARTAIR):
        return 4
    if model_id == SMARTAPNEA:
        return 6
    return 0x5C


def read_type_and_samples(header: bytes, model_id: int) -> tuple[int, int]:
    """Lit `(type, nb_echantillons)` dans les premiers octets sondes.

    Les deux champs sont intervertis sur la famille Smart.
    """
    if model_id in SMART_FAMILY:
        return _u16(header, 2), _u16(header, 0)
    return _u16(header, 0), _u16(header, 2)


def dive_geometry(model_id: int, mode: int) -> Geometry:
    """Geometrie d'un enregistrement, selon le modele et le mode de plongee."""
    freedive = mode == 3
    if model_id == ICONHDNET:
        return Geometry(0x80, 12, 6, 4)
    if model_id == QUADAIR:
        return Geometry(0x84, 12, 6, 4)
    if model_id == SMART:
        if freedive:
            return Geometry(0x2E, 6, 0x20, 0)
        return Geometry(0x5C, 8, 2, 0)
    if model_id == SMARTAIR:
        if freedive:
            return Geometry(0x30, 6, 0x22, 0)
        return Geometry(0x84, 12, 2, 0)
    if model_id == SMARTAPNEA:
        return Geometry(0x50, 14, 0x40, 0)
    return Geometry(0x5C, 8, 6, 4)


def record_size(
    model_id: int, geometry: Geometry, nsamples: int, header_block: bytes
) -> int:
    """Taille totale d'un enregistrement, extras compris."""
    nbytes = 4 + geometry.header_size + nsamples * geometry.sample_size
    if model_id in (ICONHDNET, QUADAIR) or (
        model_id == SMARTAIR and geometry.sample_size == 12
    ):
        # Un bloc de pression est intercale tous les quatre echantillons.
        nbytes += (nsamples // 4) * 8
    elif model_id == SMARTAPNEA:
        settings = _u16(header_block, 0x1C)
        divetime = _u32(header_block, 0x24)
        samplerate = 1 << ((settings >> 9) & 0x03)
        nbytes += divetime * samplerate * 2
    return nbytes


class MaresDevice:
    """Pilote d'un ordinateur Mares, au-dessus d'un transport serie."""

    def __init__(
        self,
        transport: SerialTransport,
        *,
        retries: int = MAX_RETRIES,
        retry_delay: float = 1.0,
        force_model: str = "",
        packet_size: int = 0,
    ) -> None:
        self.transport = transport
        self.retries = max(0, retries)
        self.retry_delay = max(0.0, retry_delay)
        self.force_model = force_model
        self.forced_packet_size = packet_size
        self.version: bytes = b""
        self.model_id: int = 0
        self.model_name: str = ""
        self.spec: ModelSpec | None = None
        self.serial: str = ""
        self.memory_size: int = 0
        self.packet_size: int = 256
        self.layout: MemoryLayout = LAYOUT_ICONHD

    @property
    def family(self) -> Family:
        return self.spec.family if self.spec else Family.ICONHD

    # -- connexion ----------------------------------------------------------

    def connect(self) -> DeviceInfo:
        """Ouvre le port, identifie l'ordinateur et choisit le plan memoire."""
        self.transport.open()
        self.transport.purge()

        self.version = self._transfer(CMD_VERSION, b"", VERSION_SIZE)
        log.debug("Version: %s", self.version.hex())
        detected, spec = self._detect_model(self.version)

        if self.force_model:
            forced = MODELS.get(self.force_model)
            if forced is None:
                raise ProtocolError(
                    T("Modèle forcé inconnu : {name}.").format(name=self.force_model)
                    + " "
                    + T("Modèles connus :")
                    + " "
                    + ", ".join(sorted(MODELS))
                )
            if spec is not None and spec.name != forced.name:
                log.warning(
                    "Modele force a %s alors que l'ordinateur annonce %s.",
                    forced.name,
                    spec.name,
                )
            spec = forced
            detected = detected or forced.name

        if spec is None:
            raise ProtocolError(
                T(
                    "Modèle Mares non reconnu (nom lu : {name}). Vous pouvez "
                    "forcer un modèle dans les paramètres si vous savez lequel "
                    "c'est."
                ).format(name=detected or "?")
            )

        self.spec = spec
        self.model_name = spec.name
        self.model_id = spec.model_id

        if spec.family is Family.GENIUS:
            self.layout = LAYOUT_GENIUS
            self.packet_size = self.forced_packet_size or 4096
            self.serial = self._read_object_serial()
        else:
            # Le Quad existe en deux tailles de flash: on interroge la puce.
            if self.model_id == QUAD:
                try:
                    self.memory_size = _u32(self._transfer(CMD_FLASHSIZE, b"", 4))
                except (ProtocolError, TimeoutError, TransportError) as exc:
                    log.warning("Taille de flash illisible (%s), on suppose 1 Mo.", exc)
                    self.memory_size = LAYOUT_ICONHD.memsize
            self.layout, packet = self._select_layout(self.model_id, self.memory_size)
            self.packet_size = self.forced_packet_size or packet
            if not self.memory_size:
                self.memory_size = self.layout.memsize
            self.serial = str(_u32(self.read(SERIAL_ADDRESS, 4)))

        return DeviceInfo(
            model_id=self.model_id,
            model_name=self.model_name,
            serial=self.serial,
            memory_size=self.memory_size,
            version_raw=self.version,
        )

    def close(self) -> None:
        self.transport.close()

    def __enter__(self) -> MaresDevice:
        self.connect()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @staticmethod
    def _detect_model(version: bytes) -> tuple[str, ModelSpec | None]:
        """Lit le nom de produit dans la trame de version et le resout."""
        raw = version[MODEL_NAME_OFFSET : MODEL_NAME_OFFSET + MODEL_NAME_SIZE]
        name = raw.split(b"\x00")[0].decode("ascii", "replace").strip()
        return name, MODELS.get(name)

    @staticmethod
    def _select_layout(model_id: int, memory_size: int) -> tuple[MemoryLayout, int]:
        if model_id == MATRIX:
            return LAYOUT_MATRIX, 256
        if model_id in (PUCKPRO, PUCK2, NEMOWIDE2, SMART, SMARTAPNEA):
            return LAYOUT_NEMOWIDE2, 256
        if model_id == QUAD:
            layout = LAYOUT_ICONHD if memory_size > 0x40000 else LAYOUT_NEMOWIDE2
            return layout, 256
        if model_id in (QUADAIR, SMARTAIR):
            return LAYOUT_ICONHDNET, 256
        if model_id == ICONHDNET:
            return LAYOUT_ICONHDNET, 4096
        return LAYOUT_ICONHD, 4096

    # -- trames -------------------------------------------------------------

    def _packet(self, cmd: int, payload: bytes, answer_size: int) -> bytes:
        self.transport.write(bytes((cmd, cmd ^ XOR)))

        # L'ordinateur acquitte l'entete avant d'accepter la charge utile.
        while True:
            header = self.transport.read(1)[0]
            if header == ACK:
                break
            log.warning("Octet d'entete inattendu (0x%02X), on continue.", header)

        if payload:
            self.transport.write(payload)

        answer = self.transport.read(answer_size) if answer_size else b""

        trailer = self.transport.read(1)[0]
        if trailer != END:
            raise ProtocolError(f"Fin de trame inattendue (0x{trailer:02X}).")
        return answer

    def _transfer(self, cmd: int, payload: bytes, answer_size: int) -> bytes:
        """Envoie une commande, avec reprise sur trame corrompue."""
        last: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                return self._packet(cmd, payload, answer_size)
            except (ProtocolError, TimeoutError) as exc:
                last = exc
                if attempt == self.retries:
                    break
                log.warning(
                    "Commande 0x%02X en echec (%s), tentative %d/%d.",
                    cmd,
                    exc,
                    attempt + 2,
                    self.retries + 1,
                )
                if self.retry_delay:
                    self.transport.sleep(self.retry_delay)
                self.transport.purge()
        raise TransportError(
            f"Commande 0x{cmd:02X} en echec apres {self.retries + 1} tentatives: {last}"
        ) from last

    # -- lecture memoire (familles IconHD et Smart) -------------------------

    def read(self, address: int, size: int) -> bytes:
        """Lit `size` octets a partir de `address`, en decoupant en paquets."""
        out = bytearray()
        remaining = size
        while remaining > 0:
            chunk = min(remaining, self.packet_size)
            command = address.to_bytes(4, "little") + chunk.to_bytes(4, "little")
            out += self._transfer(CMD_READ, command, chunk)
            address += chunk
            remaining -= chunk
        return bytes(out)

    def dump_memory(self, progress: Callable[[int, int], None] | None = None) -> bytes:
        """Recopie toute la memoire flash (utile pour deboguer un format)."""
        if self.family is Family.GENIUS:
            raise UnsupportedModelError(
                T(
                    "Le Mares {model} n'expose pas sa mémoire flash : ce modèle "
                    "communique par objets, il n'y a rien à recopier."
                ).format(model=self.model_name)
            )
        total = self.layout.memsize
        out = bytearray()
        while len(out) < total:
            chunk = min(self.packet_size, total - len(out))
            out += self.read(len(out), chunk)
            if progress:
                progress(len(out), total)
        return bytes(out)

    def set_time(self, when) -> None:
        """Met l'ordinateur a l'heure (heure locale)."""
        import calendar

        ticks = calendar.timegm(when.timetuple())
        self._transfer(CMD_SET_TIME, int(ticks).to_bytes(4, "little"), 0)

    # -- protocole par objets (famille Genius) ------------------------------

    def read_object(self, index: int, subindex: int) -> bytes:
        """Lit un objet complet, en recollant ses segments."""
        command = bytes(
            (0x40, index & 0xFF, (index >> 8) & 0xFF, subindex & 0xFF)
        ) + bytes(12)
        answer = self._transfer(CMD_OBJ_INIT, command, 16)

        if answer[1:4] != command[1:4]:
            raise ProtocolError(
                f"L'objet renvoye ({answer[1:4].hex()}) n'est pas celui demande "
                f"({command[1:4].hex()})."
            )

        buffer = bytearray()
        if answer[0] == 0x41:
            # Charge utile longue: la premiere trame n'annonce que sa taille.
            size = _u32(answer, 4)
        elif answer[0] == 0x42:
            # Charge utile courte: elle tient dans la trame d'ouverture.
            buffer += answer[4:16]
            size = len(buffer)
        else:
            raise ProtocolError(f"Type de trame d'objet inattendu (0x{answer[0]:02X}).")

        packets = 0
        while len(buffer) < size:
            toggle = packets % 2
            cmd = CMD_OBJ_EVEN if toggle == 0 else CMD_OBJ_ODD
            length = min(size - len(buffer), OBJECT_PACKET_SIZE)
            segment = self._transfer(cmd, b"", length + 1)
            if (segment[0] & 0xF0) >> 4 != toggle:
                raise ProtocolError(
                    f"Segment d'objet hors sequence (0x{segment[0]:02X})."
                )
            buffer += segment[1:]
            packets += 1
        return bytes(buffer)

    def _read_object_serial(self) -> str:
        """Numero de serie d'un modele Genius: six chiffres ASCII."""
        raw = self.read_object(OBJ_DEVICE, OBJ_DEVICE_SERIAL)
        if len(raw) < 16:
            raise ProtocolError(
                f"Numero de serie tronque ({len(raw)} octets au lieu de 16)."
            )
        text = raw[10:16].decode("ascii", "ignore").strip()
        digits = "".join(c for c in text if c.isdigit())
        return str(int(digits)) if digits else text or "0"

    def dive_count(self) -> int:
        """Nombre de plongees en memoire (famille Genius)."""
        raw = self.read_object(OBJ_LOGBOOK, OBJ_LOGBOOK_COUNT)
        if len(raw) < 2:
            raise ProtocolError("Nombre de plongees illisible.")
        return _u16(raw, 0)

    # -- parcours des plongees ----------------------------------------------

    def iter_raw_dives(
        self,
        fingerprint: bytes | None = None,
        limit: int | None = None,
        progress: Callable[[int, int | None], None] | None = None,
    ) -> Iterator[bytes]:
        """Parcourt les plongees de la plus recente a la plus ancienne.

        Args:
            fingerprint: empreinte de la derniere plongee deja importee. Le
                parcours s'arrete des qu'elle est rencontree.
            limit: nombre maximum de plongees a renvoyer.
            progress: rappel `(plongees_lues, limite)`.
        """
        if self.family is Family.GENIUS:
            yield from self._iter_object_dives(fingerprint, limit, progress)
        else:
            yield from self._iter_flash_dives(fingerprint, limit, progress)

    def _iter_object_dives(
        self,
        fingerprint: bytes | None,
        limit: int | None,
        progress: Callable[[int, int | None], None] | None,
    ) -> Iterator[bytes]:
        """Famille Genius: les plongees se demandent objet par objet."""
        total = self.dive_count()
        log.info("%d plongee(s) annoncee(s) par l'ordinateur.", total)
        count = 0
        for index in range(total):
            header = self.read_object(OBJ_DIVE + index, OBJ_DIVE_HEADER)
            if len(header) < 12:
                log.warning("Entete de plongee %d trop courte, arret.", index)
                break
            if fingerprint and header[0x08 : 0x08 + len(fingerprint)] == fingerprint:
                log.debug("Empreinte connue atteinte, arret de l'import.")
                break
            body = self.read_object(OBJ_DIVE + index, OBJ_DIVE_DATA)
            count += 1
            yield header + body
            if progress:
                progress(count, limit if limit is not None else total)
            if limit is not None and count >= limit:
                break

    def _iter_flash_dives(
        self,
        fingerprint: bytes | None,
        limit: int | None,
        progress: Callable[[int, int | None], None] | None,
    ) -> Iterator[bytes]:
        """Familles IconHD et Smart: parcours du buffer circulaire."""
        eop = self._read_eop()
        if eop is None:
            return

        reader = _RingBufferReader(
            self,
            self.layout.profile_begin,
            self.layout.profile_end,
            eop,
            self.packet_size,
        )

        probe = probe_size(self.model_id)
        offset = reader.total
        count = 0
        while offset >= probe + 4:
            try:
                head = reader.read(probe)
            except EOFError:
                break

            dive_type, nsamples = read_type_and_samples(head, self.model_id)
            if dive_type == 0xFFFF or nsamples == 0xFFFF:
                break  # zone de memoire jamais ecrite

            geometry = dive_geometry(self.model_id, dive_type & 0x03)
            if offset < geometry.header_size:
                break
            if geometry.header_size > probe:
                try:
                    head = reader.read(geometry.header_size - probe) + head
                except EOFError:
                    break

            nbytes = record_size(self.model_id, geometry, nsamples, head)
            if offset < nbytes:
                break  # plongee tronquee par le bouclage du buffer

            try:
                body = reader.read(nbytes - geometry.header_size)
            except EOFError:
                break

            record = body + head
            offset -= nbytes

            if _u32(record) != nbytes:
                log.debug(
                    "Taille annoncee (%d) != calculee (%d), fin du parcours.",
                    _u32(record),
                    nbytes,
                )
                break

            if fingerprint:
                start = len(record) - geometry.header_size + geometry.fingerprint_offset
                if record[start : start + len(fingerprint)] == fingerprint:
                    log.debug("Empreinte connue atteinte, arret de l'import.")
                    break

            count += 1
            yield record
            if progress:
                progress(count, limit)
            if limit is not None and count >= limit:
                break

    def _read_eop(self) -> int | None:
        """Lit le pointeur de fin du buffer circulaire des profils."""
        eop = 0
        for address in EOP_POINTERS:
            eop = _u32(self.read(address, 4))
            if self.layout.profile_begin <= eop < self.layout.profile_end:
                return eop
            if eop == 0xFFFFFFFF:
                return None  # memoire vierge: aucune plongee
        raise ProtocolError(f"Pointeur de buffer circulaire hors bornes (0x{eop:08X}).")


#: Ancien nom de la classe, conserve pour ne pas casser le code existant.
MaresIconHD = MaresDevice


class _RingBufferReader:
    """Lecture a reculons d'un buffer circulaire en memoire flash.

    Les paquets sont recuperes a la demande: importer les dernieres plongees
    ne lit donc que quelques kilo-octets, pas la flash entiere.
    """

    def __init__(
        self, device: MaresDevice, begin: int, end: int, eop: int, packet_size: int
    ) -> None:
        self.device = device
        self.begin = begin
        self.end = end
        self.total = end - begin
        self.address = eop
        self.packet_size = packet_size
        self.remaining = self.total
        self._buffer = bytearray()

    def read(self, size: int) -> bytes:
        """Renvoie les `size` octets qui precedent la position courante."""
        while len(self._buffer) < size:
            self._fetch()
        cut = len(self._buffer) - size
        out = bytes(self._buffer[cut:])
        del self._buffer[cut:]
        return out

    def _fetch(self) -> None:
        if self.remaining <= 0:
            raise EOFError("Debut du buffer circulaire atteint.")
        size = min(self.packet_size, self.remaining)
        before_begin = self.address - self.begin
        if size <= before_begin:
            chunk = self.device.read(self.address - size, size)
            self.address -= size
        else:
            # Le bloc chevauche le debut: la fin du buffer le precede.
            head = self.device.read(self.begin, before_begin)
            tail_size = size - before_begin
            tail = self.device.read(self.end - tail_size, tail_size)
            chunk = tail + head
            self.address = self.end - tail_size
        self._buffer[:0] = chunk
        self.remaining -= size
