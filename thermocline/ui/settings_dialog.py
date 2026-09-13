"""Boite « Paramètres »: tout ce qui se regle une fois pour toutes.

Six volets, du plus courant au plus technique:

* **Interface** — langue, theme, police, comportement de la fenetre;
* **Ordinateur** — modele, port, vitesse et surtout les delais, qui sont ce
  qu'on touche quand un ordinateur repond mal ou pas du tout;
* **Bloc** — le bloc et les pressions qui servent de valeurs par defaut;
* **Analyse** — les seuils affiches par le carnet;
* **Données** — ou vivent la base et les exports;
* **Diagnostic** — versions, chemins et ports, a copier-coller pour demander
  de l'aide.

La boite travaille sur une copie des reglages: « Annuler » ne laisse rien
derriere lui.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from PyQt6 import QtGui, QtWidgets

from .. import config
from ..config import Settings
from ..device import MODELS, Family
from ..i18n import LANGUAGES, T
from ..simulator import DEMO_MODELS
from ..transport import list_serial_ports
from . import theme
from .workers import ProbeWorker

log = logging.getLogger(__name__)

#: Reglages qui ne prennent effet qu'au prochain demarrage.
RESTART_KEYS = ("language", "theme", "font_size")


class SettingsDialog(QtWidgets.QDialog):
    """Edite les preferences et signale ce qui demande un redemarrage."""

    def __init__(
        self, settings: Settings, parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.original = settings
        self.draft = settings.copy()
        self.probe: ProbeWorker | None = None
        self.needs_restart = False

        self.setWindowTitle(T("Paramètres"))
        self.resize(720, 620)
        self.setStyleSheet(theme.STYLESHEET)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._build_interface_tab(), T("Interface"))
        self.tabs.addTab(self._build_device_tab(), T("Ordinateur"))
        self.tabs.addTab(self._build_tank_tab(), T("Bloc"))
        self.tabs.addTab(self._build_analysis_tab(), T("Analyse"))
        self.tabs.addTab(self._build_data_tab(), T("Données"))
        self.tabs.addTab(self._build_diagnostic_tab(), T("Diagnostic"))

        reset = QtWidgets.QPushButton(T("Valeurs par défaut"))
        reset.setToolTip(T("Remet tous les réglages dans leur état d'origine"))
        reset.clicked.connect(self._restore_defaults)
        cancel = QtWidgets.QPushButton(T("Annuler"))
        cancel.clicked.connect(self.reject)
        save = QtWidgets.QPushButton(T("Enregistrer"))
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self._save)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(reset)
        buttons.addStretch(1)
        buttons.addWidget(cancel)
        buttons.addWidget(save)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(self.tabs, stretch=1)
        layout.addLayout(buttons)

        self._load(self.draft)

    # -- fabriques ----------------------------------------------------------

    @staticmethod
    def _page() -> tuple[QtWidgets.QWidget, QtWidgets.QFormLayout]:
        page = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(page)
        form.setContentsMargins(14, 14, 14, 14)
        form.setSpacing(9)
        form.setFieldGrowthPolicy(
            QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )
        return page, form

    @staticmethod
    def _hint(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("subtitle")
        label.setWordWrap(True)
        return label

    @staticmethod
    def _spin(
        minimum: float,
        maximum: float,
        suffix: str = "",
        decimals: int = 0,
        step: float = 1.0,
    ) -> QtWidgets.QAbstractSpinBox:
        if decimals:
            box: QtWidgets.QAbstractSpinBox = QtWidgets.QDoubleSpinBox()
            box.setDecimals(decimals)
            box.setRange(float(minimum), float(maximum))
            box.setSingleStep(float(step))
        else:
            # QSpinBox refuse les flottants, y compris pour son pas.
            box = QtWidgets.QSpinBox()
            box.setRange(int(minimum), int(maximum))
            box.setSingleStep(max(int(step), 1))
        if suffix:
            box.setSuffix(suffix)
        box.setMinimumWidth(130)
        return box

    # -- volet Interface ----------------------------------------------------

    def _build_interface_tab(self) -> QtWidgets.QWidget:
        page, form = self._page()

        self.language_combo = QtWidgets.QComboBox()
        self.language_combo.addItem(T("Comme le système"), "auto")
        for code, name in LANGUAGES.items():
            self.language_combo.addItem(name, code)
        form.addRow(T("Langue"), self.language_combo)

        self.theme_combo = QtWidgets.QComboBox()
        self.theme_combo.addItem(T("Sombre"), "dark")
        self.theme_combo.addItem(T("Clair"), "light")
        form.addRow(T("Thème"), self.theme_combo)

        self.font_spin = self._spin(7, 16, " pt")
        form.addRow(T("Taille du texte"), self.font_spin)

        self.tab_combo = QtWidgets.QComboBox()
        for index, name in enumerate(
            (
                T("Profil"),
                T("Analyse"),
                T("Oxygène et tissus"),
                T("Détails"),
                T("Statistiques"),
                T("Carnet"),
            )
        ):
            self.tab_combo.addItem(name, index)
        form.addRow(T("Onglet à l'ouverture"), self.tab_combo)

        self.geometry_check = QtWidgets.QCheckBox(
            T("Rouvrir la fenêtre à sa taille et à sa place")
        )
        form.addRow("", self.geometry_check)

        self.confirm_check = QtWidgets.QCheckBox(
            T("Demander confirmation avant de masquer une plongée")
        )
        form.addRow("", self.confirm_check)

        form.addRow(
            self._hint(
                T(
                    "La langue, le thème et la taille du texte s'appliquent au "
                    "prochain démarrage."
                )
            )
        )
        return page

    # -- volet Ordinateur ---------------------------------------------------

    def _build_device_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(page)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        connection = QtWidgets.QGroupBox(T("Connexion"))
        form = QtWidgets.QFormLayout(connection)
        form.setSpacing(9)

        self.model_combo = QtWidgets.QComboBox()
        self.model_combo.addItem(T("Détection automatique (recommandé)"), "")
        for name, spec in sorted(MODELS.items()):
            suffix = {
                Family.ICONHD: T("lecture mémoire"),
                Family.SMART: T("famille Smart"),
                Family.GENIUS: T("protocole par objets"),
            }[spec.family]
            self.model_combo.addItem(f"Mares {name} — {suffix}", name)
        self.model_combo.setToolTip(
            T(
                "À n'utiliser que si votre ordinateur n'est pas reconnu : forcer "
                "le mauvais modèle produit des plongées illisibles."
            )
        )
        form.addRow(T("Modèle"), self.model_combo)

        port_row = QtWidgets.QHBoxLayout()
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(260)
        refresh = QtWidgets.QPushButton(T("Rafraîchir"))
        refresh.clicked.connect(self._refresh_ports)
        port_row.addWidget(self.port_combo, stretch=1)
        port_row.addWidget(refresh)
        form.addRow(T("Port série"), port_row)

        self.remember_port_check = QtWidgets.QCheckBox(
            T("Retenir le dernier port utilisé")
        )
        form.addRow("", self.remember_port_check)

        outer.addWidget(connection)

        timings = QtWidgets.QGroupBox(T("Quand l'ordinateur répond mal"))
        tform = QtWidgets.QFormLayout(timings)
        tform.setSpacing(9)

        self.timeout_spin = self._spin(0.5, 30.0, " s", decimals=1, step=0.5)
        self.timeout_spin.setToolTip(
            T("Temps d'attente d'une réponse avant d'abandonner la commande")
        )
        tform.addRow(T("Délai d'attente"), self.timeout_spin)

        self.retries_spin = self._spin(0, 20)
        self.retries_spin.setToolTip(
            T("Nombre de reprises après une trame perdue ou corrompue")
        )
        tform.addRow(T("Tentatives supplémentaires"), self.retries_spin)

        self.retry_delay_spin = self._spin(0.0, 10.0, " s", decimals=1, step=0.5)
        tform.addRow(T("Pause entre deux tentatives"), self.retry_delay_spin)

        self.open_delay_spin = self._spin(0.0, 5.0, " s", decimals=1, step=0.1)
        self.open_delay_spin.setToolTip(
            T("Pause après l'ouverture du port, avant la première commande")
        )
        tform.addRow(T("Pause à l'ouverture"), self.open_delay_spin)

        self.packet_spin = self._spin(0, 8192, " o", step=128)
        self.packet_spin.setToolTip(
            T(
                "0 = taille conseillée pour le modèle détecté. La réduire aide "
                "sur les câbles capricieux et les concentrateurs USB."
            )
        )
        tform.addRow(T("Taille des paquets"), self.packet_spin)

        self.baud_combo = QtWidgets.QComboBox()
        for rate in (9600, 19200, 38400, 57600, 115200, 230400):
            self.baud_combo.addItem(str(rate), rate)
        tform.addRow(T("Vitesse"), self.baud_combo)

        lines = QtWidgets.QHBoxLayout()
        self.dtr_check = QtWidgets.QCheckBox("DTR")
        self.rts_check = QtWidgets.QCheckBox("RTS")
        lines.addWidget(self.dtr_check)
        lines.addWidget(self.rts_check)
        lines.addStretch(1)
        tform.addRow(T("Lignes de contrôle"), lines)
        tform.addRow(
            self._hint(
                T(
                    "Les ordinateurs Mares attendent DTR et RTS relâchés. Ne les "
                    "activez que si le vôtre reste muet autrement."
                )
            )
        )

        outer.addWidget(timings)

        demo = QtWidgets.QGroupBox(T("Mode démonstration"))
        dform = QtWidgets.QFormLayout(demo)
        self.demo_combo = QtWidgets.QComboBox()
        for name in DEMO_MODELS:
            self.demo_combo.addItem(f"Mares {name}", name)
        self.demo_combo.setToolTip(
            T("Modèle imité par le mode démo, pour voir le carnet sans matériel")
        )
        dform.addRow(T("Modèle simulé"), self.demo_combo)
        outer.addWidget(demo)

        test_row = QtWidgets.QHBoxLayout()
        self.test_button = QtWidgets.QPushButton(T("Tester la connexion"))
        self.test_button.clicked.connect(self._test_connection)
        self.test_label = QtWidgets.QLabel("")
        self.test_label.setWordWrap(True)
        self.test_label.setObjectName("subtitle")
        test_row.addWidget(self.test_button)
        test_row.addWidget(self.test_label, stretch=1)
        outer.addLayout(test_row)
        outer.addStretch(1)

        self._refresh_ports()
        return page

    # -- volet Bloc ---------------------------------------------------------

    def _build_tank_tab(self) -> QtWidgets.QWidget:
        page, form = self._page()

        self.tank_spin = self._spin(0.0, 40.0, " L", decimals=1, step=0.5)
        form.addRow(T("Volume du bloc"), self.tank_spin)

        self.start_spin = self._spin(0.0, 400.0, " bar", step=5)
        form.addRow(T("Pression de départ"), self.start_spin)

        self.end_spin = self._spin(0.0, 400.0, " bar", step=5)
        form.addRow(T("Pression de fin"), self.end_spin)

        self.device_tank_check = QtWidgets.QCheckBox(
            T("Utiliser les pressions mesurées par l'ordinateur quand il y en a")
        )
        form.addRow("", self.device_tank_check)

        form.addRow(
            self._hint(
                T(
                    "Ces valeurs s'appliquent aux plongées importées ensuite, pour "
                    "afficher une consommation dès le premier import. Une plongée "
                    "déjà en base garde ce qu'elle a ; vous pouvez toujours saisir "
                    "les vraies valeurs dans l'onglet Carnet."
                )
            )
        )
        return page

    # -- volet Analyse ------------------------------------------------------

    def _build_analysis_tab(self) -> QtWidgets.QWidget:
        page, form = self._page()

        self.gf_spin = self._spin(10, 100, " %")
        self.gf_spin.setToolTip(
            T("Marge appliquée aux M-values au chargement d'une plongée")
        )
        form.addRow(T("Facteur de gradient"), self.gf_spin)

        self.ascent_spin = self._spin(1.0, 30.0, " m/min", decimals=1, step=0.5)
        form.addRow(T("Vitesse de remontée maximale"), self.ascent_spin)

        self.ppo2_warn_spin = self._spin(0.5, 2.0, " bar", decimals=2, step=0.05)
        form.addRow(T("ppO2 d'avertissement"), self.ppo2_warn_spin)

        self.ppo2_max_spin = self._spin(0.5, 2.0, " bar", decimals=2, step=0.05)
        form.addRow(T("ppO2 critique"), self.ppo2_max_spin)

        band = QtWidgets.QHBoxLayout()
        self.stop_min_spin = self._spin(0.0, 20.0, " m", decimals=1, step=0.5)
        self.stop_max_spin = self._spin(0.0, 20.0, " m", decimals=1, step=0.5)
        band.addWidget(self.stop_min_spin)
        band.addWidget(QtWidgets.QLabel("→"))
        band.addWidget(self.stop_max_spin)
        band.addStretch(1)
        form.addRow(T("Bande du palier de sécurité"), band)

        self.stop_target_spin = self._spin(0, 900, " s", step=30)
        form.addRow(T("Palier considéré comme tenu"), self.stop_target_spin)

        self.window_spin = self._spin(5, 120, " s", step=5)
        self.window_spin.setToolTip(
            T("Plus la fenêtre est large, plus la courbe de vitesse est lisse")
        )
        form.addRow(T("Lissage des vitesses"), self.window_spin)

        form.addRow(
            self._hint(
                T(
                    "Ces seuils ne servent qu'à l'affichage et aux alertes du "
                    "carnet. Ils ne modifient ni les données de l'ordinateur, ni "
                    "sa décompression."
                )
            )
        )
        return page

    # -- volet Données ------------------------------------------------------

    def _build_data_tab(self) -> QtWidgets.QWidget:
        page, form = self._page()

        db_row = QtWidgets.QHBoxLayout()
        self.db_edit = QtWidgets.QLineEdit()
        self.db_edit.setPlaceholderText(str(config.default_db_path()))
        browse_db = QtWidgets.QPushButton("…")
        browse_db.setFixedWidth(36)
        browse_db.clicked.connect(self._browse_db)
        db_row.addWidget(self.db_edit, stretch=1)
        db_row.addWidget(browse_db)
        form.addRow(T("Base de plongées"), db_row)

        export_row = QtWidgets.QHBoxLayout()
        self.export_edit = QtWidgets.QLineEdit()
        self.export_edit.setPlaceholderText(str(Path.home()))
        browse_export = QtWidgets.QPushButton("…")
        browse_export.setFixedWidth(36)
        browse_export.clicked.connect(self._browse_export)
        export_row.addWidget(self.export_edit, stretch=1)
        export_row.addWidget(browse_export)
        form.addRow(T("Dossier d'export"), export_row)

        open_folder = QtWidgets.QPushButton(T("Ouvrir le dossier de données"))
        open_folder.clicked.connect(self._open_data_dir)
        form.addRow("", open_folder)

        portable = (
            T("Actif : les données sont rangées à côté de l'application.")
            if config.is_portable()
            else T(
                "Inactif. Pour emporter le carnet sur une clé USB, placez un "
                "fichier vide nommé « portable.txt » à côté de l'application."
            )
        )
        form.addRow(T("Mode portable"), self._hint(portable))
        form.addRow(
            self._hint(
                T("Changer de base de plongées prend effet au prochain démarrage.")
            )
        )
        return page

    # -- volet Diagnostic ---------------------------------------------------

    def _build_diagnostic_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        layout.addWidget(
            self._hint(
                T(
                    "Si quelque chose ne fonctionne pas sur cet ordinateur, "
                    "copiez ce texte et joignez-le à votre demande d'aide."
                )
            )
        )

        self.diagnostic_view = QtWidgets.QPlainTextEdit()
        self.diagnostic_view.setReadOnly(True)
        self.diagnostic_view.setFont(QtGui.QFontDatabase.systemFont(
            QtGui.QFontDatabase.SystemFont.FixedFont
        ))
        layout.addWidget(self.diagnostic_view, stretch=1)

        row = QtWidgets.QHBoxLayout()
        refresh = QtWidgets.QPushButton(T("Actualiser"))
        refresh.clicked.connect(self._refresh_diagnostic)
        copy = QtWidgets.QPushButton(T("Copier"))
        copy.clicked.connect(self._copy_diagnostic)
        row.addWidget(refresh)
        row.addWidget(copy)
        row.addStretch(1)
        layout.addLayout(row)

        self._refresh_diagnostic()
        return page

    # -- chargement et enregistrement ---------------------------------------

    def _load(self, settings: Settings) -> None:
        self._select(self.language_combo, settings.language)
        self._select(self.theme_combo, settings.theme)
        self._set(self.font_spin, settings.font_size)
        self._select(self.tab_combo, settings.start_tab)
        self.geometry_check.setChecked(settings.remember_geometry)
        self.confirm_check.setChecked(settings.confirm_hide)

        self._select(self.model_combo, settings.force_model)
        self._select(self.port_combo, settings.port)
        self.remember_port_check.setChecked(settings.remember_port)
        self._set(self.timeout_spin, settings.timeout)
        self._set(self.retries_spin, settings.retries)
        self._set(self.retry_delay_spin, settings.retry_delay)
        self._set(self.open_delay_spin, settings.open_delay)
        self._set(self.packet_spin, settings.packet_size)
        self._select(self.baud_combo, settings.baudrate)
        self.dtr_check.setChecked(settings.dtr)
        self.rts_check.setChecked(settings.rts)
        self._select(self.demo_combo, settings.demo_model)

        self._set(self.tank_spin, settings.tank_volume)
        self._set(self.start_spin, settings.pressure_start)
        self._set(self.end_spin, settings.pressure_end)
        self.device_tank_check.setChecked(settings.use_device_tank)

        self._set(self.gf_spin, settings.gradient_factor)
        self._set(self.ascent_spin, settings.ascent_limit)
        self._set(self.ppo2_warn_spin, settings.ppo2_warn)
        self._set(self.ppo2_max_spin, settings.ppo2_max)
        self._set(self.stop_min_spin, settings.safety_stop_min)
        self._set(self.stop_max_spin, settings.safety_stop_max)
        self._set(self.stop_target_spin, settings.safety_stop_target)
        self._set(self.window_spin, settings.rate_window)

        self.db_edit.setText(settings.db_path)
        self.export_edit.setText(settings.export_dir)

    def _collect(self) -> Settings:
        settings = self.draft.copy()
        settings.language = self.language_combo.currentData()
        settings.theme = self.theme_combo.currentData()
        settings.font_size = int(self.font_spin.value())
        settings.start_tab = int(self.tab_combo.currentData())
        settings.remember_geometry = self.geometry_check.isChecked()
        settings.confirm_hide = self.confirm_check.isChecked()

        settings.force_model = self.model_combo.currentData() or ""
        settings.port = self.port_combo.currentData() or ""
        settings.remember_port = self.remember_port_check.isChecked()
        settings.timeout = float(self.timeout_spin.value())
        settings.retries = int(self.retries_spin.value())
        settings.retry_delay = float(self.retry_delay_spin.value())
        settings.open_delay = float(self.open_delay_spin.value())
        settings.packet_size = int(self.packet_spin.value())
        settings.baudrate = int(self.baud_combo.currentData())
        settings.dtr = self.dtr_check.isChecked()
        settings.rts = self.rts_check.isChecked()
        settings.demo_model = self.demo_combo.currentData() or "Quad"

        settings.tank_volume = float(self.tank_spin.value())
        settings.pressure_start = float(self.start_spin.value())
        settings.pressure_end = float(self.end_spin.value())
        settings.use_device_tank = self.device_tank_check.isChecked()

        settings.gradient_factor = int(self.gf_spin.value())
        settings.ascent_limit = float(self.ascent_spin.value())
        settings.ppo2_warn = float(self.ppo2_warn_spin.value())
        settings.ppo2_max = float(self.ppo2_max_spin.value())
        settings.safety_stop_min = float(self.stop_min_spin.value())
        settings.safety_stop_max = float(self.stop_max_spin.value())
        settings.safety_stop_target = int(self.stop_target_spin.value())
        settings.rate_window = int(self.window_spin.value())

        settings.db_path = self.db_edit.text().strip()
        settings.export_dir = self.export_edit.text().strip()
        return settings

    def _save(self) -> None:
        collected = self._collect()
        if collected.safety_stop_min > collected.safety_stop_max:
            QtWidgets.QMessageBox.warning(
                self,
                T("Paramètres"),
                T("La bande du palier commence plus profond qu'elle ne finit."),
            )
            return
        if collected.ppo2_warn > collected.ppo2_max:
            QtWidgets.QMessageBox.warning(
                self,
                T("Paramètres"),
                T("La ppO2 d'avertissement doit rester sous la ppO2 critique."),
            )
            return

        self.needs_restart = any(
            getattr(collected, key) != getattr(self.original, key)
            for key in (*RESTART_KEYS, "db_path")
        )
        self.draft = collected
        try:
            collected.save()
        except OSError as exc:
            QtWidgets.QMessageBox.critical(
                self,
                T("Paramètres"),
                T("Enregistrement impossible : {error}").format(error=exc),
            )
            return
        config.set_settings(collected)
        self.accept()

    def _restore_defaults(self) -> None:
        confirm = QtWidgets.QMessageBox.question(
            self,
            T("Valeurs par défaut"),
            T("Remettre tous les réglages dans leur état d'origine ?"),
        )
        if confirm is QtWidgets.QMessageBox.StandardButton.Yes:
            self._load(self.original.reset())

    # -- actions ------------------------------------------------------------

    @staticmethod
    def _set(box: QtWidgets.QAbstractSpinBox, value: float) -> None:
        """Renseigne un champ numerique sans se soucier de son type exact."""
        if isinstance(box, QtWidgets.QSpinBox):
            box.setValue(int(round(value)))
        else:
            box.setValue(float(value))

    @staticmethod
    def _select(combo: QtWidgets.QComboBox, value: object) -> None:
        index = combo.findData(value)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _refresh_ports(self) -> None:
        previous = self.port_combo.currentData() or self.draft.port
        self.port_combo.clear()
        self.port_combo.addItem(T("Détection automatique"), "")
        for port in list_serial_ports():
            self.port_combo.addItem(port.label, port.device)
        self._select(self.port_combo, previous)

    def _browse_db(self) -> None:
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            T("Base de plongées"),
            self.db_edit.text() or str(config.default_db_path()),
            "SQLite (*.sqlite *.db)",
        )
        if path:
            self.db_edit.setText(path)

    def _browse_export(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, T("Dossier d'export"), self.export_edit.text() or str(Path.home())
        )
        if path:
            self.export_edit.setText(path)

    def _open_data_dir(self) -> None:
        path = config.app_dir()
        try:
            if sys.platform.startswith("win"):
                subprocess.Popen(["explorer", str(path)])  # noqa: S607
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])  # noqa: S607
            else:
                subprocess.Popen(["xdg-open", str(path)])  # noqa: S607
        except OSError as exc:  # pragma: no cover - depend du bureau
            QtWidgets.QMessageBox.information(self, T("Dossier de données"), str(path))
            log.warning("Ouverture du dossier impossible : %s", exc)

    def _refresh_diagnostic(self) -> None:
        self.diagnostic_view.setPlainText(config.diagnostic().as_text())

    def _copy_diagnostic(self) -> None:
        clipboard = QtWidgets.QApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.diagnostic_view.toPlainText())
        self.test_label.setText(T("Diagnostic copié."))

    def _test_connection(self) -> None:
        """Se connecte vraiment, pour verifier cable, pilote et modele."""
        if self.probe is not None and self.probe.isRunning():
            return
        self.test_button.setEnabled(False)
        self.test_label.setText(T("Connexion en cours…"))
        self.probe = ProbeWorker(self._collect(), parent=self)
        self.probe.succeeded.connect(self._on_probe_ok)
        self.probe.failed.connect(self._on_probe_failed)
        self.probe.finished.connect(lambda: self.test_button.setEnabled(True))
        self.probe.start()

    def _on_probe_ok(self, label: str) -> None:
        self.test_label.setText(T("Connecté : {device}").format(device=label))
        self.test_label.setStyleSheet(f"color: {theme.GOOD};")

    def _on_probe_failed(self, message: str) -> None:
        self.test_label.setText(message)
        self.test_label.setStyleSheet(f"color: {theme.WARN};")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        if self.probe is not None and self.probe.isRunning():
            self.probe.wait(2000)
        super().closeEvent(event)
