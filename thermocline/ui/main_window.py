"""Fenetre principale: liste des plongees, profil, analyses et statistiques."""

from __future__ import annotations

import csv
import datetime as _dt
import logging

from PyQt6 import QtCore, QtGui, QtWidgets

from .. import __version__, analytics, config, dates
from ..analytics import LIMITS, DiveStats, Overview, pretty_duration
from ..csv_import import CsvFormatError, annotate_known, import_rows, parse_csv_file
from ..i18n import T, count_label
from ..models import Dive, Sample
from ..storage import Database, DiveSummary, ImportResult, TankSource
from ..transport import list_serial_ports
from . import theme
from .dialogs import CsvImportDialog, HiddenDivesDialog
from .plots import (
    SPEED_HISTOGRAM_TOOLTIP,
    TEMP_DEPTH_TOOLTIP,
    TIME_AT_DEPTH_TOOLTIP,
    BarPanel,
    CategoryBarPanel,
    EadPlot,
    GasPressurePlot,
    NavigatorPlot,
    OxygenLoadPlot,
    PpO2Plot,
    ProfilePlot,
    RatePlot,
    ScatterPanel,
    TissueBarPanel,
    TissueLoadPlot,
    TrendPanel,
    ZoomBar,
    sync_cursors,
)
from .settings_dialog import SettingsDialog
from .widgets import CardRow, KeyValueTable, SectionTitle, scrollable
from .workers import ImportWorker

log = logging.getLogger(__name__)

SORT_ROLE = QtCore.Qt.ItemDataRole.UserRole + 1
UID_ROLE = QtCore.Qt.ItemDataRole.UserRole + 2

COLUMNS: tuple[tuple[str, str], ...] = (
    ("number", "N°"),
    ("date", "Date"),
    ("duration", "Durée"),
    ("max_depth", "Max"),
    ("temp", "Temp."),
    ("gas", "Gaz"),
    ("site", "Site"),
)

#: Largeur initiale de chaque colonne, en pixels. La derniere est elastique.
COLUMN_WIDTHS: tuple[int, ...] = (34, 98, 52, 48, 46, 78, 130)

CONNECTION_HELP = """<b>Brancher un ordinateur Mares</b><br><br>
1. Clipsez le câble USB Mares sur les contacts au dos de l'ordinateur.<br>
2. Réveillez l'ordinateur en appuyant sur un bouton, et mettez-le en mode
   transfert de données si votre modèle le demande.<br>
3. Choisissez le port dans la barre d'outils — un <b>*</b> signale un
   convertisseur USB-série reconnu — puis cliquez sur
   <b>Importer les plongées</b>.<br><br>
<b>Rien ne se passe ?</b><br>
• Installez le pilote du convertisseur (FTDI, CP210x, CH340 selon le câble).<br>
• Fermez tout autre logiciel qui pourrait tenir le port.<br>
• Les modèles Sirius, Puck 4 et Puck Air 2 ne parlent qu'en Bluetooth : ils ne
  sont pas lisibles par câble.<br>
• Augmentez le délai d'attente dans <b>Paramètres › Ordinateur</b>.<br>
• <b>Aide › Diagnostic</b> résume ce que voit l'application."""

ABOUT_TEXT = """<b>Thermocline {version}</b><br><br>
Carnet de plongée local pour les ordinateurs Mares.<br>
Aucun compte, aucun service en ligne : tout reste sur cette machine.<br><br>
Le décodage des données dérive de <b>libdivecomputer</b> (LGPL 2.1) ;
ce projet est distribué sous la même licence.<br><br>
Les calculs de saturation sont <b>indicatifs</b> et ne doivent jamais servir
à planifier une plongée."""

DECO_DISCLAIMER = (
    "Modèle Bühlmann ZH-L16C rejoué à titre indicatif sur un profil déjà "
    "réalisé. Ce n'est pas l'algorithme de l'ordinateur Mares, et cela ne doit "
    "jamais servir à planifier une plongée."
)


