"""Graphiques pyqtgraph.

Tous les graphiques heritent de `PlotPanel` et partagent les memes
interactions: molette pour zoomer, glisser pour deplacer, double-clic ou
bouton « Ajuster » pour revenir a la vue complete, clic droit pour le menu
pyqtgraph (export PNG/CSV, echelles, etc.).

Les graphiques dont l'abscisse est le temps de plongee heritent en plus de
`TimeSeriesPanel`: leur axe peut etre synchronise et ils partagent un curseur
de lecture commun.
"""

from __future__ import annotations

import datetime as _dt
from collections.abc import Iterable, Sequence

import pyqtgraph as pg
from PyQt6 import QtCore, QtGui, QtWidgets

from ..i18n import T
from ..analytics import LIMITS, DiveStats
from ..deco import NCOMPARTMENTS, N2_HALFLIVES
from ..models import Dive, DiveMode, Sample
from . import theme

pg.setConfigOptions(antialias=True, background=theme.PANEL, foreground=theme.TEXT_MUTED)

DASH = QtCore.Qt.PenStyle.DashLine
DOT = QtCore.Qt.PenStyle.DotLine

# -- textes d'aide affiches au survol --------------------------------------

PROFILE_TOOLTIP = """<b>Profil de la plongée</b><br>
<span style="color:#38bdf8">■</span> profondeur (axe de gauche, inversé)<br>
<span style="color:#fb923c">■</span> température (axe de droite)<br>
<span style="color:#22c55e">■</span> bande verte : zone du palier de sécurité, 3 à 6 m<br>
<span style="color:#f87171">▲</span> remontée plus rapide que 10 m/min<br>
● point blanc : profondeur maximale<br>
<span style="color:#f87171">┄</span> plafond théorique, quand le modèle en impose un<br>
<i>Molette pour zoomer, double-clic pour tout réafficher.</i>"""

RATE_TOOLTIP = """<b>Vitesse verticale</b>, lissée sur 30 secondes.<br>
Au-dessus de zéro : remontée. En dessous : descente.<br>
La limite de 10 m/min est celle que Mares recommande à la remontée ;
18 m/min est un repère de descente confortable."""

PRESSURE_TOOLTIP = """<b>Pression du bloc</b><br>
Sur les modèles à intégration d'air, la courbe est <b>mesurée</b> par
l'ordinateur.<br>
Ailleurs elle est <b>reconstituée</b> à partir du volume du bloc, des pressions
saisies dans l'onglet Carnet et de la profondeur instantanée, en supposant une
consommation régulière : c'est une estimation, pas une mesure."""

TIME_AT_DEPTH_TOOLTIP = """<b>Temps par tranche de 3 m</b><br>
Durée cumulée passée dans chaque tranche de profondeur. Un profil carré
concentre tout sur une ou deux barres ; un profil multiniveaux les étale."""

SPEED_HISTOGRAM_TOOLTIP = """<b>Répartition des vitesses verticales</b><br>
Temps passé à chaque vitesse. Une plongée maîtrisée se concentre autour de
zéro, avec une queue limitée au-delà de 10 m/min."""

PPO2_TOOLTIP = """<b>Pression partielle d'oxygène</b><br>
ppO2 = fraction d'O2 du mélange × pression absolue.<br>
<span style="color:#f87171">┄</span> <b>1,4 bar</b> : limite habituelle au fond en plongée loisir.<br>
<span style="color:#dc2626">┄</span> <b>1,6 bar</b> : limite d'exception, réservée à la décompression.<br>
Au-delà, le risque de crise hyperoxique augmente nettement."""

OXYGEN_TOOLTIP = """<b>Exposition cumulée à l'oxygène</b> (limites NOAA)<br>
<span style="color:#f87171">■</span> <b>CNS</b> : part consommée de la dose maximale de toxicité
neurologique. 100 % correspond à la limite d'exposition unique ; la charge se
cumule d'une plongée à l'autre et décroît en surface.<br>
<span style="color:#fb923c">■</span> <b>OTU</b> : unités de toxicité pulmonaire. Repères usuels :
300 par jour, 850 sur une semaine.<br>
Rien ne s'accumule tant que la ppO2 reste sous 0,5 bar."""

TISSUE_TOOLTIP = """<b>Saturation des tissus — Bühlmann ZH-L16C</b><br>
16 compartiments théoriques, de 4 à 635 minutes de demi-vie.<br><br>
<span style="color:#4ade80">■</span> <b>À la profondeur courante</b> : sursaturation du
compartiment le plus contraignant, là où vous êtes. Elle reste basse tant que
vous descendez ou restez au fond, car la pression ambiante est élevée.<br>
<span style="color:#38bdf8">┄</span> <b>Si remontée immédiate</b> : sursaturation que vous
auriez en rejoignant la surface tout de suite. C'est elle qui indique si la
remontée directe reste possible.<br>
<span style="color:#f87171">━</span> <b>Plafond</b> (axe de droite) : profondeur minimale
tolérée à cet instant. Zéro signifie remontée directe autorisée.<br><br>
<b>100 % = M-value</b>, seuil théorique de tolérance du modèle. Le facteur de
gradient abaisse ce seuil : 100 % = limites brutes, 70 % = 30 % de marge."""

