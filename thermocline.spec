# -*- mode: python ; coding: utf-8 -*-
"""Recette PyInstaller, commune aux trois systemes.

    pyinstaller thermocline.spec --noconfirm

Un seul fichier sous Windows et Linux, un paquet `.app` sous macOS: c'est ce
que chaque systeme attend, et c'est ce qui demande le moins d'explications a
l'utilisateur.
"""

import sys
from pathlib import Path

ROOT = Path(SPECPATH)
RESOURCES = ROOT / "thermocline" / "resources"

WINDOWS = sys.platform.startswith("win")
MACOS = sys.platform == "darwin"

icon = None
if WINDOWS and (RESOURCES / "thermocline.ico").exists():
    icon = str(RESOURCES / "thermocline.ico")
elif MACOS and (RESOURCES / "thermocline.icns").exists():
    icon = str(RESOURCES / "thermocline.icns")

# Qt embarque beaucoup de choses dont un carnet de plongee n'a pas l'usage.
# Les ecarter divise la taille du binaire par deux environ.
EXCLUDES = [
    "tkinter",
    "PyQt5",
    "PySide2",
    "PySide6",
    "matplotlib",
    "pandas",
    "scipy",
    "IPython",
    "pytest",
    "setuptools",
    "PyQt6.QtWebEngineCore",
    "PyQt6.QtWebEngineWidgets",
    "PyQt6.QtQuick",
    "PyQt6.QtQml",
    "PyQt6.Qt3DCore",
    "PyQt6.QtMultimedia",
    "PyQt6.QtBluetooth",
    "PyQt6.QtNetworkAuth",
    "PyQt6.QtPositioning",
    "PyQt6.QtSensors",
    "PyQt6.QtSerialPort",
    "PyQt6.QtDesigner",
    "PyQt6.QtHelp",
    "PyQt6.QtTest",
]

analysis = Analysis(
    ["run.py"],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[(str(RESOURCES), "thermocline/resources")],
    hiddenimports=["thermocline.translations"],
    hookspath=[],
    runtime_hooks=[],
    excludes=EXCLUDES,
    noarchive=False,
)

pyz = PYZ(analysis.pure)

if MACOS:
    # macOS veut un dossier .app: l'executable seul ne recoit pas les
    # evenements du systeme et ne peut pas porter d'icone.
    executable = EXE(
        pyz,
        analysis.scripts,
        [],
        exclude_binaries=True,
        name="Thermocline",
        console=False,
        icon=icon,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
    )
    collection = COLLECT(
        executable,
        analysis.binaries,
        analysis.datas,
        strip=False,
        upx=False,
        name="Thermocline",
    )
    app = BUNDLE(
        collection,
        name="Thermocline.app",
        icon=icon,
        bundle_identifier="fr.pataclop.thermocline",
        info_plist={
            "CFBundleDisplayName": "Thermocline",
            "CFBundleShortVersionString": "1.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
            "NSHumanReadableCopyright": "LGPL-2.1-or-later",
        },
    )
else:
    executable = EXE(
        pyz,
        analysis.scripts,
        analysis.binaries,
        analysis.datas,
        [],
        name="Thermocline",
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=False,
        runtime_tmpdir=None,
        console=False,
        disable_windowed_traceback=False,
        icon=icon,
    )
