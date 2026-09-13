"""Tests du carnet de plongee Mares Quad."""

import logging

# Les tests de reprise sur erreur journalisent volontairement des avertissements.
logging.getLogger("thermocline").setLevel(logging.CRITICAL)
