"""Petits composants reutilisables: cartes de statistiques, tableau cle/valeur."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from ..i18n import T
from . import theme


class StatCard(QtWidgets.QFrame):
    """Une valeur mise en avant, avec son intitule et une precision optionnelle."""

    def __init__(
        self,
        label: str,
        value: str = "-",
        hint: str = "",
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("card")
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed
        )

        self._label = QtWidgets.QLabel(label.upper())
        self._label.setObjectName("statLabel")
        self._label.setMinimumWidth(1)
        self._value = QtWidgets.QLabel(value)
        self._value.setObjectName("statValue")
        self._hint = QtWidgets.QLabel(hint)
        self._hint.setObjectName("statHint")
        self._hint.setVisible(bool(hint))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(2)
        layout.addWidget(self._label)
        layout.addWidget(self._value)
        layout.addWidget(self._hint)

    def set_value(self, value: str, hint: str = "", color: str | None = None) -> None:
        self._value.setText(value)
        self._hint.setText(hint)
        self._hint.setVisible(bool(hint))
        self._value.setStyleSheet(f"color: {color};" if color else "")


class CardRow(QtWidgets.QWidget):
    """Une rangee de `StatCard`, accessibles par cle."""

    def __init__(
        self, keys: list[tuple[str, str]], parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.cards: dict[str, StatCard] = {}
        grid = QtWidgets.QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setSpacing(8)
        for column, (key, label) in enumerate(keys):
            card = StatCard(label)
            card.setMinimumWidth(110)
            self.cards[key] = card
            grid.addWidget(card, 0, column)
            grid.setColumnStretch(column, 1)

    def set(self, key: str, value: str, hint: str = "", color: str | None = None) -> None:
        card = self.cards.get(key)
        if card is not None:
            card.set_value(value, hint, color)

    def reset(self) -> None:
        for card in self.cards.values():
            card.set_value("-", "")


class KeyValueTable(QtWidgets.QTableWidget):
    """Tableau a deux colonnes pour afficher des champs brutes."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(0, 2, parent)
        self.setHorizontalHeaderLabels([T("Champ"), T("Valeur")])
        self.verticalHeader().setVisible(False)
        self.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.setAlternatingRowColors(True)
        self.setShowGrid(False)
        self.setWordWrap(False)
        self.setTextElideMode(QtCore.Qt.TextElideMode.ElideRight)
        header = self.horizontalHeader()
        header.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        header.resizeSection(0, 240)

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        self.setRowCount(len(rows))
        for index, (key, value) in enumerate(rows):
            name = QtWidgets.QTableWidgetItem(key)
            name.setForeground(QtCore.Qt.GlobalColor.gray)
            self.setItem(index, 0, name)
            cell = QtWidgets.QTableWidgetItem(value)
            cell.setToolTip(value)
            self.setItem(index, 1, cell)


class SectionTitle(QtWidgets.QWidget):
    """Titre de section avec sous-titre discret."""

    def __init__(
        self, title: str, subtitle: str = "", parent: QtWidgets.QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self.title = QtWidgets.QLabel(title)
        self.title.setObjectName("title")
        self.subtitle = QtWidgets.QLabel(subtitle)
        self.subtitle.setObjectName("subtitle")
        self.subtitle.setVisible(bool(subtitle))

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 4)
        layout.setSpacing(1)
        layout.addWidget(self.title)
        layout.addWidget(self.subtitle)

    def set_text(self, title: str, subtitle: str = "") -> None:
        self.title.setText(title)
        self.subtitle.setText(subtitle)
        self.subtitle.setVisible(bool(subtitle))


def scrollable(widget: QtWidgets.QWidget) -> QtWidgets.QScrollArea:
    """Emballe un widget dans une zone defilante sans bordure."""
    area = QtWidgets.QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
    area.setStyleSheet(f"QScrollArea {{ background: {theme.BG}; }}")
    area.setWidget(widget)
    return area
