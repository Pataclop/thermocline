"""Couche transport: liaison serie USB vers l'ordinateur de plongee.

Le cable Mares (clip USB) expose un convertisseur USB-serie: FTDI sur les
cables d'origine, CP210x, PL2303 ou CH340 sur les compatibles. On repere donc
un port candidat via son VID/PID, puis on parle le protocole Mares dessus.

Rien n'est fige: la vitesse, le temps d'attente et l'etat des lignes DTR/RTS
viennent des reglages, parce qu'un cable bon marche ou un concentrateur USB
capricieux demande parfois autre chose que les valeurs d'origine.
"""

from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass

import serial
from serial.tools import list_ports

from .i18n import T

log = logging.getLogger(__name__)

#: Convertisseurs USB-serie couramment utilises par les cables Mares.
KNOWN_USB_IDS: dict[tuple[int, int], str] = {
    (0x0403, 0x6001): "FTDI FT232 (câble Mares d'origine)",
    (0x0403, 0x6010): "FTDI FT2232",
    (0x0403, 0x6011): "FTDI FT4232",
    (0x0403, 0x6014): "FTDI FT232H",
    (0x0403, 0x6015): "FTDI FT231X",
    (0x10C4, 0xEA60): "Silicon Labs CP210x",
    (0x10C4, 0xEA70): "Silicon Labs CP2105",
    (0x067B, 0x2303): "Prolific PL2303",
    (0x067B, 0x23A3): "Prolific PL2303GC",
    (0x1A86, 0x7522): "QinHeng CH340",
    (0x1A86, 0x7523): "QinHeng CH340",
    (0x1A86, 0x5523): "QinHeng CH341",
    (0x1A86, 0x55D3): "QinHeng CH343",
    (0x1A86, 0x55D4): "QinHeng CH9102",
    (0x2341, 0x0043): "Puce série compatible",
}

KNOWN_VENDORS = {0x0403, 0x10C4, 0x067B, 0x1A86}


@dataclass
class SerialPortInfo:
    """Un port serie candidat, avec de quoi l'afficher dans l'interface."""

    device: str
    description: str
    vid: int | None = None
    pid: int | None = None
    serial_number: str | None = None
    likely: bool = False

    @property
    def hint(self) -> str:
        """Nom lisible du convertisseur, a defaut la description du pilote."""
        return T(KNOWN_USB_IDS.get((self.vid or -1, self.pid or -1), self.description))

    @property
    def label(self) -> str:
        mark = "* " if self.likely else "  "
        return f"{mark}{self.device} - {self.hint}"


def list_serial_ports() -> list[SerialPortInfo]:
    """Liste les ports serie, les candidats probables en premier."""
    found: list[SerialPortInfo] = []
    try:
        ports = list(list_ports.comports())
    except Exception as exc:  # noqa: BLE001 - pilote serie fantaisiste
        log.warning("Énumération des ports série impossible : %s", exc)
        return []
    for port in ports:
        info = SerialPortInfo(
            device=port.device,
            description=port.description or T("port série"),
            vid=port.vid,
            pid=port.pid,
            serial_number=port.serial_number,
            likely=(port.vid in KNOWN_VENDORS) if port.vid else False,
        )
        found.append(info)
    found.sort(key=lambda p: (not p.likely, p.device))
    return found


def autodetect_port() -> str | None:
    """Renvoie le premier port serie qui ressemble a un cable Mares."""
    ports = list_serial_ports()
    for port in ports:
        if (port.vid, port.pid) in KNOWN_USB_IDS:
            return port.device
    for port in ports:
        if port.likely:
            return port.device
    return ports[0].device if len(ports) == 1 else None


def permission_hint() -> str:
    """Conseil adapte au systeme quand le port refuse de s'ouvrir."""
    if sys.platform.startswith("linux"):
        return T(
            "Sous Linux, l'accès aux ports série demande d'appartenir au groupe "
            "« dialout » : sudo usermod -aG dialout $USER, puis rouvrez votre "
            "session."
        )
    if sys.platform == "darwin":
        return T(
            "Sous macOS, installez le pilote du convertisseur (CP210x ou CH340 "
            "selon le câble) et autorisez-le dans Réglages Système › "
            "Confidentialité et sécurité."
        )
    return T(
        "Sous Windows, vérifiez dans le Gestionnaire de périphériques que le "
        "convertisseur USB-série apparaît sans point d'exclamation, et qu'aucun "
        "autre logiciel (Mares Dive Organizer, Subsurface…) ne tient le port."
    )


