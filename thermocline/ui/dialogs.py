"""Boites de dialogue secondaires."""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from .. import dates
from ..csv_import import CsvDiveRow, CsvParseResult
from ..i18n import T, count_label
from ..storage import Database, HiddenDive
from . import theme


class HiddenDivesDialog(QtWidgets.QDialog):
    """Gere les plongees masquees: les consulter et les reautoriser.

    Masquer sert surtout aux ordinateurs d'occasion, dont la memoire contient
    encore les plongees de l'ancien proprietaire.
    """

    def __init__(self, db: Database, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.db = db
        self.setWindowTitle(T("Plongées masquées"))
        self.resize(620, 420)

        intro = QtWidgets.QLabel(
            T("Ces plongées ont été retirées du carnet et ne seront plus "
            "importées, même lors d'une relecture complète.\n"
            "Les restaurer les rend à nouveau importables : relancez ensuite "
            "« Tout relire » pour les récupérer.")
        )
        intro.setWordWrap(True)
        intro.setObjectName("subtitle")

        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self.list.setAlternatingRowColors(True)

        self.restore_button = QtWidgets.QPushButton(T("Restaurer la sélection"))
        self.restore_button.setObjectName("primary")
        self.restore_button.clicked.connect(self._restore_selected)
        close_button = QtWidgets.QPushButton(T("Fermer"))
        close_button.clicked.connect(self.accept)

        buttons = QtWidgets.QHBoxLayout()
        buttons.addWidget(self.restore_button)
        buttons.addStretch(1)
        buttons.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(intro)
        layout.addWidget(self.list, stretch=1)
        layout.addLayout(buttons)

        self.restored = 0
        self.reload()

    def reload(self) -> None:
        self.list.clear()
        hidden = self.db.hidden_dives()
        for entry in hidden:
            item = QtWidgets.QListWidgetItem(self._describe(entry))
            item.setData(
                QtCore.Qt.ItemDataRole.UserRole, (entry.device_serial, entry.fingerprint)
            )
            self.list.addItem(item)
        empty = not hidden
        self.restore_button.setEnabled(not empty)
        if empty:
            placeholder = QtWidgets.QListWidgetItem(T("Aucune plongée masquée."))
            placeholder.setFlags(QtCore.Qt.ItemFlag.NoItemFlags)
            placeholder.setForeground(QtCore.Qt.GlobalColor.gray)
            self.list.addItem(placeholder)

    @staticmethod
    def _describe(entry: HiddenDive) -> str:
        label = entry.label
        if entry.hidden_at is not None:
            label += T("    (masquée le {short_date})").format(short_date=dates.short_date(entry.hidden_at))
        return label

    def _restore_selected(self) -> None:
        keys = [
            item.data(QtCore.Qt.ItemDataRole.UserRole)
            for item in self.list.selectedItems()
            if item.data(QtCore.Qt.ItemDataRole.UserRole)
        ]
        if not keys:
            QtWidgets.QMessageBox.information(
                self, T("Restaurer"), T("Sélectionnez au moins une plongée dans la liste.")
            )
            return
        for serial, fingerprint in keys:
            self.db.restore_hidden(serial, fingerprint)
        self.restored += len(keys)
        self.reload()
        QtWidgets.QMessageBox.information(
            self,
            T("Restaurer"),
            T("{len} plongée(s) à nouveau importable(s).\n\nLancez « Tout relire » pour les récupérer depuis l'ordinateur.").format(len=len(keys)),
        )


class CsvImportDialog(QtWidgets.QDialog):
    """Choix des plongees a importer parmi celles lues dans un carnet CSV."""

    def __init__(self, result: CsvParseResult, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(T("Importer un carnet CSV"))
        self.resize(640, 480)

        summary = count_label(
            len(result.rows),
            "{count} plongée trouvée.",
            "{count} plongées trouvées.",
        )
        if result.errors:
            summary += " " + count_label(
                len(result.errors),
                "{count} ligne ignorée.",
                "{count} lignes ignorées.",
            )
        intro = QtWidgets.QLabel(summary)
        intro.setWordWrap(True)
        intro.setObjectName("subtitle")

        self.list = QtWidgets.QListWidget()
        self.list.setAlternatingRowColors(True)
        for row in result.rows:
            label = row.label
            if row.duplicate:
                label += T("    (déjà importée)")
            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(
                QtCore.Qt.CheckState.Unchecked
                if row.duplicate
                else QtCore.Qt.CheckState.Checked
            )
            if row.duplicate:
                item.setForeground(QtCore.Qt.GlobalColor.gray)
            item.setData(QtCore.Qt.ItemDataRole.UserRole, row)
            self.list.addItem(item)

        select_all = QtWidgets.QPushButton(T("Tout cocher"))
        select_all.clicked.connect(lambda: self._set_all(QtCore.Qt.CheckState.Checked))
        select_none = QtWidgets.QPushButton(T("Tout décocher"))
        select_none.clicked.connect(lambda: self._set_all(QtCore.Qt.CheckState.Unchecked))
        top_buttons = QtWidgets.QHBoxLayout()
        top_buttons.addWidget(select_all)
        top_buttons.addWidget(select_none)
        top_buttons.addStretch(1)

        self.import_button = QtWidgets.QPushButton(T("Importer la sélection"))
        self.import_button.setObjectName("primary")
        self.import_button.setEnabled(bool(result.rows))
        self.import_button.clicked.connect(self.accept)
        cancel_button = QtWidgets.QPushButton(T("Annuler"))
        cancel_button.clicked.connect(self.reject)
        bottom_buttons = QtWidgets.QHBoxLayout()
        bottom_buttons.addStretch(1)
        bottom_buttons.addWidget(cancel_button)
        bottom_buttons.addWidget(self.import_button)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)
        layout.addWidget(intro)
        if result.errors:
            errors_label = QtWidgets.QLabel("\n".join(result.errors[:10]))
            errors_label.setWordWrap(True)
            errors_label.setObjectName("subtitle")
            layout.addWidget(errors_label)
        layout.addLayout(top_buttons)
        layout.addWidget(self.list, stretch=1)
        layout.addLayout(bottom_buttons)

    def _set_all(self, state: QtCore.Qt.CheckState) -> None:
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def selected_rows(self) -> list[CsvDiveRow]:
        rows = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                rows.append(item.data(QtCore.Qt.ItemDataRole.UserRole))
        return rows


def apply_theme(dialog: QtWidgets.QDialog) -> None:
    """Applique la feuille de style sombre a une boite de dialogue isolee."""
    dialog.setStyleSheet(theme.STYLESHEET)
