"""Interface graphique PyQt6.

PyQt5 et PyQt6 peuvent cohabiter sur la machine: on force explicitement
pyqtgraph sur PyQt6 avant tout import, sinon il choisit la premiere liaison
Qt qu'il trouve.
"""

from __future__ import annotations

import os

os.environ.setdefault("PYQTGRAPH_QT_LIB", "PyQt6")