class TransportError(IOError):
    """Erreur de communication bas niveau (port, timeout, cable)."""


class SerialTransport:
    """Liaison serie configuree pour les ordinateurs Mares: 115200 8E1.

    Les lignes DTR et RTS doivent rester relachees, sinon l'ordinateur ne
    repond pas (comportement repris de libdivecomputer).
    """

    BAUDRATE = 115200
    TIMEOUT = 3.0

    def __init__(
        self,
        port: str,
        timeout: float | None = None,
        *,
        baudrate: int | None = None,
        dtr: bool = False,
        rts: bool = False,
        open_delay: float = 0.1,
    ) -> None:
        self.port = port
        self.timeout = timeout if timeout is not None else self.TIMEOUT
        self.baudrate = baudrate or self.BAUDRATE
        self.dtr = dtr
        self.rts = rts
        self.open_delay = max(0.0, open_delay)
        self._ser: serial.Serial | None = None

    @classmethod
    def from_settings(cls, port: str, settings) -> "SerialTransport":
        """Construit la liaison a partir des preferences de l'utilisateur."""
        return cls(
            port,
            timeout=settings.timeout,
            baudrate=settings.baudrate,
            dtr=settings.dtr,
            rts=settings.rts,
            open_delay=settings.open_delay,
        )

    # -- cycle de vie -------------------------------------------------------

    def open(self) -> None:
        if self._ser is not None:
            return
        try:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_EVEN,
                stopbits=serial.STOPBITS_ONE,
                timeout=self.timeout,
                write_timeout=self.timeout,
                rtscts=False,
                dsrdtr=False,
                xonxoff=False,
            )
        except serial.SerialException as exc:
            raise TransportError(
                T("Ouverture de {port} impossible : {error}").format(
                    port=self.port, error=exc
                )
                + "\n\n"
                + permission_hint()
            ) from exc

        try:
            self._ser.dtr = self.dtr
            self._ser.rts = self.rts
        except (OSError, serial.SerialException) as exc:  # pragma: no cover
            # Certains pilotes refusent de piloter ces lignes: ce n'est pas
            # bloquant, l'ordinateur repond generalement quand meme.
            log.warning("Lignes DTR/RTS non modifiables (%s).", exc)
        if self.open_delay:
            time.sleep(self.open_delay)
        self.purge()

    def close(self) -> None:
        if self._ser is not None:
            try:
                self._ser.close()
            finally:
                self._ser = None

    def __enter__(self) -> "SerialTransport":
        self.open()
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # -- entrees / sorties --------------------------------------------------

    @property
    def _port(self) -> serial.Serial:
        if self._ser is None:
            raise TransportError(T("Le port série n'est pas ouvert."))
        return self._ser

    def purge(self) -> None:
        """Vide les tampons d'entree et de sortie."""
        try:
            self._port.reset_input_buffer()
            self._port.reset_output_buffer()
        except serial.SerialException:  # pragma: no cover - depend du pilote
            pass

    def write(self, data: bytes) -> None:
        try:
            written = self._port.write(data)
        except serial.SerialException as exc:
            raise TransportError(
                T("Écriture sur {port} impossible : {error}").format(
                    port=self.port, error=exc
                )
            ) from exc
        if written != len(data):
            raise TransportError(
                T("Écriture partielle ({written}/{total} octets).").format(
                    written=written, total=len(data)
                )
            )
        self._port.flush()

    def read(self, size: int) -> bytes:
        """Lit exactement `size` octets, sinon leve une erreur de timeout."""
        chunks: list[bytes] = []
        remaining = size
        while remaining > 0:
            try:
                chunk = self._port.read(remaining)
            except serial.SerialException as exc:
                raise TransportError(
                    T("Lecture sur {port} interrompue : {error}").format(
                        port=self.port, error=exc
                    )
                ) from exc
            if not chunk:
                got = size - remaining
                raise TimeoutError(
                    T(
                        "Délai dépassé : {got}/{size} octets reçus depuis {port}."
                    ).format(got=got, size=size, port=self.port)
                )
            chunks.append(chunk)
            remaining -= len(chunk)
        return b"".join(chunks)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)