TISSUE_BARS_TOOLTIP = """<b>Charge des 16 compartiments à la sortie de l'eau</b><br>
Pour chaque compartiment, sa sursaturation en surface, en % de sa M-value.<br>
Les compartiments rapides (à gauche, 4 à 27 min) se chargent et se vident en
quelques dizaines de minutes ; les lents (à droite) gardent l'azote plusieurs
heures et pilotent l'intervalle avant l'avion.<br>
<span style="color:#4ade80">■</span> sous 60 % &nbsp;
<span style="color:#fb923c">■</span> 60 à 85 % &nbsp;
<span style="color:#f87171">■</span> 85 % et plus"""

EAD_TOOLTIP = """<b>Profondeur équivalente air</b><br>
Profondeur à laquelle on respirerait la même pression partielle d'azote en
respirant de l'air. Avec un nitrox elle est inférieure à la profondeur réelle,
et c'est ce gain qui allonge la durée sans palier."""

TEMP_DEPTH_TOOLTIP = """<b>Température en fonction de la profondeur</b><br>
Chaque point est un échantillon du profil. Une rupture de pente marque une
thermocline ; un nuage dédoublé indique que l'eau s'est réchauffée entre la
descente et la remontée."""


def _pen(color: str, width: float = 1.6, style: QtCore.Qt.PenStyle | None = None) -> QtGui.QPen:
    pen = pg.mkPen(color=color, width=width)
    if style is not None:
        pen.setStyle(style)
    return pen


# -- axes ------------------------------------------------------------------


class TimeAxis(pg.AxisItem):
    """Axe temporel en minutes:secondes, a partir de secondes."""

    def tickStrings(self, values, scale, spacing):  # noqa: N802 (API pyqtgraph)
        out = []
        for value in values:
            total = int(value)
            sign = "-" if total < 0 else ""
            total = abs(total)
            if spacing >= 60:
                out.append(f"{sign}{total // 60}")
            else:
                out.append(f"{sign}{total // 60}:{total % 60:02d}")
        return out


class DateAxis(pg.AxisItem):
    """Axe temporel en dates, a partir d'horodatages Unix."""

    def tickStrings(self, values, scale, spacing):  # noqa: N802
        out = []
        for value in values:
            try:
                moment = _dt.datetime.fromtimestamp(value)
            except (OverflowError, OSError, ValueError):
                out.append("")
                continue
            if spacing > 86400 * 300:
                out.append(f"{moment:%Y}")
            elif spacing > 86400 * 45:
                out.append(f"{moment:%m/%y}")
            elif spacing > 86400:
                out.append(f"{moment:%d/%m}")
            else:
                out.append(f"{moment:%d/%m %Hh}")
        return out