class DiveTableModel(QtCore.QAbstractTableModel):
    """Liste des plongees, en lecture seule."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self._rows: list[DiveSummary] = []

    def set_rows(self, rows: list[DiveSummary]) -> None:
        self.beginResetModel()
        self._rows = rows
        self.endResetModel()

    def summary_at(self, row: int) -> DiveSummary | None:
        return self._rows[row] if 0 <= row < len(self._rows) else None

    # -- API Qt -------------------------------------------------------------

    def rowCount(self, parent: QtCore.QModelIndex | None = None) -> int:  # noqa: N802
        return 0 if parent and parent.isValid() else len(self._rows)

    def columnCount(self, parent: QtCore.QModelIndex | None = None) -> int:  # noqa: N802
        return 0 if parent and parent.isValid() else len(COLUMNS)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: QtCore.Qt.Orientation,
        role: int = QtCore.Qt.ItemDataRole.DisplayRole,
    ):
        if (
            orientation is QtCore.Qt.Orientation.Horizontal
            and role == QtCore.Qt.ItemDataRole.DisplayRole
        ):
            return T(COLUMNS[section][1])
        return None

    def data(self, index: QtCore.QModelIndex, role: int = QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        key = COLUMNS[index.column()][0]

        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return self._display(row, key)
        if role == SORT_ROLE:
            return self._sort_value(row, key)
        if role == UID_ROLE:
            return row.uid
        if role == QtCore.Qt.ItemDataRole.TextAlignmentRole:
            if key in ("number", "duration", "max_depth", "temp"):
                return int(
                    QtCore.Qt.AlignmentFlag.AlignRight
                    | QtCore.Qt.AlignmentFlag.AlignVCenter
                )
            return int(
                QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignVCenter
            )
        if (
            role == QtCore.Qt.ItemDataRole.ForegroundRole
            and key == "max_depth"
            and row.max_depth >= 40
        ):
            return QtGui.QColor(theme.WARN)
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            bits = [dates.long_datetime(row.started_at)]
            if row.site:
                bits.append(T("Site : {site}").format(site=row.site))
            if row.buddy:
                bits.append(T("Binôme : {buddy}").format(buddy=row.buddy))
            if row.notes:
                bits.append(row.notes)
            return "\n".join(bits)
        return None

    @staticmethod
    def _display(row: DiveSummary, key: str) -> str:
        match key:
            case "number":
                return str(row.number)
            case "date":
                return f"{row.started_at:%d/%m/%y %H:%M}"  # i18n: skip
            case "duration":
                return row.duration_label
            case "max_depth":
                return f"{row.max_depth:.1f}"  # i18n: skip
            case "temp":
                return f"{row.temp_min:.0f}°" if row.temp_min is not None else "-"  # i18n: skip
            case "gas":
                return row.gas_label
            case _:
                return row.site or "-"

    @staticmethod
    def _sort_value(row: DiveSummary, key: str):
        match key:
            case "number":
                return row.number
            case "date":
                return row.started_at.timestamp()
            case "duration":
                return row.duration
            case "max_depth":
                return row.max_depth
            case "temp":
                return row.temp_min if row.temp_min is not None else 99.0
            case "gas":
                return row.gas_label
            case _:
                return row.site.lower()


class DiveFilterModel(QtCore.QSortFilterProxyModel):
    """Filtre texte libre sur le site, le binome, les notes et la date."""

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)
        self.setSortRole(SORT_ROLE)
        self._needle = ""

    def set_needle(self, text: str) -> None:
        self._needle = text.strip().lower()
        self.invalidateFilter()

    def filterAcceptsRow(  # noqa: N802
        self, source_row: int, source_parent: QtCore.QModelIndex
    ) -> bool:
        if not self._needle:
            return True
        model = self.sourceModel()
        assert isinstance(model, DiveTableModel)
        row = model.summary_at(source_row)
        if row is None:
            return False
        haystack = " ".join(
            [
                row.site,
                row.buddy,
                row.notes,
                row.gas_label,
                row.mode.label,
                f"{row.started_at:%d/%m/%Y}",  # i18n: skip
            ]
        ).lower()
        return self._needle in haystack


class MainWindow(QtWidgets.QMainWindow):
    """Fenetre unique de l'application."""

    def __init__(
        self,
        db: Database,
        demo: bool = False,
        settings: config.Settings | None = None,
    ) -> None:
        super().__init__()
        self.db = db
        self.settings = settings or config.settings()
        self.worker: ImportWorker | None = None
        self.current: DiveSummary | None = None
        self.current_dive: Dive | None = None
        self.current_stats: DiveStats | None = None
        self._splitter_sized = False
        self._syncing_range = False

        self.setWindowTitle(T("Thermocline — carnet de plongée"))
        self.resize(1560, 940)

        self._build_menus()
        self._build_toolbar(demo)
        self._build_central()
        self._build_statusbar()
        self._restore_geometry()
        self.tabs.setCurrentIndex(self.settings.start_tab)
        self.gf_spin.setValue(self.settings.gradient_factor)
        self.reload()

    # -- construction -------------------------------------------------------

    def _build_menus(self) -> None:
        """Barre de menus: tout est aussi accessible depuis la barre d'outils."""
        bar = self.menuBar()

        carnet = bar.addMenu(T("&Carnet"))
        self._action(carnet, T("Importer les plongées"), lambda: self.start_import(),
                     shortcut="Ctrl+I")
        self._action(carnet, T("Tout relire"), lambda: self.start_import(full=True))
        carnet.addSeparator()
        self._action(carnet, T("Importer un CSV…"), self.import_csv)
        self._action(carnet, T("Exporter le carnet…"), self.export_csv, shortcut="Ctrl+E")
        self._action(carnet, T("Exporter le profil…"), self.export_profile_csv)
        carnet.addSeparator()
        self._action(carnet, T("Quitter"), self.close, shortcut="Ctrl+Q")

        outils = bar.addMenu(T("&Outils"))
        self._action(outils, T("Plongées masquées…"), self.open_hidden_dialog)
        self._action(outils, T("Rafraîchir les ports série"), self.refresh_ports,
                     shortcut="F5")
        outils.addSeparator()
        self._action(outils, T("Paramètres…"), self.open_settings, shortcut="Ctrl+,")

        aide = bar.addMenu(T("&Aide"))
        self._action(aide, T("Brancher mon ordinateur…"), self.show_connection_help)
        self._action(aide, T("Diagnostic…"), self.show_diagnostic)
        aide.addSeparator()
        self._action(aide, T("À propos de Thermocline"), self.show_about)

    def _action(
        self,
        menu: QtWidgets.QMenu,
        label: str,
        slot,
        shortcut: str = "",
    ) -> QtGui.QAction:
        action = QtGui.QAction(label, self)
        if shortcut:
            action.setShortcut(QtGui.QKeySequence(shortcut))
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _build_toolbar(self, demo: bool) -> None:
        bar = QtWidgets.QToolBar(T("Actions"))
        bar.setMovable(False)
        self.addToolBar(bar)

        bar.addWidget(QtWidgets.QLabel(T("Port  ")))
        self.port_combo = QtWidgets.QComboBox()
        self.port_combo.setMinimumWidth(250)
        bar.addWidget(self.port_combo)

        refresh = QtGui.QAction(T("Rafraîchir"), self)
        refresh.setToolTip(T("Relire la liste des ports série"))
        refresh.triggered.connect(self.refresh_ports)
        bar.addAction(refresh)
        bar.addSeparator()

        self.import_button = QtWidgets.QPushButton(T("Importer les plongées"))
        self.import_button.setObjectName("primary")
        self.import_button.clicked.connect(lambda: self.start_import(full=False))
        bar.addWidget(self.import_button)

        self.full_button = QtWidgets.QPushButton(T("Tout relire"))
        self.full_button.setToolTip(
            T("Relit tout l'historique de l'ordinateur, sans s'arrêter à la "
            "dernière plongée connue")
        )
        self.full_button.clicked.connect(lambda: self.start_import(full=True))
        bar.addWidget(self.full_button)

        self.demo_check = QtWidgets.QCheckBox(T("Mode démo"))
        self.demo_check.setToolTip(T("Importe des plongées simulées, sans ordinateur branché"))
        self.demo_check.setChecked(demo)
        bar.addWidget(self.demo_check)

        bar.addSeparator()

        import_csv_button = QtWidgets.QPushButton(T("Importer un CSV…"))
        import_csv_button.setToolTip(
            T("Ajouter des plongées depuis un carnet CSV (le format d'« Exporter le "
            "carnet », ou compatible) ; vous choisissez ensuite lesquelles importer")
        )
        import_csv_button.clicked.connect(self.import_csv)
        bar.addWidget(import_csv_button)

        spacer = QtWidgets.QWidget()
        # Sans fond transparent, l'espaceur se peint comme un champ vide.
        spacer.setObjectName("toolbarSpacer")
        spacer.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred
        )
        bar.addWidget(spacer)

        export = QtWidgets.QPushButton(T("Exporter le carnet"))
        export.setToolTip(T("Une ligne par plongée, au format CSV"))
        export.clicked.connect(self.export_csv)
        bar.addWidget(export)

        self.hidden_button = QtWidgets.QPushButton(T("Masquées"))
        self.hidden_button.setToolTip(
            T("Consulter les plongées masquées et les rendre à nouveau importables")
        )
        self.hidden_button.clicked.connect(self.open_hidden_dialog)
        bar.addWidget(self.hidden_button)

        profile_export = QtWidgets.QPushButton(T("Exporter le profil"))
        profile_export.setToolTip(
            T("Toutes les séries calculées de la plongée affichée, au format CSV")
        )
        profile_export.clicked.connect(self.export_profile_csv)
        bar.addWidget(profile_export)

        settings_button = QtWidgets.QPushButton(T("Paramètres"))
        settings_button.setToolTip(
            T("Langue, modèle d'ordinateur, délais de connexion, bloc, seuils…")
        )
        settings_button.clicked.connect(self.open_settings)
        bar.addWidget(settings_button)

        self.refresh_ports()

    def _build_central(self) -> None:
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        self.splitter.addWidget(self._build_list_panel())
        self.splitter.addWidget(self._build_tabs())
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.setCentralWidget(self.splitter)

    def showEvent(self, event: QtGui.QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        # La repartition n'est fiable qu'une fois la largeur reelle connue:
        # appliquee dans le constructeur, elle est renormalisee par Qt.
        if not self._splitter_sized:
            self._splitter_sized = True
            total = self.splitter.width()
            left = min(max(int(total * 0.3), 360), 520)
            self.splitter.setSizes([left, total - left])

    def _build_list_panel(self) -> QtWidgets.QWidget:
        panel = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(10, 10, 5, 10)
        layout.setSpacing(8)

        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(T("Filtrer : site, binôme, notes, date…"))
        self.search.setClearButtonEnabled(True)
        layout.addWidget(self.search)

        self.model = DiveTableModel(self)
        self.proxy = DiveFilterModel(self)
        self.proxy.setSourceModel(self.model)
        self.search.textChanged.connect(self.proxy.set_needle)

        self.table = QtWidgets.QTableView()
        self.table.setModel(self.proxy)
        self.table.setSortingEnabled(True)
        self.table.sortByColumn(1, QtCore.Qt.SortOrder.DescendingOrder)
        self.table.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(26)
        header = self.table.horizontalHeader()
        # Largeurs fixees puis ajustables: en mode ResizeToContents la colonne
        # Site finissait hors du panneau.
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate(COLUMN_WIDTHS):
            header.resizeSection(column, width)
        header.setSectionResizeMode(
            len(COLUMNS) - 1, QtWidgets.QHeaderView.ResizeMode.Stretch
        )
        self.table.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        self.table.setWordWrap(False)
        self.table.setHorizontalScrollMode(
            QtWidgets.QAbstractItemView.ScrollMode.ScrollPerPixel
        )
        self.table.selectionModel().currentRowChanged.connect(self._on_row_changed)
        self.table.setContextMenuPolicy(QtCore.Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._on_context_menu)
        layout.addWidget(self.table)

        self.count_label = QtWidgets.QLabel()
        self.count_label.setObjectName("subtitle")
        layout.addWidget(self.count_label)
        return panel

    def _build_tabs(self) -> QtWidgets.QWidget:
        self.tabs = QtWidgets.QTabWidget()
        self.tabs.addTab(self._build_profile_tab(), T("Profil"))
        self.tabs.addTab(self._build_analysis_tab(), T("Analyse"))
        self.tabs.addTab(self._build_oxygen_tab(), T("Oxygène et tissus"))
        self.tabs.addTab(self._build_details_tab(), T("Détails"))
        self.tabs.addTab(self._build_dashboard_tab(), T("Statistiques"))
        self.tabs.addTab(self._build_logbook_tab(), T("Carnet"))

        # Un curseur de lecture commun a tous les graphiques temporels.
        self.time_panels = [
            self.profile_plot,
            self.rate_plot,
            self.pressure_plot,
            self.ppo2_plot,
            self.oxygen_plot,
            self.tissue_plot,
            self.ead_plot,
        ]
        sync_cursors(self.time_panels)
        return self.tabs

    # -- onglet Profil ------------------------------------------------------

    def _build_profile_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.dive_title = SectionTitle(T("Aucune plongée sélectionnée"), "")
        layout.addWidget(self.dive_title)

        self.dive_cards = CardRow(
            [
                ("max_depth", T("Prof. max")),
                ("duration", T("Durée")),
                ("avg_depth", T("Prof. moy")),
                ("temp", T("Temp. min")),
                ("ascent", T("Remontée max")),
                ("safety", T("Palier 3-6 m")),
            ]
        )
        layout.addWidget(self.dive_cards)

        self.dive_cards2 = CardRow(
            [
                ("gas", T("Mélange")),
                ("ppo2", T("ppO2 max")),
                ("cns", T("CNS")),
                ("otu", T("OTU")),
                ("ead", T("Prof. équiv. air")),
                ("sac", T("Conso.")),
            ]
        )
        layout.addWidget(self.dive_cards2)

        self.profile_plot = ProfilePlot()
        layout.addWidget(ZoomBar([self.profile_plot]))
        layout.addWidget(self.profile_plot, stretch=1)

        self.navigator = NavigatorPlot()
        self.navigator.setToolTip(
            T("Vue d'ensemble du profil : déplacez ou redimensionnez la fenêtre "
            "claire pour zoomer sur une phase de la plongée")
        )
        layout.addWidget(self.navigator)

        self.navigator.range_changed.connect(self._on_navigator_moved)
        self.profile_plot.item.sigXRangeChanged.connect(self._on_profile_range_changed)
        return page

    # -- onglet Analyse ----------------------------------------------------

    def _build_analysis_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.rate_plot = RatePlot()
        self.pressure_plot = GasPressurePlot()
        self.time_at_depth_plot = BarPanel(
            "", T("Temps (min)"), T("Profondeur (m)"), theme.DEPTH, horizontal=True, invert_y=True
        )
        self.speed_hist_plot = BarPanel("", T("Vitesse (m/min)"), T("Temps (min)"), theme.ASCENT)
        self.time_at_depth_plot.setToolTip(T(TIME_AT_DEPTH_TOOLTIP))
        self.speed_hist_plot.setToolTip(T(SPEED_HISTOGRAM_TOOLTIP))

        layout.addWidget(
            ZoomBar(
                [
                    self.rate_plot,
                    self.pressure_plot,
                    self.time_at_depth_plot,
                    self.speed_hist_plot,
                ],
                [self.rate_plot, self.pressure_plot],
            )
        )

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self._titled(T("Vitesse verticale"), self.rate_plot), 0, 0)
        grid.addWidget(self._titled(T("Pression du bloc"), self.pressure_plot), 0, 1)
        grid.addWidget(
            self._titled(T("Temps par tranche de 3 m"), self.time_at_depth_plot), 1, 0
        )
        grid.addWidget(
            self._titled(T("Répartition des vitesses verticales"), self.speed_hist_plot), 1, 1
        )
        for index in (0, 1):
            grid.setRowStretch(index, 1)
            grid.setColumnStretch(index, 1)
        layout.addLayout(grid, stretch=1)
        return page

    # -- onglet Oxygene & tissus -------------------------------------------

    def _build_oxygen_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        self.ppo2_plot = PpO2Plot()
        self.oxygen_plot = OxygenLoadPlot()
        self.tissue_plot = TissueLoadPlot()
        self.ead_plot = EadPlot()
        self.tissue_bars = TissueBarPanel()

        controls = QtWidgets.QHBoxLayout()
        controls.setSpacing(8)
        controls.addWidget(
            ZoomBar(
                [
                    self.ppo2_plot,
                    self.oxygen_plot,
                    self.tissue_plot,
                    self.ead_plot,
                    self.tissue_bars,
                ],
                [self.ppo2_plot, self.oxygen_plot, self.tissue_plot, self.ead_plot],
            ),
            stretch=1,
        )
        controls.addWidget(QtWidgets.QLabel(T("Facteur de gradient")))
        self.gf_spin = QtWidgets.QSpinBox()
        self.gf_spin.setRange(30, 100)
        self.gf_spin.setValue(100)
        self.gf_spin.setSuffix(" %")
        self.gf_spin.setMinimumWidth(90)
        self.gf_spin.setToolTip(
            T("Marge appliquée aux M-values : 100 % = limites Bühlmann brutes, "
            "une valeur plus basse est plus conservatrice")
        )
        self.gf_spin.valueChanged.connect(self._on_gradient_factor_changed)
        controls.addWidget(self.gf_spin)
        layout.addLayout(controls)

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        grid.addWidget(self._titled(T("Pression partielle d'oxygène"), self.ppo2_plot), 0, 0)
        grid.addWidget(self._titled(T("Charge CNS et OTU cumulées"), self.oxygen_plot), 0, 1)
        grid.addWidget(
            self._titled(T("Compartiment directeur et plafond"), self.tissue_plot), 1, 0
        )
        grid.addWidget(self._titled(T("Profondeur équivalente air"), self.ead_plot), 1, 1)
        grid.addWidget(
            self._titled(T("Charge des 16 compartiments à la sortie"), self.tissue_bars),
            2, 0, 1, 2,
        )
        for index in (0, 1, 2):
            grid.setRowStretch(index, 1)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid, stretch=1)

        disclaimer = QtWidgets.QLabel(T(DECO_DISCLAIMER))
        disclaimer.setObjectName("subtitle")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)
        return page

    # -- onglet Details ----------------------------------------------------

    def _build_details_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        grid = QtWidgets.QGridLayout(page)
        grid.setContentsMargins(10, 10, 10, 10)
        grid.setSpacing(10)

        self.profile_table = KeyValueTable()
        self.gas_table = KeyValueTable()
        self.device_table = KeyValueTable()
        self.temp_depth_plot = ScatterPanel(
            "", T("Profondeur (m)"), T("Température (°C)"), theme.TEMP
        )
        self.temp_depth_plot.setToolTip(T(TEMP_DEPTH_TOOLTIP))

        grid.addWidget(self._titled(T("Profondeur, durée, vitesses"), self.profile_table), 0, 0)
        grid.addWidget(self._titled(T("Gaz, oxygène, décompression"), self.gas_table), 0, 1)
        grid.addWidget(
            self._titled(T("Température en fonction de la profondeur"), self.temp_depth_plot),
            1, 0,
        )
        grid.addWidget(self._titled(T("Ordinateur et enregistrement"), self.device_table), 1, 1)
        grid.setRowStretch(0, 3)
        grid.setRowStretch(1, 2)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        return page

    # -- onglet Statistiques ------------------------------------------------

    def _build_dashboard_tab(self) -> QtWidgets.QWidget:
        content = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.overview_cards = CardRow(
            [
                ("dives", T("Plongées")),
                ("time", T("Temps immergé")),
                ("max_depth", T("Record")),
                ("avg_depth", T("Prof. moyenne")),
                ("avg_duration", T("Durée moyenne")),
                ("coldest", T("Eau la + froide")),
            ]
        )
        layout.addWidget(self.overview_cards)

        self.overview_cards2 = CardRow(
            [
                ("avg_max", T("Prof. max moyenne")),
                ("descent", T("Cumul descendu")),
                ("streak", T("Jours d'affilée")),
                ("rolling", T("Sur 12 mois")),
                ("sites", T("Sites visités")),
                ("last", T("Dernière sortie")),
            ]
        )
        layout.addWidget(self.overview_cards2)

        self.per_month_chart = CategoryBarPanel(T("Plongées par mois"), T("nombre"), theme.DEPTH)
        self.per_year_chart = CategoryBarPanel(T("Plongées par année"), T("nombre"), theme.GOOD)
        self.per_weekday_chart = CategoryBarPanel(T("Jour de la semaine"), T("nombre"), theme.PPO2)
        self.per_hour_chart = CategoryBarPanel(T("Heure de mise à l'eau"), T("nombre"), theme.TEMP)
        self.depth_distribution = CategoryBarPanel(
            T("Tranches de profondeur"), T("plongées"), theme.PPO2
        )
        self.duration_distribution = CategoryBarPanel(
            T("Tranches de durée"), T("plongées"), theme.ASCENT
        )
        self.sites_chart = CategoryBarPanel(
            T("Sites les plus plongés"), T("plongées"), theme.DEPTH, horizontal=True
        )

        self.depth_trend = TrendPanel(T("Profondeur maximale"), "m", theme.DEPTH, invert=True)
        self.avg_depth_trend = TrendPanel(
            T("Profondeur moyenne"), "m", theme.ACCENT, invert=True
        )
        self.duration_trend = TrendPanel(T("Durée des plongées"), "min", theme.GOOD)
        self.temp_trend = TrendPanel(T("Température minimale"), "°C", theme.TEMP)
        self.cumulative_trend = TrendPanel(T("Temps immergé cumulé"), T("heures"), theme.GOOD)
        self.cumulative_dives_trend = TrendPanel(
            T("Nombre de plongées cumulé"), T("plongées"), theme.DEPTH
        )
        self.rolling_trend = TrendPanel(
            T("Plongées sur 12 mois glissants"), T("plongées"), theme.PPO2
        )
        self.sac_trend = TrendPanel(T("Consommation (SAC)"), T("L/min"), theme.WARN)
        self.interval_chart = TrendPanel(
            T("Intervalles de surface (< 24 h)"), T("heures"), theme.TEMP
        )

        self.global_time_at_depth = BarPanel(
            "", T("Temps (min)"), T("Profondeur (m)"), theme.DEPTH, horizontal=True, invert_y=True
        )
        self.duration_depth_scatter = ScatterPanel(
            "", T("Durée (min)"), T("Profondeur max (m)"), theme.ACCENT, invert_y=True
        )

        charts = [
            self.per_month_chart,
            self.per_year_chart,
            self.depth_trend,
            self.avg_depth_trend,
            self.duration_trend,
            self.temp_trend,
            self.cumulative_trend,
            self.cumulative_dives_trend,
            self.rolling_trend,
            self.sac_trend,
            self.per_weekday_chart,
            self.per_hour_chart,
            self.depth_distribution,
            self.duration_distribution,
            self.duration_depth_scatter,
            self.interval_chart,
            self.sites_chart,
            self.global_time_at_depth,
        ]
        for chart in charts:
            chart.setMinimumHeight(210)
            chart.setMinimumWidth(230)
        layout.addWidget(ZoomBar(charts))

        grid = QtWidgets.QGridLayout()
        grid.setSpacing(10)
        titles = {
            id(self.duration_depth_scatter): T("Durée en fonction de la profondeur maximale"),
            id(self.global_time_at_depth): T("Temps total par tranche de 3 m"),
        }
        for index, chart in enumerate(charts):
            row, column = divmod(index, 2)
            title = titles.get(id(chart))
            grid.addWidget(self._titled(title, chart) if title else chart, row, column)
        grid.setColumnStretch(0, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

        self.records_table = KeyValueTable()
        self.records_table.setMinimumHeight(300)
        records_box = QtWidgets.QGroupBox(T("Records et repères"))
        records_layout = QtWidgets.QVBoxLayout(records_box)
        records_layout.addWidget(self.records_table)
        layout.addWidget(records_box)
        return scrollable(content)

    # -- onglet Carnet ------------------------------------------------------

    def _build_logbook_tab(self) -> QtWidgets.QWidget:
        page = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(page)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        form_box = QtWidgets.QGroupBox(T("Mes notes"))
        form = QtWidgets.QFormLayout(form_box)
        form.setSpacing(8)

        self.site_edit = QtWidgets.QLineEdit()
        self.buddy_edit = QtWidgets.QLineEdit()
        self.rating_spin = QtWidgets.QSpinBox()
        self.rating_spin.setRange(0, 5)
        self.rating_spin.setSuffix(" / 5")
        self.notes_edit = QtWidgets.QTextEdit()
        self.notes_edit.setMinimumHeight(160)

        self.tank_spin = QtWidgets.QDoubleSpinBox()
        self.tank_spin.setRange(0, 40)
        self.tank_spin.setDecimals(1)
        self.tank_spin.setSuffix(" L")
        self.start_spin = QtWidgets.QDoubleSpinBox()
        self.start_spin.setRange(0, 400)
        self.start_spin.setSuffix(T(" bar"))
        self.end_spin = QtWidgets.QDoubleSpinBox()
        self.end_spin.setRange(0, 400)
        self.end_spin.setSuffix(T(" bar"))

        form.addRow(T("Site"), self.site_edit)
        form.addRow(T("Binôme"), self.buddy_edit)
        form.addRow(T("Note"), self.rating_spin)
        form.addRow(T("Bloc"), self.tank_spin)
        form.addRow(T("Pression départ"), self.start_spin)
        form.addRow(T("Pression fin"), self.end_spin)
        form.addRow(T("Commentaire"), self.notes_edit)

        hint = QtWidgets.QLabel(
            T(
                "Quand l'ordinateur ne mesure pas la pression du bloc, saisir "
                "ici le bloc et les pressions permet de calculer la "
                "consommation ramenée à la surface et d'estimer la courbe de "
                "pression. Les modèles à intégration d'air remplissent ces "
                "champs tout seuls."
            )
        )
        hint.setObjectName("subtitle")
        hint.setWordWrap(True)
        form.addRow(hint)

        self.save_button = QtWidgets.QPushButton(T("Enregistrer"))
        self.save_button.setObjectName("primary")
        self.save_button.clicked.connect(self.save_annotations)
        form.addRow(self.save_button)

        history_box = QtWidgets.QGroupBox(T("Historique des imports"))
        history_layout = QtWidgets.QVBoxLayout(history_box)
        self.history_table = KeyValueTable()
        history_layout.addWidget(self.history_table)

        layout.addWidget(form_box, stretch=1)
        layout.addWidget(history_box, stretch=1)
        return page

    @staticmethod
    def _titled(title: str, widget: QtWidgets.QWidget) -> QtWidgets.QWidget:
        box = QtWidgets.QGroupBox(title)
        layout = QtWidgets.QVBoxLayout(box)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(widget)
        return box

    def _build_statusbar(self) -> None:
        self.status = self.statusBar()
        self.progress = QtWidgets.QProgressBar()
        self.progress.setMaximumWidth(220)
        self.progress.setVisible(False)
        self.status.addPermanentWidget(self.progress)
        self.status.showMessage(T("Prêt."))

    # -- donnees ------------------------------------------------------------

    def refresh_ports(self) -> None:
        previous = (
            self.port_combo.currentData()
            or self.settings.port
            or (self.settings.last_port if self.settings.remember_port else "")
        )
        self.port_combo.clear()
        ports = list_serial_ports()
        for port in ports:
            self.port_combo.addItem(port.label, port.device)
        if not ports:
            self.port_combo.addItem(T("Aucun port détecté"), None)
        if previous:
            index = self.port_combo.findData(previous)
            if index >= 0:
                self.port_combo.setCurrentIndex(index)

    def reload(self, select_uid: str | None = None) -> None:
        """Recharge la liste depuis la base et rafraichit les statistiques."""
        rows = self.db.list_dives()
        self.model.set_rows(rows)
        label = (
            count_label(len(rows), "{count} plongée en base", "{count} plongées en base")
            if rows
            else T("Base vide")
        )
        hidden = self.db.hidden_count()
        if hidden:
            label += count_label(hidden, " · {count} masquée", " · {count} masquées")
        self.count_label.setText(f"{label} · {self.db.path.name}")
        self.count_label.setToolTip(str(self.db.path))
        self.hidden_button.setText(T("Masquées ({hidden})").format(hidden=hidden) if hidden else T("Masquées"))
        self.hidden_button.setEnabled(bool(hidden))
        self._update_dashboard(rows)
        self._update_history()

        if not rows:
            self._clear_dive_view()
            return
        target = select_uid or (self.current.uid if self.current else rows[0].uid)
        self._select_uid(target)

    def _select_uid(self, uid: str) -> None:
        for row in range(self.proxy.rowCount()):
            index = self.proxy.index(row, 0)
            if self.proxy.data(index, UID_ROLE) == uid:
                self.table.setCurrentIndex(index)
                return
        if self.proxy.rowCount():
            self.table.setCurrentIndex(self.proxy.index(0, 0))

    def _on_row_changed(
        self, current: QtCore.QModelIndex, _previous: QtCore.QModelIndex
    ) -> None:
        if not current.isValid():
            return
        summary = self.model.summary_at(self.proxy.mapToSource(current).row())
        if summary is None:
            return
        self.current = summary
        self.current_dive = self.db.load_dive(summary.uid)
        if self.current_dive is None:
            return
        self._show_dive(summary, self.current_dive)

    def _clear_dive_view(self) -> None:
        self.current = None
        self.current_dive = None
        self.current_stats = None
        self.dive_title.set_text(T("Aucune plongée sélectionnée"), "")
        self.dive_cards.reset()
        self.dive_cards2.reset()
        self.profile_plot.clear()
        self.navigator.show_dive([])
        self.rate_plot.show_series([])
        self.pressure_plot.show_series([], False)
        self.time_at_depth_plot.show_buckets([])
        self.speed_hist_plot.show_buckets([])
        self.ppo2_plot.show_series([])
        self.oxygen_plot.show_series([], [])
        self.tissue_plot.show_series([], [], [])
        self.ead_plot.show_series([], [])
        self.tissue_bars.show_loadings([])
        self.temp_depth_plot.show_points([])
        for table in (self.profile_table, self.gas_table, self.device_table):
            table.set_rows([])

    # -- affichage d'une plongee -------------------------------------------

    def _show_dive(self, summary: DiveSummary, dive: Dive) -> None:
        stats = analytics.compute(
            dive,
            tank_volume=summary.tank_volume,
            pressure_start=summary.pressure_start,
            pressure_end=summary.pressure_end,
            gradient_factor=self.gf_spin.value() / 100.0,
        )
        self.current_stats = stats
        samples = analytics.effective_samples(dive)

        title = summary.site or T("Plongée n° {number}").format(number=summary.number)
        subtitle = (
            T("{long_datetime} · {label} · {water} · un point toutes les {sample_interval} s").format(long_datetime=dates.long_datetime(summary.started_at), label=dive.mode.label, water=T('eau douce') if dive.salinity == 'fresh' else T('eau de mer'), sample_interval=dive.sample_interval)
        )
        self.dive_title.set_text(f"#{summary.number} · {title}", subtitle)

        self._fill_cards(summary, dive, stats)
        self._fill_plots(dive, samples, stats)
        self._fill_form(summary)
        self._fill_tables(summary, dive, stats)

    def _fill_cards(
        self, summary: DiveSummary, dive: Dive, stats: DiveStats
    ) -> None:
        self.dive_cards.set(
            "max_depth",
            f"{stats.max_depth:.1f} m",
            T("atteinte à {pretty_duration}").format(pretty_duration=pretty_duration(stats.time_to_max_depth)),
        )
        self.dive_cards.set(
            "duration",
            pretty_duration(stats.duration) if stats.duration else "-",
            T("fond {pretty_duration}").format(pretty_duration=pretty_duration(stats.bottom_time)) if stats.bottom_time else "",
        )
        self.dive_cards.set(
            "avg_depth", f"{stats.avg_depth:.1f} m", T("médiane {median_depth:.1f} m").format(median_depth=stats.median_depth)
        )
        self.dive_cards.set(
            "temp",
            f"{stats.temp_min:.1f} °C" if stats.temp_min is not None else "-",
            T("max {temp_max:.1f} °C").format(temp_max=stats.temp_max) if stats.temp_max is not None else "",
        )
        self.dive_cards.set(
            "ascent",
            T("{ascent_rate_max:.1f} m/min").format(ascent_rate_max=stats.ascent_rate_max),
            T("{duration} au-delà de {limit:.0f} m/min").format(
                duration=pretty_duration(stats.fast_ascent_seconds),
                limit=LIMITS.ascent_limit,
            )
            if stats.fast_ascent_seconds
            else T("dans la limite"),
            theme.WARN if stats.ascent_rate_max > LIMITS.ascent_limit else theme.GOOD,
        )
        self.dive_cards.set(
            "safety",
            pretty_duration(stats.safety_stop_seconds)
            if stats.safety_stop_seconds
            else T("aucun"),
            "",
            theme.GOOD if stats.safety_stop_seconds >= 180 else theme.TEXT_MUTED,
        )

        self.dive_cards2.set(
            "gas",
            dive.gas_label,
            T("{gas_switches} changement(s)").format(gas_switches=stats.gas_switches) if stats.gas_switches else "",
        )
        self.dive_cards2.set(
            "ppo2",
            T("{max_ppo2:.2f} bar").format(max_ppo2=stats.max_ppo2) if stats.max_ppo2 else "-",
            T("{duration} au-delà de {limit:g} bar").format(
                duration=pretty_duration(stats.mod_exceeded_seconds),
                limit=LIMITS.ppo2_warn,
            )
            if stats.mod_exceeded_seconds
            else "",
            theme.WARN if stats.max_ppo2 > LIMITS.ppo2_warn else theme.GOOD,
        )
        self.dive_cards2.set("cns", f"{stats.cns:.1f} %" if stats.cns else "-")
        self.dive_cards2.set("otu", f"{stats.otu:.0f}" if stats.otu else "-")
        self.dive_cards2.set(
            "ead", f"{stats.ead_max:.1f} m" if stats.ead_max is not None else "-"
        )
        measured = summary.tank_source in (TankSource.USER.value, TankSource.DEVICE.value)
        if stats.sac and summary.tank_source == TankSource.DEVICE.value:
            sac_hint = T("{used:.0f} L, pressions mesurées").format(used=stats.gas_used)
        elif stats.sac and measured:
            sac_hint = T("{used:.0f} L consommés").format(used=stats.gas_used)
        elif stats.sac:
            sac_hint = T(
                "supposé {volume:.0f} L, {start:.0f}→{end:.0f} bar"
            ).format(
                volume=summary.tank_volume,
                start=summary.pressure_start,
                end=summary.pressure_end,
            )
        else:
            sac_hint = T("à saisir dans le Carnet")
        self.dive_cards2.set(
            "sac",
            T("{sac:.1f} L/min").format(sac=stats.sac) if stats.sac else "-",
            sac_hint,
            None if measured else theme.TEXT_MUTED,
        )

    def _fill_plots(
        self, dive: Dive, samples: list[Sample], stats: DiveStats
    ) -> None:
        self.profile_plot.show_dive(dive, samples, stats)
        self.navigator.show_dive(samples)
        self.rate_plot.show_series(stats.ascent_series)
        self.pressure_plot.show_series(
            stats.pressure_series, measured=any(s.pressure for s in samples)
        )
        self.time_at_depth_plot.show_buckets(
            [(low, seconds / 60.0) for low, seconds in stats.time_at_depth], 3.0
        )
        self.speed_hist_plot.show_buckets(
            [(low, seconds / 60.0) for low, seconds in stats.speed_histogram], 2.0
        )
        self.ppo2_plot.show_series(stats.ppo2_series)
        self.oxygen_plot.show_series(stats.cns_series, stats.otu_series)
        self.tissue_plot.show_series(
            stats.deco.loading_series,
            stats.deco.ceiling_series,
            stats.deco.surface_loading_series,
        )
        self.ead_plot.show_series(samples, stats.ead_series)
        self.tissue_bars.show_loadings(stats.deco.final_loadings)
        self.temp_depth_plot.show_points(stats.temp_vs_depth)

    def _fill_form(self, summary: DiveSummary) -> None:
        self.site_edit.setText(summary.site)
        self.buddy_edit.setText(summary.buddy)
        self.notes_edit.setPlainText(summary.notes)
        self.rating_spin.setValue(summary.rating)
        self.tank_spin.setValue(summary.tank_volume)
        self.start_spin.setValue(summary.pressure_start)
        self.end_spin.setValue(summary.pressure_end)

    def _fill_tables(self, summary: DiveSummary, dive: Dive, stats: DiveStats) -> None:
        self.profile_table.set_rows(
            [
                (T("Début"), dates.long_datetime(dive.datetime)),
                (T("Fin"), f"{dive.end_datetime:%H:%M}"),
                (T("Durée"), pretty_duration(dive.duration)),
                (T("Mode"), dive.mode.label),
                (T("Profondeur max (entête)"), f"{dive.max_depth:.1f} m"),
                (T("Profondeur max (profil)"), f"{stats.max_depth:.1f} m"),
                (T("Profondeur moyenne (entête)"), f"{dive.avg_depth:.1f} m"),
                (T("Profondeur moyenne (profil)"), f"{stats.avg_depth:.1f} m"),
                (T("Profondeur médiane"), f"{stats.median_depth:.1f} m"),
                (T("Temps au fond (> 80 % du max)"), pretty_duration(stats.bottom_time)),
                (T("Temps pour atteindre le fond"), pretty_duration(stats.time_to_max_depth)),
                (T("Durée de la remontée"), pretty_duration(stats.ascent_duration)),
                (T("Palier 3-6 m"), pretty_duration(stats.safety_stop_seconds)),
                (T("Vitesse de descente max"), T("{descent_rate_max:.1f} m/min").format(descent_rate_max=stats.descent_rate_max)),
                (T("Vitesse de descente moyenne"), T("{descent_rate_avg:.1f} m/min").format(descent_rate_avg=stats.descent_rate_avg)),
                (T("Vitesse de remontée max"), T("{ascent_rate_max:.1f} m/min").format(ascent_rate_max=stats.ascent_rate_max)),
                (T("Vitesse de remontée moyenne"), T("{ascent_rate_avg:.1f} m/min").format(ascent_rate_avg=stats.ascent_rate_avg)),
                (
                    T("Temps en remontée trop rapide"),
                    pretty_duration(stats.fast_ascent_seconds),
                ),
                (T("Cumul descendu"), f"{stats.total_descent:.0f} m"),
                (T("Cumul remonté"), f"{stats.total_ascent:.0f} m"),
                (T("Aller-retours verticaux (> 4 m)"), str(stats.yoyo_count)),
                (T("Intégrale profondeur-temps"), T("{depth_profile_area:.0f} m.min").format(depth_profile_area=stats.depth_profile_area)),
                (
                    T("Température"),
                    T("{temp_min:.1f} à {temp_max:.1f} °C (moyenne {temp_avg:.1f} °C)").format(temp_min=stats.temp_min, temp_max=stats.temp_max, temp_avg=stats.temp_avg)
                    if stats.temp_avg is not None
                    else "-",
                ),
                (
                    T("Température au plus profond"),
                    f"{stats.temp_at_max_depth:.1f} °C"
                    if stats.temp_at_max_depth is not None
                    else "-",
                ),
                (
                    T("Thermocline"),
                    T("vers {thermocline_depth:.1f} m").format(thermocline_depth=stats.thermocline_depth)
                    if stats.thermocline_depth
                    else T("non marquée"),
                ),
            ]
        )
        self.gas_table.set_rows(self._gas_rows(summary, dive, stats))
        self.device_table.set_rows(
            [
                (T("Ordinateur"), dive.device_model),
                (T("Numéro de série"), dive.device_serial),
                (T("Intervalle d'échantillonnage"), f"{dive.sample_interval} s"),
                (T("Échantillons enregistrés"), str(len(dive.samples))),
                (T("Échantillons utiles"), str(len(analytics.effective_samples(dive)))),
                (
                    T("Unités de l'ordinateur"),
                    T("métriques") if dive.units_metric else T("impériales"),
                ),
                (T("Réglages (brut)"), f"0x{dive.settings:04X}"),
                (T("Empreinte matérielle"), dive.fingerprint),
                (T("Identifiant interne"), summary.uid),
                (T("Taille de l'enregistrement"), T("{len} octets").format(len=len(dive.raw))),
                (T("Note"), f"{summary.rating} / 5" if summary.rating else "-"),
                (T("Binôme"), summary.buddy or "-"),
            ]
        )

    def _gas_rows(
        self, summary: DiveSummary, dive: Dive, stats: DiveStats
    ) -> list[tuple[str, str]]:
        rows: list[tuple[str, str]] = []
        for index, mix in enumerate(dive.gasmixes, start=1):
            rows.append(
                (
                    T("Mélange {index}").format(index=index),
                    T("{label} — MOD 1,4 : {mod_1_4:.1f} m · MOD 1,6 : {mod_1_6:.1f} m").format(label=mix.label, mod_1_4=mix.mod_1_4, mod_1_6=mix.mod_1_6),
                )
            )
        rows += [
            (T("Changements de gaz"), str(stats.gas_switches)),
            (T("ppO2 minimale"), T("{min_ppo2:.2f} bar").format(min_ppo2=stats.min_ppo2) if stats.min_ppo2 else "-"),
            (T("ppO2 maximale"), T("{max_ppo2:.2f} bar").format(max_ppo2=stats.max_ppo2) if stats.max_ppo2 else "-"),
            (
                T("Temps au-delà de {limit:g} bar").format(limit=LIMITS.ppo2_warn),
                pretty_duration(stats.mod_exceeded_seconds),
            ),
            (
                T("Temps au-delà de {limit:g} bar").format(limit=LIMITS.ppo2_max),
                pretty_duration(stats.mod_critical_seconds),
            ),
            (T("Charge CNS"), f"{stats.cns:.1f} %"),
            (T("OTU"), f"{stats.otu:.0f}"),
            (
                T("Profondeur équivalente air max"),
                f"{stats.ead_max:.1f} m" if stats.ead_max is not None else "-",
            ),
            (T("Pression atmosphérique"), T("{atmospheric:.3f} bar").format(atmospheric=dive.atmospheric)),
            (T("Eau"), T("douce") if dive.salinity == "fresh" else T("mer")),
        ]
        if summary.tank_volume:
            suffix = {
                TankSource.USER.value: "",
                TankSource.DEVICE.value: T(" (mesuré par l'ordinateur)"),
            }.get(summary.tank_source, T(" (valeur par défaut)"))
            rows += [
                (T("Bloc"), f"{summary.tank_volume:.1f} L{suffix}"),
                (
                    T("Pressions"),
                    T("{pressure_start:.0f} → {pressure_end:.0f} bar").format(pressure_start=summary.pressure_start, pressure_end=summary.pressure_end),
                ),
                (T("Gaz consommé"), f"{stats.gas_used:.0f} L" if stats.gas_used else "-"),
                (T("Consommation (SAC)"), T("{sac:.1f} L/min").format(sac=stats.sac) if stats.sac else "-"),
            ]
        profile = stats.deco
        rows += [
            (T("— Modèle ZH-L16C —"), T("facteur de gradient {value} %").format(value=self.gf_spin.value())),
            (T("Sursaturation maximale"), T("{max_loading:.1f} % de la M-value").format(max_loading=profile.max_loading)),
            (
                T("Compartiment directeur"),
                T("n° {index} ({halflife:g} min)").format(
                    index=profile.leading_compartment + 1,
                    halflife=profile.leading_halflife,
                ),
            ),
            (
                T("Plafond théorique max"),
                f"{profile.max_ceiling:.1f} m" if profile.max_ceiling else T("aucun"),
            ),
            (T("Temps avec plafond"), pretty_duration(profile.deco_seconds)),
            (
                T("Désaturation estimée"),
                T("{pretty_duration} (retour à 2 % de l'équilibre)").format(pretty_duration=pretty_duration(profile.desaturation_minutes * 60))
                if profile.desaturation_minutes
                else "-",
            ),
        ]
        return rows

    def _on_gradient_factor_changed(self) -> None:
        if self.current is not None and self.current_dive is not None:
            self._show_dive(self.current, self.current_dive)

    # -- navigation temporelle ---------------------------------------------

    def _on_navigator_moved(self, start: float, end: float) -> None:
        if self._syncing_range or end <= start:
            return
        self._syncing_range = True
        self.profile_plot.item.setXRange(start, end, padding=0)
        self._syncing_range = False

    def _on_profile_range_changed(self, _view, view_range) -> None:
        if self._syncing_range:
            return
        self._syncing_range = True
        self.navigator.set_window(view_range[0], view_range[1])
        self._syncing_range = False

    # -- statistiques globales ----------------------------------------------

    def _update_dashboard(self, rows: list[DiveSummary]) -> None:
        overview = analytics.compute_overview(rows)
        if not rows:
            self.overview_cards.reset()
            self.overview_cards2.reset()
            self._clear_dashboard_charts()
            self.records_table.set_rows([])
            return
        self._fill_overview_cards(overview)
        self._fill_dashboard_charts(overview)
        self.records_table.set_rows(self._records_rows(overview, rows))

    def _clear_dashboard_charts(self) -> None:
        for chart in (
            self.per_month_chart,
            self.per_year_chart,
            self.per_weekday_chart,
            self.per_hour_chart,
            self.depth_distribution,
            self.duration_distribution,
            self.sites_chart,
        ):
            chart.show_values([], [])
        for trend in (
            self.depth_trend,
            self.avg_depth_trend,
            self.duration_trend,
            self.temp_trend,
            self.cumulative_trend,
            self.cumulative_dives_trend,
            self.rolling_trend,
            self.sac_trend,
            self.interval_chart,
        ):
            trend.show_series([])
        self.global_time_at_depth.show_buckets([])
        self.duration_depth_scatter.show_points([])

    def _fill_overview_cards(self, overview: Overview) -> None:
        cards = self.overview_cards
        cards.set(
            "dives",
            str(overview.total_dives),
            T("depuis le {started_at:%d/%m/%Y}").format(started_at=overview.first.started_at) if overview.first else "",
        )
        cards.set(
            "time",
            overview.total_duration_label,
            T("plus longue {duration_label}").format(duration_label=overview.longest.duration_label) if overview.longest else "",
        )
        cards.set(
            "max_depth",
            f"{overview.max_depth:.1f} m",
            (overview.deepest.site or f"{overview.deepest.started_at:%d/%m/%Y}")
            if overview.deepest
            else "",
        )
        cards.set("avg_depth", f"{overview.avg_depth:.1f} m")
        cards.set("avg_duration", pretty_duration(overview.avg_duration))
        cards.set(
            "coldest",
            f"{overview.coldest.temp_min:.1f} °C"
            if overview.coldest and overview.coldest.temp_min is not None
            else "-",
            overview.coldest.site if overview.coldest else "",
        )

        cards2 = self.overview_cards2
        cards2.set("avg_max", f"{overview.avg_max_depth:.1f} m")
        cards2.set("descent", f"{overview.total_descent:.0f} m", T("profondeurs max cumulées"))
        cards2.set("streak", str(overview.longest_streak), T("jours consécutifs"))
        cards2.set(
            "rolling",
            str(int(overview.rolling_year[-1][1])) if overview.rolling_year else "-",
            T("12 mois glissants"),
        )
        cards2.set("sites", str(len(overview.per_site)) if overview.per_site else "-")
        cards2.set(
            "last",
            dates.short_date(overview.last.started_at) if overview.last else "-",
            self._days_since(overview.last),
        )

    @staticmethod
    def _days_since(summary: DiveSummary | None) -> str:
        if summary is None:
            return ""
        days = (_dt.datetime.now() - summary.started_at).days
        if days <= 0:
            return T("aujourd'hui")
        return count_label(days, "il y a {count} jour", "il y a {count} jours")

    def _fill_dashboard_charts(self, overview: Overview) -> None:
        self.per_month_chart.show_values(
            [dates.month_label(label) for label, _ in overview.per_month],
            [float(count) for _, count in overview.per_month],
        )
        self.per_year_chart.show_values(
            [str(year) for year, _ in overview.per_year],
            [float(count) for _, count in overview.per_year],
        )
        self.per_weekday_chart.show_values(
            [label for label, _ in overview.per_weekday],
            [float(count) for _, count in overview.per_weekday],
        )
        self.per_hour_chart.show_values(
            [f"{hour}h" for hour, _ in overview.per_hour],
            [float(count) for _, count in overview.per_hour],
        )
        self.depth_distribution.show_values(
            [f"{int(low)}-{int(low) + 10} m" for low, _ in overview.depth_buckets],
            [float(count) for _, count in overview.depth_buckets],
        )
        self.duration_distribution.show_values(
            [f"{int(low)}-{int(low) + 10}" for low, _ in overview.duration_buckets],
            [float(count) for _, count in overview.duration_buckets],
        )
        self.sites_chart.show_values(
            [site for site, _ in overview.per_site],
            [float(count) for _, count in overview.per_site],
        )

        self.depth_trend.show_series(overview.depth_progression)
        self.avg_depth_trend.show_series(overview.avg_depth_progression)
        self.duration_trend.show_series(overview.duration_progression)
        self.temp_trend.show_series(overview.temp_progression)
        self.cumulative_trend.show_series(overview.cumulative, with_trend=False)
        self.cumulative_dives_trend.show_series(overview.cumulative_dives, with_trend=False)
        self.rolling_trend.show_series(overview.rolling_year, with_trend=False)
        self.sac_trend.show_series(overview.sac_progression)
        self.interval_chart.show_series(overview.surface_intervals, with_trend=False)

        self.global_time_at_depth.show_buckets(
            [(low, seconds / 60.0) for low, seconds in self.db.depth_histogram()], 3.0
        )
        self.duration_depth_scatter.show_points(overview.duration_vs_depth)

    def _records_rows(
        self, overview: Overview, rows: list[DiveSummary]
    ) -> list[tuple[str, str]]:
        def describe(summary: DiveSummary | None, value: str) -> str:
            if summary is None:
                return "-"
            place = summary.site or T("plongée n° {number}").format(number=summary.number)
            return f"{value} · {place} · {summary.started_at:%d/%m/%Y}"

        ordered = sorted(rows, key=lambda s: s.started_at)
        gaps: list[tuple[int, DiveSummary]] = []
        for previous, current in zip(ordered, ordered[1:]):
            gap = analytics.surface_interval(previous, current)
            if gap is not None and gap < 6 * 3600:
                gaps.append((gap, current))

        out = [
            (
                T("Plus profonde"),
                describe(overview.deepest, f"{overview.deepest.max_depth:.1f} m")
                if overview.deepest
                else "-",
            ),
            (
                T("Plus longue"),
                describe(overview.longest, overview.longest.duration_label)
                if overview.longest
                else "-",
            ),
            (
                T("Eau la plus froide"),
                describe(
                    overview.coldest,
                    f"{overview.coldest.temp_min:.1f} °C"
                    if overview.coldest and overview.coldest.temp_min is not None
                    else "-",
                ),
            ),
            (
                T("Eau la plus chaude"),
                describe(
                    overview.warmest,
                    f"{overview.warmest.temp_max:.1f} °C"
                    if overview.warmest and overview.warmest.temp_max is not None
                    else "-",
                ),
            ),
            (
                T("Première plongée"),
                dates.long_date(overview.first.started_at) if overview.first else "-",
            ),
            (
                T("Dernière plongée"),
                dates.long_date(overview.last.started_at) if overview.last else "-",
            ),
            (T("Profondeur maximale moyenne"), f"{overview.avg_max_depth:.1f} m"),
            (T("Cumul des profondeurs max"), f"{overview.total_descent:.0f} m"),
            (T("Temps immergé total"), overview.total_duration_label),
            (T("Durée moyenne"), pretty_duration(overview.avg_duration)),
            (T("Jours consécutifs (record)"), str(overview.longest_streak)),
            (
                T("Journée la plus chargée"),
                count_label(
                    overview.busiest_day[1],
                    "{count} plongée le {date:%d/%m/%Y}",
                    "{count} plongées le {date:%d/%m/%Y}",
                    date=overview.busiest_day[0],
                )
                if overview.busiest_day
                else "-",
            ),
            (T("Modes utilisés"), ", ".join(f"{m} ({n})" for m, n in overview.modes)),
            (T("Mélanges utilisés"), ", ".join(f"{g} ({n})" for g, n in overview.gases)),
            (
                T("Plongées successives"),
                T("{len} avec moins de 6 h d'intervalle").format(len=len(gaps))
                + (
                    T(" · plus court : {pretty_duration}").format(pretty_duration=pretty_duration(min((g for g, _ in gaps))))
                    if gaps
                    else ""
                ),
            ),
        ]
        if overview.per_year:
            out.append(
                (
                    T("Par année"),
                    ", ".join(f"{year} : {count}" for year, count in overview.per_year),
                )
            )
        if overview.per_site:
            out.append(
                (
                    T("Sites les plus plongés"),
                    ", ".join(
                        f"{site} ({count})" for site, count in overview.per_site[:5]
                    ),
                )
            )
        return out

    def _update_history(self) -> None:
        rows = [
            (
                row["at"][:16].replace("T", " "),
                row["message"]
                + (f" — s/n {row['device_serial']}" if row["device_serial"] else ""),
            )
            for row in self.db.import_history(30)
        ]
        self.history_table.set_rows(rows or [(T("Aucun import"), "-")])

    # -- actions ------------------------------------------------------------

    def start_import(self, full: bool = False) -> None:
        if self.worker is not None and self.worker.isRunning():
            return
        demo = self.demo_check.isChecked()
        port = self.port_combo.currentData()
        if not demo and not port:
            QtWidgets.QMessageBox.warning(
                self,
                T("Aucun port"),
                T(
                    "Aucun port série n'est sélectionné. Branchez le câble USB "
                    "Mares puis cliquez sur Rafraîchir, ou cochez le mode démo."
                ),
            )
            return
        if port and self.settings.remember_port and port != self.settings.last_port:
            self.settings.last_port = port
            self._save_settings()

        self._set_busy(True)
        self.status.showMessage(T("Connexion à l'ordinateur…"))
        self.worker = ImportWorker(
            self.db.path,
            port,
            demo=demo,
            demo_model=self.settings.demo_model,
            full=full,
            settings=self.settings,
            parent=self,
        )
        self.worker.progress.connect(self._on_progress)
        self.worker.succeeded.connect(self._on_import_done)
        self.worker.failed.connect(self._on_import_failed)
        self.worker.finished.connect(lambda: self._set_busy(False))
        self.worker.start()

    def _set_busy(self, busy: bool) -> None:
        self.import_button.setEnabled(not busy)
        self.full_button.setEnabled(not busy)
        self.progress.setVisible(busy)
        if busy:
            self.progress.setRange(0, 0)

    def _on_progress(self, step: str, done: int, total: object) -> None:
        self.status.showMessage(step)
        if isinstance(total, int) and total > 0:
            self.progress.setRange(0, total)
            self.progress.setValue(done)

    def _on_import_done(self, result: ImportResult) -> None:
        self.status.showMessage(result.message, 15000)
        select = result.added[-1].uid if result.added else None
        self.reload(select_uid=select)
        if result.errors:
            QtWidgets.QMessageBox.warning(
                self,
                T("Import partiel"),
                T("Certains enregistrements n'ont pas pu être lus :")
                + "\n\n"
                + "\n".join(result.errors[:10]),
            )

    def _on_import_failed(self, message: str, details: str) -> None:
        self.status.showMessage(T("Import en échec."), 10000)
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Critical)
        box.setWindowTitle(T("Import impossible"))
        box.setText(message)
        if details:
            box.setDetailedText(details)
        box.exec()

    def save_annotations(self) -> None:
        if self.current is None:
            return
        self.db.update_annotations(
            self.current.uid,
            site=self.site_edit.text().strip(),
            buddy=self.buddy_edit.text().strip(),
            notes=self.notes_edit.toPlainText().strip(),
            rating=self.rating_spin.value(),
            tank_volume=self.tank_spin.value(),
            pressure_start=self.start_spin.value(),
            pressure_end=self.end_spin.value(),
        )
        self.status.showMessage(T("Notes enregistrées."), 4000)
        self.reload(select_uid=self.current.uid)

    def _selected_summaries(self) -> list[DiveSummary]:
        rows = sorted(
            {self.proxy.mapToSource(index).row() for index in self.table.selectionModel().selectedRows()}
        )
        summaries = (self.model.summary_at(row) for row in rows)
        return [summary for summary in summaries if summary is not None]

    def _on_context_menu(self, position: QtCore.QPoint) -> None:
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        # Un clic droit hors de la selection courante la remplace par la ligne visee,
        # comme le fait l'Explorateur de fichiers.
        if not self.table.selectionModel().isSelected(index):
            self.table.setCurrentIndex(index)
            self.table.selectionModel().select(
                index,
                QtCore.QItemSelectionModel.SelectionFlag.ClearAndSelect
                | QtCore.QItemSelectionModel.SelectionFlag.Rows,
            )
        summaries = self._selected_summaries()
        if not summaries:
            return
        menu = QtWidgets.QMenu(self)
        if len(summaries) > 1:
            hide = menu.addAction(
                T("Masquer ces {len} plongées (ne plus les importer)").format(len=len(summaries))
            )
        else:
            hide = menu.addAction(T("Masquer cette plongée (ne plus l'importer)"))
        menu.addSeparator()
        manage = menu.addAction(T("Gérer les plongées masquées…"))
        chosen = menu.exec(self.table.viewport().mapToGlobal(position))
        if chosen is hide:
            self.hide_dives(summaries)
        elif chosen is manage:
            self.open_hidden_dialog()

    def hide_dives(self, summaries: list[DiveSummary]) -> None:
        """Retire une ou plusieurs plongees du carnet et interdit leur reimportation."""
        if not summaries:
            return
        if len(summaries) == 1:
            summary = summaries[0]
            question = (
                T("Masquer la plongée du {started_at:%d/%m/%Y à %H:%M} ({max_depth:.1f} m) ?\n\nElle disparaît du carnet et ne sera plus réimportée, même avec « Tout relire ». Pratique pour les plongées de l'ancien propriétaire d'un ordinateur d'occasion.\n\nElle reste dans la mémoire de l'ordinateur, et le bouton « Masquées » permet de revenir en arrière.").format(started_at=summary.started_at, max_depth=summary.max_depth)
            )
        else:
            question = (
                T("Masquer ces {len} plongées ?\n\nElles disparaissent du carnet et ne seront plus réimportées, même avec « Tout relire ». Pratique pour les plongées de l'ancien propriétaire d'un ordinateur d'occasion.\n\nElles restent dans la mémoire de l'ordinateur, et le bouton « Masquées » permet de revenir en arrière.").format(len=len(summaries))
            )
        if self.settings.confirm_hide:
            confirm = QtWidgets.QMessageBox.question(
                self, T("Masquer la plongée"), question
            )
            if confirm is not QtWidgets.QMessageBox.StandardButton.Yes:
                return
        for summary in summaries:
            self.db.hide_dive(summary.uid)
        self.current = None
        message = (
            T("Plongée masquée ; elle ne sera plus importée.")
            if len(summaries) == 1
            else T("{len} plongées masquées ; elles ne seront plus importées.").format(len=len(summaries))
        )
        self.status.showMessage(message, 6000)
        self.reload()

    def open_hidden_dialog(self) -> None:
        dialog = HiddenDivesDialog(self.db, self)
        dialog.exec()
        if dialog.restored:
            self.reload()

    def import_csv(self) -> None:
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, T("Importer un carnet CSV"), str(self.settings.exports), "CSV (*.csv)"
        )
        if not path:
            return
        try:
            result = parse_csv_file(path)
        except CsvFormatError as exc:
            QtWidgets.QMessageBox.warning(self, "Import CSV", str(exc))
            return
        if not result.rows:
            message = T("Aucune plongée exploitable dans ce fichier.")
            if result.errors:
                message += "\n\n" + "\n".join(result.errors[:10])
            QtWidgets.QMessageBox.information(self, T("Import CSV"), message)
            return
        annotate_known(self.db, result)

        dialog = CsvImportDialog(result, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        chosen = dialog.selected_rows()
        if not chosen:
            return
        self._on_import_done(import_rows(self.db, chosen))

    def export_csv(self) -> None:
        rows = self.db.list_dives(order="asc")
        if not rows:
            QtWidgets.QMessageBox.information(self, T("Export"), T("Aucune plongée à exporter."))
            return
        default = str(
            self.settings.exports
            / T("plongees-{today:%Y%m%d}.csv").format(today=_dt.date.today())
        )
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, T("Exporter le carnet"), default, "CSV (*.csv)"
        )
        if not path:
            return
        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(
                [
                    "numero", "date", "heure", "mode", "duree_s", "duree",
                    "prof_max_m", "prof_moy_m", "temp_min_c", "temp_max_c",
                    "melanges", "eau", "site", "binome", "note", "bloc_l",
                    "pression_depart_bar", "pression_fin_bar", "commentaire",
                ]
            )
            for row in rows:
                writer.writerow(
                    [
                        row.number,
                        f"{row.started_at:%Y-%m-%d}",
                        f"{row.started_at:%H:%M}",
                        row.mode.label,
                        row.duration,
                        row.duration_label,
                        f"{row.max_depth:.1f}",
                        f"{row.avg_depth:.1f}" if row.avg_depth else "",
                        f"{row.temp_min:.1f}" if row.temp_min is not None else "",
                        f"{row.temp_max:.1f}" if row.temp_max is not None else "",
                        row.gas_label,
                        "douce" if row.salinity == "fresh" else "mer",
                        row.site,
                        row.buddy,
                        row.rating or "",
                        f"{row.tank_volume:.1f}" if row.tank_volume else "",
                        f"{row.pressure_start:.0f}" if row.pressure_start else "",
                        f"{row.pressure_end:.0f}" if row.pressure_end else "",
                        row.notes.replace("\n", " "),
                    ]
                )
        self.status.showMessage(T("Carnet exporté vers {path}").format(path=path), 8000)

    def export_profile_csv(self) -> None:
        """Exporte toutes les series calculees de la plongee affichee."""
        if self.current is None or self.current_dive is None or self.current_stats is None:
            QtWidgets.QMessageBox.information(
                self, T("Export"), T("Sélectionnez d'abord une plongée.")
            )
            return
        dive = self.current_dive
        stats = self.current_stats
        default = str(
            self.settings.exports
            / T("profil-{datetime:%Y%m%d-%H%M}.csv").format(datetime=dive.datetime)
        )
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, T("Exporter le profil"), default, "CSV (*.csv)"
        )
        if not path:
            return

        rates = dict(stats.ascent_series)
        ppo2 = dict(stats.ppo2_series)
        cns = dict(stats.cns_series)
        otu = dict(stats.otu_series)
        ead = dict(stats.ead_series)
        pressure = dict(stats.pressure_series)
        ceiling = dict(stats.deco.ceiling_series)
        loading = dict(stats.deco.loading_series)

        with open(path, "w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.writer(handle, delimiter=";")
            writer.writerow(
                [
                    "temps_s", "profondeur_m", "temperature_c", "melange",
                    "vitesse_m_min", "ppo2_bar", "cns_pct", "otu",
                    "prof_equiv_air_m", "pression_bar", "plafond_m",
                    "sursaturation_pct",
                ]
            )
            for sample in analytics.effective_samples(dive):
                writer.writerow(
                    [
                        sample.time,
                        f"{sample.depth:.1f}",
                        f"{sample.temperature:.1f}"
                        if sample.temperature is not None
                        else "",
                        sample.gasmix if sample.gasmix is not None else "",
                        f"{rates.get(sample.time, 0.0):.2f}",
                        f"{ppo2.get(sample.time, 0.0):.3f}",
                        f"{cns.get(sample.time, 0.0):.2f}",
                        f"{otu.get(sample.time, 0.0):.2f}",
                        f"{ead.get(sample.time, 0.0):.1f}",
                        f"{pressure.get(sample.time, 0.0):.1f}" if pressure else "",
                        f"{ceiling.get(sample.time, 0.0):.2f}",
                        f"{loading.get(sample.time, 0.0):.1f}",
                    ]
                )
        self.status.showMessage(T("Profil exporté vers {path}").format(path=path), 8000)

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # noqa: N802
        if self.settings.remember_geometry:
            self.settings.geometry = bytes(
                self.saveGeometry().toBase64()
            ).decode("ascii")
            self._save_settings()
        if self.worker is not None and self.worker.isRunning():
            self.worker.wait(3000)
        self.db.close()
        super().closeEvent(event)

    # -- reglages et aide ---------------------------------------------------

    def _save_settings(self) -> None:
        """Ecrit les reglages sans jamais faire echouer l'action en cours."""
        try:
            self.settings.save()
        except OSError as exc:  # pragma: no cover - disque plein, droits...
            log.warning("Réglages non enregistrés : %s", exc)

    def _restore_geometry(self) -> None:
        if not (self.settings.remember_geometry and self.settings.geometry):
            return
        try:
            data = QtCore.QByteArray.fromBase64(self.settings.geometry.encode("ascii"))
            self.restoreGeometry(data)
        except (ValueError, TypeError) as exc:  # pragma: no cover - reglage abime
            log.warning("Géométrie de fenêtre illisible : %s", exc)

    def open_settings(self) -> None:
        """Ouvre les parametres et applique tout de suite ce qui peut l'etre."""
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != QtWidgets.QDialog.DialogCode.Accepted:
            return
        self.settings = dialog.draft
        config.apply(self.settings)
        self.refresh_ports()
        self.reload(select_uid=self.current.uid if self.current else None)
        if dialog.needs_restart:
            QtWidgets.QMessageBox.information(
                self,
                T("Paramètres"),
                T(
                    "Enregistré. La langue, le thème et la base de plongées "
                    "s'appliqueront au prochain démarrage."
                ),
            )
        else:
            self.status.showMessage(T("Paramètres enregistrés."), 5000)

    def show_connection_help(self) -> None:
        """Rappelle la marche a suivre pour brancher l'ordinateur."""
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        box.setWindowTitle(T("Brancher mon ordinateur"))
        box.setTextFormat(QtCore.Qt.TextFormat.RichText)
        box.setText(T(CONNECTION_HELP))
        box.exec()

    def show_diagnostic(self) -> None:
        """Affiche versions, chemins et ports: de quoi demander de l'aide."""
        report = config.diagnostic().as_text()
        box = QtWidgets.QMessageBox(self)
        box.setIcon(QtWidgets.QMessageBox.Icon.Information)
        box.setWindowTitle(T("Diagnostic"))
        box.setText(T("Copiez ce texte pour toute demande d'aide."))
        box.setDetailedText(report)
        copy = box.addButton(T("Copier"), QtWidgets.QMessageBox.ButtonRole.ActionRole)
        box.addButton(QtWidgets.QMessageBox.StandardButton.Close)
        box.exec()
        if box.clickedButton() is copy:
            clipboard = QtWidgets.QApplication.clipboard()
            if clipboard is not None:
                clipboard.setText(report)

    def show_about(self) -> None:
        QtWidgets.QMessageBox.about(
            self,
            T("À propos de Thermocline"),
            T(ABOUT_TEXT).format(version=__version__),
        )
