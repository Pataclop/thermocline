"""Fabrique l'executable de l'application pour le systeme courant.

    python tools/build.py

PyInstaller ne sait pas compiler pour un autre systeme que celui sur lequel il
tourne: un binaire macOS se fabrique sur macOS, un binaire Linux sur Linux.
C'est le role du workflow `.github/workflows/release.yml`, qui lance ce meme
script sur les trois systemes.

Le resultat est range dans `dist/`, puis compresse sous un nom qui dit tout de
suite a quoi il correspond, par exemple `Thermocline-1.1.0-windows-x86_64.zip`.
"""

from __future__ import annotations

import argparse
import platform
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from thermocline import __version__  # noqa: E402

DIST = ROOT / "dist"
BUILD = ROOT / "build"
RESOURCES = ROOT / "thermocline" / "resources"


def platform_tag() -> str:
    """`windows-x86_64`, `macos-arm64`, `linux-x86_64`..."""
    system = {"win32": "windows", "darwin": "macos"}.get(sys.platform, "linux")
    machine = platform.machine().lower()
    machine = {"amd64": "x86_64", "x86_64": "x86_64", "arm64": "arm64"}.get(
        machine, machine
    )
    return f"{system}-{machine}"


def make_icns() -> None:
    """Convertit le PNG en icone macOS, avec l'outil du systeme."""
    png = RESOURCES / "thermocline.png"
    icns = RESOURCES / "thermocline.icns"
    if sys.platform != "darwin" or not png.exists() or icns.exists():
        return
    if shutil.which("iconutil") is None or shutil.which("sips") is None:
        print("iconutil introuvable : l'application n'aura pas d'icône.")
        return

    iconset = RESOURCES / "thermocline.iconset"
    iconset.mkdir(exist_ok=True)
    for size in (16, 32, 64, 128, 256, 512):
        for scale, suffix in ((1, ""), (2, "@2x")):
            target = iconset / f"icon_{size}x{size}{suffix}.png"
            subprocess.run(
                ["sips", "-z", str(size * scale), str(size * scale), str(png),
                 "--out", str(target)],
                check=True,
                capture_output=True,
            )
    subprocess.run(
        ["iconutil", "-c", "icns", str(iconset), "-o", str(icns)], check=True
    )
    shutil.rmtree(iconset, ignore_errors=True)
    print(f"  icône macOS : {icns.relative_to(ROOT)}")


def ensure_icon() -> None:
    """Redessine l'icone si elle manque (Pillow n'est requis que pour cela)."""
    if (RESOURCES / "thermocline.png").exists():
        return
    try:
        subprocess.run([sys.executable, str(ROOT / "tools" / "make_icon.py")], check=True)
    except (subprocess.CalledProcessError, OSError) as exc:
        print(f"Icône non générée ({exc}) : l'application gardera l'icône par défaut.")


def archive(target: Path, tag: str) -> Path:
    """Compresse le resultat sous un nom lisible."""
    name = f"Thermocline-{__version__}-{tag}"
    if sys.platform == "darwin":
        # `ditto` preserve les liens symboliques et les droits du paquet .app,
        # ce qu'un zip ordinaire casse silencieusement.
        archive_path = DIST / f"{name}.zip"
        subprocess.run(
            ["ditto", "-c", "-k", "--sequesterRsrc", "--keepParent",
             str(target), str(archive_path)],
            check=True,
        )
        return archive_path

    archive_path = DIST / f"{name}.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as bundle:
        if target.is_dir():
            for path in sorted(target.rglob("*")):
                bundle.write(path, path.relative_to(target.parent))
        else:
            bundle.write(target, target.name)
        readme = ROOT / "README.md"
        if readme.exists():
            bundle.write(readme, "README.md")
    return archive_path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--clean", action="store_true", help="repart de zéro")
    parser.add_argument("--no-archive", action="store_true", help="pas de .zip")
    args = parser.parse_args()

    if args.clean:
        for folder in (DIST, BUILD):
            shutil.rmtree(folder, ignore_errors=True)

    ensure_icon()
    make_icns()

    print(f"Compilation de Thermocline {__version__} pour {platform_tag()}…")
    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "thermocline.spec", "--noconfirm"],
        cwd=ROOT,
    )
    if result.returncode != 0:
        return result.returncode

    produced = DIST / ("Thermocline.app" if sys.platform == "darwin" else "Thermocline")
    if sys.platform.startswith("win"):
        produced = DIST / "Thermocline.exe"
    if not produced.exists():
        print(f"Résultat introuvable : {produced}", file=sys.stderr)
        return 1
    print(f"  {produced.relative_to(ROOT)}")

    if not args.no_archive:
        bundle = archive(produced, platform_tag())
        size = bundle.stat().st_size / 1e6
        print(f"  {bundle.relative_to(ROOT)}  ({size:.1f} Mo)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