class LabelAxis(pg.AxisItem):
    """Axe categoriel: une etiquette par position entiere."""

    def __init__(self, labels: Sequence[str] = (), *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.labels = list(labels)

    def tickStrings(self, values, scale, spacing):  # noqa: N802
        out = []
        for value in values:
            index = int(round(value))
            out.append(self.labels[index] if 0 <= index < len(self.labels) else "")
        return out


def styled_plot(**axis_items: pg.AxisItem) -> pg.PlotWidget:
    """Cree un `PlotWidget` accorde au theme sombre."""
    widget = pg.PlotWidget(axisItems=axis_items or None)
    widget.setBackground(theme.PANEL)
    item = widget.getPlotItem()
    item.showGrid(x=True, y=True, alpha=0.15)
    item.getViewBox().setDefaultPadding(0.03)
    for name in ("left", "bottom", "right", "top"):
        axis = item.getAxis(name)
        axis.setPen(pg.mkPen(theme.BORDER))
        axis.setTextPen(pg.mkPen(theme.TEXT_MUTED))
    return widget


# -- socle commun ----------------------------------------------------------


class PlotPanel(QtWidgets.QWidget):
    """Un graphique, son titre et ses interactions de zoom."""

    def __init__(
        self,
        title: str = "",
        y_label: str = "",
        x_label: str = "",
        axis_items: dict[str, pg.AxisItem] | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.plot = styled_plot(**(axis_items or {}))
        self.item = self.plot.getPlotItem()
        if title:
            self.item.setTitle(title, color=theme.TEXT, size="10pt")
        if y_label:
            self.item.setLabel("left", y_label)
        if x_label:
            self.item.setLabel("bottom", x_label)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

        # pyqtgraph ne fait rien du double-clic: on s'en sert pour reajuster.
        self.plot.scene().sigMouseClicked.connect(self._on_scene_clicked)

    # -- zoom ---------------------------------------------------------------

    def _on_scene_clicked(self, event) -> None:
        if event.double():
            self.reset_zoom()
            event.accept()

    def reset_zoom(self) -> None:
        """Rajuste les echelles sur l'ensemble des donnees affichees."""
        self.item.enableAutoRange()
        self.item.autoRange()

    def set_mouse_mode(self, rectangle: bool) -> None:
        """Bascule entre zoom par rectangle et deplacement au glisser."""
        mode = pg.ViewBox.RectMode if rectangle else pg.ViewBox.PanMode
        self.item.getViewBox().setMouseMode(mode)

    def legend(self) -> pg.LegendItem:
        if self.item.legend is None:
            self.item.addLegend(
                offset=(-8, 8),
                labelTextColor=theme.TEXT_MUTED,
                brush=pg.mkBrush("#0f141bbb"),
                pen=pg.mkPen(theme.BORDER),
            )
        return self.item.legend

    def add_curve(
        self,
        name: str,
        color: str,
        width: float = 1.6,
        style: QtCore.Qt.PenStyle | None = None,
        fill: str | None = None,
    ) -> pg.PlotDataItem:
        curve = self.item.plot(
            [],
            [],
            name=name or None,
            pen=_pen(color, width, style),
            fillLevel=0 if fill else None,
            brush=pg.mkBrush(fill) if fill else None,
        )
        # Les longues plongees (1 point/s) depassent 10 000 points: on laisse
        # pyqtgraph reduire l'echantillonnage a l'affichage.
        curve.setDownsampling(auto=True, method="peak")
        curve.setClipToView(True)
        return curve


class TimeSeriesPanel(PlotPanel):
    """Graphique dont l'abscisse est le temps de plongee, en secondes."""

    time_hovered = QtCore.pyqtSignal(float)

    def __init__(
        self,
        title: str = "",
        y_label: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(
            title,
            y_label,
            T("Temps (min)"),
            {"bottom": TimeAxis(orientation="bottom")},
            parent,
        )
        self.cursor = pg.InfiniteLine(angle=90, movable=False, pen=_pen("#64748b", 1.0))
        self.cursor.setZValue(40)
        self.cursor.hide()
        self.item.addItem(self.cursor, ignoreBounds=True)
        self.plot.scene().sigMouseMoved.connect(self._on_mouse_moved)

    def _on_mouse_moved(self, position: QtCore.QPointF) -> None:
        if not self.item.sceneBoundingRect().contains(position):
            return
        point = self.item.getViewBox().mapSceneToView(position)
        self.time_hovered.emit(point.x())

    def set_cursor_time(self, seconds: float | None) -> None:
        if seconds is None:
            self.cursor.hide()
            return
        self.cursor.setPos(seconds)
        self.cursor.show()


def link_time_axes(panels: Sequence[TimeSeriesPanel], link: bool = True) -> None:
    """Synchronise (ou desynchronise) l'axe du temps d'une serie de graphiques."""
    if not panels:
        return
    reference = panels[0].item
    for panel in panels[1:]:
        panel.item.setXLink(reference if link else None)


def sync_cursors(panels: Sequence[TimeSeriesPanel]) -> None:
    """Fait suivre a tous les graphiques le curseur de celui que l'on survole."""
    for panel in panels:
        panel.time_hovered.connect(
            lambda seconds, group=panels: [p.set_cursor_time(seconds) for p in group]
        )


class ZoomBar(QtWidgets.QWidget):
    """Commandes de zoom partagees par un groupe de graphiques."""

    def __init__(
        self,
        panels: Sequence[PlotPanel],
        linkable: Sequence[TimeSeriesPanel] = (),
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.panels = list(panels)
        self.linkable = list(linkable)

        reset = QtWidgets.QPushButton(T("Ajuster"))
        reset.setToolTip(
            T("Revenir à la vue complète. Un double-clic sur un graphique fait "
            "la même chose pour ce graphique seul.")
        )
        reset.clicked.connect(self.reset_all)

        self.rect_mode = QtWidgets.QCheckBox(T("Zoom rectangle"))
        self.rect_mode.setToolTip(
            T("Glisser pour encadrer une zone. Decoche: glisser deplace la vue.")
        )
        self.rect_mode.toggled.connect(self._on_mode_toggled)

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(reset)
        layout.addWidget(self.rect_mode)

        if self.linkable:
            self.link_axes = QtWidgets.QCheckBox(T("Axes du temps lies"))
            self.link_axes.setChecked(True)
            self.link_axes.setToolTip(
                T("Zoomer sur un graphique zoome tous les autres au meme instant")
            )
            self.link_axes.toggled.connect(self._on_link_toggled)
            layout.addWidget(self.link_axes)
            link_time_axes(self.linkable, True)

        hint = QtWidgets.QLabel(
            T("molette : zoom · glisser : déplacer · double-clic : ajuster · "
            "clic droit : export")
        )
        hint.setObjectName("subtitle")
        layout.addWidget(hint)
        layout.addStretch(1)

    def reset_all(self) -> None:
        for panel in self.panels:
            panel.reset_zoom()

    def _on_mode_toggled(self, checked: bool) -> None:
        for panel in self.panels:
            panel.set_mouse_mode(checked)

    def _on_link_toggled(self, checked: bool) -> None:
        link_time_axes(self.linkable, checked)
        if not checked:
            self.reset_all()


# -- profil de plongee -----------------------------------------------------


class ProfilePlot(TimeSeriesPanel):
    """Profil: profondeur, temperature, plafond theorique et alertes."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("", T("Profondeur (m)"), parent)
        self.item.invertY(True)
        self.item.setLabel("left", T("Profondeur (m)"), color=theme.DEPTH)
        self.item.showAxis("right")

        # Second repere pour la temperature, synchronise en abscisse.
        self.temp_box = pg.ViewBox()
        self.item.scene().addItem(self.temp_box)
        right = self.item.getAxis("right")
        right.linkToView(self.temp_box)
        right.setLabel(T("Température (°C)"), color=theme.TEMP)
        right.setTextPen(pg.mkPen(theme.TEMP))
        self.temp_box.setXLink(self.item)
        self.item.getViewBox().sigResized.connect(self._sync_boxes)

        self.safety_band = pg.LinearRegionItem(
            values=LIMITS.safety_stop_band,
            orientation="horizontal",
            movable=False,
            brush=pg.mkBrush(theme.SAFETY),
            pen=pg.mkPen(None),
        )
        self.safety_band.setZValue(-30)
        self.item.addItem(self.safety_band)

        self.depth_curve = pg.PlotCurveItem(
            pen=_pen(theme.DEPTH, 2.0),
            brush=pg.mkBrush(theme.DEPTH_FILL),
            fillLevel=0,
        )
        self.item.addItem(self.depth_curve)

        self.ceiling_curve = pg.PlotCurveItem(pen=_pen(theme.WARN, 1.4, DASH))
        self.item.addItem(self.ceiling_curve)

        self.temp_curve = pg.PlotCurveItem(pen=_pen(theme.TEMP, 1.4))
        self.temp_box.addItem(self.temp_curve)

        self.alerts = pg.ScatterPlotItem(
            size=7, pen=pg.mkPen(theme.WARN), brush=pg.mkBrush(theme.WARN), symbol="t1"
        )
        self.item.addItem(self.alerts)

        self.max_marker = pg.ScatterPlotItem(
            size=11, pen=pg.mkPen("#ffffff"), brush=pg.mkBrush(theme.DEPTH), symbol="o"
        )
        self.item.addItem(self.max_marker)

        self._gas_markers: list[pg.InfiniteLine] = []

        self.hline = pg.InfiniteLine(angle=0, movable=False, pen=_pen("#64748b", 1.0))
        self.hline.setZValue(40)
        self.hline.hide()
        self.item.addItem(self.hline, ignoreBounds=True)
        self.readout = pg.TextItem(
            color=theme.TEXT, anchor=(0, 1), fill=pg.mkBrush("#0f141bdd")
        )
        self.readout.setZValue(60)
        self.item.addItem(self.readout)

        self._samples: list[Sample] = []
        self._depth_span = 0.0
        self._time_span = 0.0
        self._temp_span: tuple[float, float] | None = None
        self.time_hovered.connect(self._update_readout)
        self.setToolTip(T(PROFILE_TOOLTIP))
        self.clear()

    def reset_zoom(self) -> None:
        """Retrouve le cadrage initial, temperature comprise."""
        if not self._samples:
            super().reset_zoom()
            return
        self.item.setYRange(0, self._depth_span, padding=0.02)
        self.item.setXRange(0, self._time_span, padding=0.01)
        if self._temp_span:
            self.temp_box.setYRange(*self._temp_span)
        self._sync_boxes()

    # -- rendu --------------------------------------------------------------

    def clear(self) -> None:
        self._samples = []
        for curve in (self.depth_curve, self.temp_curve, self.ceiling_curve):
            curve.setData([], [])
        self.alerts.setData([], [])
        self.max_marker.setData([], [])
        self._clear_gas_markers()
        self.readout.setText("")
        self.hline.hide()

    def show_dive(self, dive: Dive, samples: list[Sample], stats: DiveStats) -> None:
        self.clear()
        if not samples:
            return
        self._samples = samples
        times = [s.time for s in samples]
        depths = [s.depth for s in samples]
        self.depth_curve.setData(times, depths)

        temps = [(s.time, s.temperature) for s in samples if s.temperature is not None]
        if temps:
            self.temp_curve.setData([t for t, _ in temps], [v for _, v in temps])
            values = [v for _, v in temps]
            margin = max((max(values) - min(values)) * 0.6, 1.5)
            self._temp_span = (min(values) - margin, max(values) + margin * 2.5)
            self.temp_box.setYRange(*self._temp_span)

        ceiling = [(t, c) for t, c in stats.deco.ceiling_series if c > 0.05]
        if ceiling:
            self.ceiling_curve.setData([t for t, _ in ceiling], [c for _, c in ceiling])

        rates = dict(stats.ascent_series)
        fast = [(s.time, s.depth) for s in samples if rates.get(s.time, 0.0) > LIMITS.ascent_limit]
        if fast:
            self.alerts.setData([t for t, _ in fast], [d for _, d in fast])

        deepest = max(samples, key=lambda s: s.depth)
        self.max_marker.setData([deepest.time], [deepest.depth])

        if dive.mode is not DiveMode.FREEDIVE:
            self._draw_gas_markers(dive, samples)
        self.safety_band.setVisible(dive.mode is not DiveMode.FREEDIVE)

        self._depth_span = max(depths) * 1.12 + 1
        self._time_span = max(times)
        self.item.setYRange(0, self._depth_span)
        self.item.setXRange(0, self._time_span, padding=0.01)
        self._sync_boxes()

    def _draw_gas_markers(self, dive: Dive, samples: list[Sample]) -> None:
        previous: int | None = None
        for sample in samples:
            if sample.gasmix is None or sample.gasmix == previous:
                continue
            if previous is not None:  # on ignore le melange initial
                mix = (
                    dive.gasmixes[sample.gasmix]
                    if sample.gasmix < len(dive.gasmixes)
                    else None
                )
                line = pg.InfiniteLine(
                    pos=sample.time,
                    angle=90,
                    pen=_pen(theme.PPO2, 1.2, DASH),
                    label=mix.label if mix else "gaz",
                    labelOpts={"position": 0.08, "color": theme.PPO2, "fill": "#0f141bcc"},
                )
                self.item.addItem(line)
                self._gas_markers.append(line)
            previous = sample.gasmix

    def _clear_gas_markers(self) -> None:
        for line in self._gas_markers:
            self.item.removeItem(line)
        self._gas_markers.clear()

    # -- interactions -------------------------------------------------------

    def _sync_boxes(self) -> None:
        self.temp_box.setGeometry(self.item.getViewBox().sceneBoundingRect())
        self.temp_box.linkedViewChanged(self.item.getViewBox(), self.temp_box.XAxis)

    def _update_readout(self, seconds: float) -> None:
        if not self._samples:
            return
        sample = min(self._samples, key=lambda s: abs(s.time - seconds))
        self.hline.setPos(sample.depth)
        self.hline.show()
        text = f"{sample.time // 60}:{sample.time % 60:02d}  ·  {sample.depth:.1f} m"
        if sample.temperature is not None:
            text += f"  ·  {sample.temperature:.1f} °C"
        if sample.pressure:
            text += T("  ·  {pressure:.0f} bar").format(pressure=sample.pressure)
        self.readout.setText(text)
        self.readout.setPos(sample.time, sample.depth)


class NavigatorPlot(QtWidgets.QWidget):
    """Vignette du profil complet, avec une fenetre deplacable.

    Deplacer ou redimensionner la zone claire change la plage temporelle
    affichee par les graphiques lies.
    """

    range_changed = QtCore.pyqtSignal(float, float)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.plot = styled_plot()
        self.plot.setFixedHeight(74)
        self.plot.setMenuEnabled(False)
        self.item = self.plot.getPlotItem()
        self.item.invertY(True)
        self.item.hideAxis("left")
        self.item.showGrid(x=False, y=False)
        self.item.setMouseEnabled(x=False, y=False)
        self.item.getAxis("bottom").setStyle(showValues=False)

        self.curve = pg.PlotCurveItem(
            pen=_pen(theme.DEPTH, 1.2), brush=pg.mkBrush(theme.DEPTH_FILL), fillLevel=0
        )
        self.item.addItem(self.curve)

        self.window = pg.LinearRegionItem(
            brush=pg.mkBrush("#38bdf822"), pen=pg.mkPen(theme.ACCENT)
        )
        self.window.setZValue(10)
        self.item.addItem(self.window)
        self.window.sigRegionChanged.connect(self._on_region_changed)
        self._silent = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.plot)

    def show_dive(self, samples: list[Sample]) -> None:
        if not samples:
            self.curve.setData([], [])
            return
        times = [s.time for s in samples]
        self.curve.setData(times, [s.depth for s in samples])
        self.item.setXRange(0, max(times), padding=0)
        self.set_window(0, max(times))

    def set_window(self, start: float, end: float) -> None:
        self._silent = True
        self.window.setRegion((start, end))
        self._silent = False

    def _on_region_changed(self) -> None:
        if self._silent:
            return
        start, end = self.window.getRegion()
        self.range_changed.emit(start, end)


# -- graphiques temporels derives ------------------------------------------


class RatePlot(TimeSeriesPanel):
    """Vitesse verticale au fil de la plongee, avec la limite recommandee."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("", T("Vitesse (m/min)"), parent)
        self.item.addLine(y=0, pen=_pen(theme.BORDER, 1.0))
        self.item.addLine(
            y=LIMITS.ascent_limit,
            pen=_pen(theme.WARN, 1.2, DASH),
            label=T("remontée 10 m/min"),
            labelOpts={"position": 0.18, "color": theme.WARN},
        )
        self.item.addLine(
            y=-18.0,
            pen=_pen(theme.DESCENT, 1.0, DOT),
            label=T("descente 18 m/min"),
            labelOpts={"position": 0.82, "color": theme.DESCENT},
        )
        self.up = self.add_curve(T("remontée"), theme.ASCENT, 1.6, fill="#22c55e22")
        self.down = self.add_curve("descente", theme.DESCENT, 1.6, fill="#60a5fa22")
        self.setToolTip(T(RATE_TOOLTIP))

    def show_series(self, series: list[tuple[int, float]]) -> None:
        if not series:
            self.up.setData([], [])
            self.down.setData([], [])
            return
        times = [t for t, _ in series]
        rates = [r for _, r in series]
        self.up.setData(times, [max(r, 0.0) for r in rates])
        self.down.setData(times, [min(r, 0.0) for r in rates])


class PpO2Plot(TimeSeriesPanel):
    """Pression partielle d'oxygene au fil de la plongee."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("", T("ppO2 (bar)"), parent)
        for level, color, label, spot in (
            (1.4, theme.WARN, T("1,4 bar"), 0.06),
            (1.6, "#dc2626", T("1,6 bar"), 0.22),
        ):
            self.item.addLine(
                y=level,
                pen=_pen(color, 1.1, DASH),
                label=label,
                labelOpts={"position": spot, "color": color},
            )
        self.curve = self.add_curve(T("ppO2"), theme.PPO2, 1.8, fill="#a78bfa22")
        self.setToolTip(T(PPO2_TOOLTIP))

    def show_series(self, series: list[tuple[int, float]]) -> None:
        if not series:
            self.curve.setData([], [])
            return
        values = [v for _, v in series]
        self.curve.setData([t for t, _ in series], values)
        self.item.setYRange(0, max(max(values) * 1.25, 1.75))


class OxygenLoadPlot(TimeSeriesPanel):
    """Cumul de la charge CNS et des OTU."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("", T("CNS (%) · OTU"), parent)
        self.legend()
        self.cns = self.add_curve(T("CNS (%)"), theme.WARN, 1.8, fill="#f8717122")
        self.otu = self.add_curve(T("OTU"), theme.TEMP, 1.6)
        self.placeholder = pg.TextItem(
            T("Aucune exposition cumulée : la ppO2 est restée sous 0,5 bar."),
            color=theme.TEXT_MUTED,
            anchor=(0.5, 0.5),
        )
        self.item.addItem(self.placeholder)
        self.setToolTip(T(OXYGEN_TOOLTIP))

    def show_series(
        self, cns: list[tuple[int, float]], otu: list[tuple[int, float]]
    ) -> None:
        self.cns.setData([t for t, _ in cns], [v for _, v in cns])
        self.otu.setData([t for t, _ in otu], [v for _, v in otu])
        highest = max([v for _, v in cns] + [v for _, v in otu] + [0.0])
        self.item.setYRange(0, max(highest * 1.15, 1.0))
        self.placeholder.setVisible(highest <= 0.001)
        if cns:
            self.placeholder.setPos((cns[0][0] + cns[-1][0]) / 2, 0.5)


class TissueLoadPlot(TimeSeriesPanel):
    """Sursaturation du compartiment directeur et plafond theorique."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("", T("Sursaturation (% M-value)"), parent)
        self.legend()
        self.item.addLine(
            y=100,
            pen=_pen(theme.WARN, 1.2, DASH),
            label=T("M-value"),
            labelOpts={"position": 0.14, "color": theme.WARN},
        )
        self.loading = self.add_curve(
            T("à la profondeur courante"), theme.GOOD, 1.8, fill="#4ade8022"
        )
        self.surface_loading = self.add_curve(
            T("si remontée immédiate"), theme.ACCENT, 1.5, DASH
        )
        self.item.showAxis("right")
        self.ceiling_box = pg.ViewBox()
        self.item.scene().addItem(self.ceiling_box)
        right = self.item.getAxis("right")
        right.linkToView(self.ceiling_box)
        right.setLabel(T("Plafond (m)"), color=theme.WARN)
        right.setTextPen(pg.mkPen(theme.WARN))
        self.ceiling_box.setXLink(self.item)
        self.ceiling_box.invertY(True)
        self.item.getViewBox().sigResized.connect(self._sync)
        self.ceiling = pg.PlotCurveItem(pen=_pen(theme.WARN, 1.6))
        self.ceiling_box.addItem(self.ceiling)
        self._ceiling_span = 3.0
        self._loading_span = 110.0
        self.setToolTip(T(TISSUE_TOOLTIP))

    def reset_zoom(self) -> None:
        self.item.setYRange(0, self._loading_span)
        self.ceiling_box.setYRange(0, self._ceiling_span)
        self.item.enableAutoRange(axis="x")
        self.item.autoRange()
        self._sync()

    def _sync(self) -> None:
        self.ceiling_box.setGeometry(self.item.getViewBox().sceneBoundingRect())
        self.ceiling_box.linkedViewChanged(self.item.getViewBox(), self.ceiling_box.XAxis)

    def show_series(
        self,
        loading: list[tuple[int, float]],
        ceiling: list[tuple[int, float]],
        surface: list[tuple[int, float]] | None = None,
    ) -> None:
        self.loading.setData([t for t, _ in loading], [v for _, v in loading])
        surface = surface or []
        self.surface_loading.setData([t for t, _ in surface], [v for _, v in surface])
        self.ceiling.setData([t for t, _ in ceiling], [v for _, v in ceiling])
        highest = max((v for _, v in ceiling), default=0.0)
        self._ceiling_span = max(highest * 1.4, 3.0)
        self.ceiling_box.setYRange(0, self._ceiling_span)
        peak = max([v for _, v in loading] + [v for _, v in surface] + [0.0])
        self._loading_span = max(peak * 1.2, 110.0)
        self.item.setYRange(0, self._loading_span)
        self._sync()


class GasPressurePlot(TimeSeriesPanel):
    """Pression du bloc: mesuree si disponible, sinon estimee."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("", T("Pression (bar)"), parent)
        self.item.addLine(
            y=50,
            pen=_pen(theme.WARN, 1.1, DASH),
            label=T("réserve 50 bar"),
            labelOpts={"position": 0.14, "color": theme.WARN},
        )
        self.curve = self.add_curve("pression", theme.ACCENT, 1.8, fill="#38bdf822")
        self.placeholder = pg.TextItem(
            T("Renseignez le bloc et les pressions dans l'onglet Carnet\n"
            "pour estimer la courbe de consommation."),
            color=theme.TEXT_MUTED,
            anchor=(0.5, 0.5),
        )
        self.item.addItem(self.placeholder)
        self.setToolTip(T(PRESSURE_TOOLTIP))

    def show_series(self, series: list[tuple[int, float]], measured: bool) -> None:
        self.placeholder.setVisible(not series)
        if not series:
            self.curve.setData([], [])
            # Repere fixe: sans donnees, le texte se retrouverait a l'abscisse 0
            # et donc a moitie hors du cadre.
            self.item.setXRange(0, 60, padding=0)
            self.item.setYRange(0, 220, padding=0)
            self.placeholder.setPos(30, 120)
            self.item.setTitle("")
            return
        times = [t for t, _ in series]
        values = [v for _, v in series]
        self.curve.setData(times, values)
        self.item.setTitle(
            T("Pression mesurée") if measured else T("Pression estimée (consommation constante)"),
            color=theme.TEXT,
            size="9pt",
        )
        self.placeholder.setPos(
            (times[0] + times[-1]) / 2, (max(values) + min(values)) / 2
        )


class EadPlot(TimeSeriesPanel):
    """Profondeur reelle et profondeur equivalente air."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__("", T("Profondeur (m)"), parent)
        self.item.invertY(True)
        self.legend()
        self.real = self.add_curve(T("profondeur réelle"), theme.DEPTH, 1.8)
        self.ead = self.add_curve(T("équivalente air"), theme.PPO2, 1.6, DASH)
        self.setToolTip(T(EAD_TOOLTIP))

    def show_series(
        self, samples: list[Sample], ead: list[tuple[int, float]]
    ) -> None:
        self.real.setData([s.time for s in samples], [s.depth for s in samples])
        self.ead.setData([t for t, _ in ead], [v for _, v in ead])


# -- graphiques non temporels ----------------------------------------------


class BarPanel(PlotPanel):
    """Histogramme, vertical ou horizontal, a etiquettes numeriques."""

    def __init__(
        self,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        color: str = theme.DEPTH,
        horizontal: bool = False,
        invert_y: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(title, y_label, x_label, None, parent)
        self.color = color
        self.horizontal = horizontal
        if invert_y:
            self.item.invertY(True)
        self.bars: pg.BarGraphItem | None = None

    def show_buckets(
        self, buckets: list[tuple[float, float]], bucket_size: float = 3.0
    ) -> None:
        if self.bars is not None:
            self.item.removeItem(self.bars)
            self.bars = None
        if not buckets:
            return
        centres = [low + bucket_size / 2 for low, _ in buckets]
        values = [float(value) for _, value in buckets]
        if self.horizontal:
            self.bars = pg.BarGraphItem(
                x0=[0] * len(buckets),
                y=centres,
                height=bucket_size * 0.82,
                width=values,
                brush=pg.mkBrush(self.color),
                pen=pg.mkPen(None),
            )
        else:
            self.bars = pg.BarGraphItem(
                x=centres,
                height=values,
                width=bucket_size * 0.82,
                brush=pg.mkBrush(self.color),
                pen=pg.mkPen(None),
            )
        self.item.addItem(self.bars)


class CategoryBarPanel(PlotPanel):
    """Histogramme a etiquettes textuelles."""

    def __init__(
        self,
        title: str = "",
        y_label: str = "",
        color: str = theme.DEPTH,
        horizontal: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        self.axis = LabelAxis(orientation="left" if horizontal else "bottom")
        super().__init__(
            title,
            y_label if not horizontal else "",
            "" if not horizontal else y_label,
            {"left" if horizontal else "bottom": self.axis},
            parent,
        )
        self.color = color
        self.horizontal = horizontal
        self.bars: pg.BarGraphItem | None = None

    def show_values(self, labels: Sequence[str], values: Sequence[float]) -> None:
        if self.bars is not None:
            self.item.removeItem(self.bars)
            self.bars = None
        self.axis.labels = list(labels)
        if not values:
            self.axis.setTicks([[]])
            return
        positions = list(range(len(values)))
        if self.horizontal:
            self.bars = pg.BarGraphItem(
                x0=[0] * len(values),
                y=positions,
                height=0.68,
                width=list(values),
                brush=pg.mkBrush(self.color),
                pen=pg.mkPen(None),
            )
        else:
            self.bars = pg.BarGraphItem(
                x=positions,
                height=list(values),
                width=0.68,
                brush=pg.mkBrush(self.color),
                pen=pg.mkPen(None),
            )
        self.item.addItem(self.bars)
        span = (-0.6, len(values) - 0.4)
        if self.horizontal:
            self.item.setYRange(*span)
            self.item.setXRange(0, max(values) * 1.12 or 1)
        else:
            self.item.setXRange(*span)
            self.item.setYRange(0, max(values) * 1.18 or 1)
        # Une etiquette sur N au-dela de douze categories, pour rester lisible.
        step = max(1, len(labels) // 12)
        self.axis.setTicks(
            [[(index, labels[index]) for index in range(0, len(labels), step)]]
        )


class ScatterPanel(PlotPanel):
    """Nuage de points, avec coloration facultative selon une troisieme valeur."""

    def __init__(
        self,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        color: str = theme.DEPTH,
        invert_y: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(title, y_label, x_label, None, parent)
        if invert_y:
            self.item.invertY(True)
        self.points = pg.ScatterPlotItem(
            size=8, pen=pg.mkPen(None), brush=pg.mkBrush(color)
        )
        self.item.addItem(self.points)

    def show_points(self, points: Iterable[tuple[float, float]]) -> None:
        data = list(points)
        if not data:
            self.points.setData([], [])
            return
        self.points.setData([x for x, _ in data], [y for _, y in data])


class TrendPanel(PlotPanel):
    """Serie temporelle datee, en points relies."""

    def __init__(
        self,
        title: str = "",
        y_label: str = "",
        color: str = theme.DEPTH,
        invert: bool = False,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(
            title, y_label, "", {"bottom": DateAxis(orientation="bottom")}, parent
        )
        self.item.invertY(invert)
        self.curve = self.item.plot(
            [],
            [],
            pen=_pen(color, 1.8),
            symbol="o",
            symbolSize=6,
            symbolBrush=pg.mkBrush(color),
            symbolPen=pg.mkPen(None),
        )
        self.trend = self.item.plot([], [], pen=_pen(theme.TEXT_MUTED, 1.0, DASH))

    def show_series(
        self, points: list[tuple[_dt.datetime, float]], with_trend: bool = True
    ) -> None:
        if not points:
            self.curve.setData([], [])
            self.trend.setData([], [])
            return
        xs = [moment.timestamp() for moment, _ in points]
        ys = [float(value) for _, value in points]
        self.curve.setData(xs, ys)
        if with_trend and len(xs) >= 3:
            self.trend.setData(xs, _linear_trend(xs, ys))
        else:
            self.trend.setData([], [])


def _linear_trend(xs: list[float], ys: list[float]) -> list[float]:
    """Droite des moindres carres, pour souligner une tendance."""
    count = len(xs)
    mean_x = sum(xs) / count
    mean_y = sum(ys) / count
    variance = sum((x - mean_x) ** 2 for x in xs)
    if variance == 0:
        return [mean_y] * count
    slope = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / variance
    return [mean_y + slope * (x - mean_x) for x in xs]


class TissueBarPanel(PlotPanel):
    """Charge des 16 compartiments a la sortie de l'eau."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        self.axis = LabelAxis(
            [f"{value:g}" for value in N2_HALFLIVES], orientation="bottom"
        )
        super().__init__(
            "",
            T("Charge (% M-value)"),
            T("Demi-vie du compartiment (min)"),
            {"bottom": self.axis},
            parent,
        )
        self.item.addLine(
            y=100,
            pen=_pen(theme.WARN, 1.2, DASH),
            label=T("M-value"),
            labelOpts={"position": 0.04, "color": theme.WARN},
        )
        self.bars: pg.BarGraphItem | None = None
        self.axis.setTicks(
            [[(index, f"{N2_HALFLIVES[index]:g}") for index in range(NCOMPARTMENTS)]]
        )
        self.setToolTip(T(TISSUE_BARS_TOOLTIP))

    def show_loadings(self, loadings: Sequence[float]) -> None:
        if self.bars is not None:
            self.item.removeItem(self.bars)
            self.bars = None
        if not loadings:
            return
        # Du vert au rouge selon la proximite de la M-value.
        brushes = [
            pg.mkBrush(theme.WARN if value >= 85 else theme.GOOD if value < 60 else theme.TEMP)
            for value in loadings
        ]
        self.bars = pg.BarGraphItem(
            x=list(range(len(loadings))),
            height=list(loadings),
            width=0.7,
            brushes=brushes,
            pen=pg.mkPen(None),
        )
        self.item.addItem(self.bars)
        self.item.setYRange(0, max(max(loadings) * 1.2, 110))
