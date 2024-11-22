from qgis.PyQt.QtCore import QObject, QSettings, QVariant
from qgis.PyQt.QtWidgets import QMessageBox

from ...attribute_linker import AttributeLinker
from ...func.utils import log


class AdvancedOptions(QObject):
    def __init__(self, dialog):
        super().__init__(dialog)
        self.dialog = dialog

    def on_segments_attr_selected(self):
        if self.dialog.ui.segments_attr_combo.currentText():
            selected_segments_attr = (
                self.dialog.ui.segments_attr_combo.currentText()
            )
            settings = QSettings()
            settings.setValue(
                "routes_composer/segments_attr_name", selected_segments_attr
            )
            log(f"Segments attribute selected: {selected_segments_attr}")

            field_index = self.dialog.layer_manager.selected_segments_layer.fields().indexOf(
                selected_segments_attr
            )
            if field_index != -1:
                field_type = (
                    self.dialog.layer_manager.selected_segments_layer.fields()
                    .at(field_index)
                    .type()
                )
                if field_type == QVariant.String:
                    self.dialog.ui.priority_mode_combo.setCurrentText("none")

    def on_compositions_attr_selected(self):
        if self.dialog.ui.compositions_attr_combo.currentText():
            selected_compositions_attr = (
                self.dialog.ui.compositions_attr_combo.currentText()
            )
            settings = QSettings()
            settings.setValue(
                "routes_composer/compositions_attr_name",
                selected_compositions_attr,
            )
            log(
                f"Compositions attribute selected: {selected_compositions_attr}"
            )

            field_index = self.dialog.layer_manager.selected_compositions_layer.fields().indexOf(
                selected_compositions_attr
            )
            if field_index != -1:
                field_type = (
                    self.dialog.layer_manager.selected_compositions_layer.fields()
                    .at(field_index)
                    .type()
                )
                if field_type == QVariant.String:
                    self.dialog.ui.priority_mode_combo.setCurrentText("none")

    def on_priority_mode_selected(self):
        selected_priority_mode = (
            self.dialog.ui.priority_mode_combo.currentText()
        )
        settings = QSettings()
        settings.setValue(
            "routes_composer/priority_mode", selected_priority_mode
        )
        log(f"Priority mode selected: {selected_priority_mode}")

    def update_attr_combos(self):
        if (
            not self.dialog.layer_manager.selected_segments_layer
            or not self.dialog.layer_manager.selected_compositions_layer
        ):
            return

        self.dialog.ui.segments_attr_combo.clear()
        self.dialog.ui.compositions_attr_combo.clear()

        for (
            field
        ) in self.dialog.layer_manager.selected_segments_layer.fields():
            self.dialog.ui.segments_attr_combo.addItem(field.name())

        for (
            field
        ) in self.dialog.layer_manager.selected_compositions_layer.fields():
            self.dialog.ui.compositions_attr_combo.addItem(field.name())

        settings = QSettings()
        saved_segments_attr = settings.value(
            "routes_composer/segments_attr_name", ""
        )
        saved_compositions_attr = settings.value(
            "routes_composer/compositions_attr_name", ""
        )

        if saved_segments_attr:
            segments_attr_index = self.dialog.ui.segments_attr_combo.findText(
                saved_segments_attr
            )
            if segments_attr_index >= 0:
                self.dialog.ui.segments_attr_combo.setCurrentIndex(
                    segments_attr_index
                )

        if saved_compositions_attr:
            compositions_attr_index = (
                self.dialog.ui.compositions_attr_combo.findText(
                    saved_compositions_attr
                )
            )
            if compositions_attr_index >= 0:
                self.dialog.ui.compositions_attr_combo.setCurrentIndex(
                    compositions_attr_index
                )

    def start_attribute_linking(self):
        if (
            not self.dialog.ui.segments_combo.currentData()
            or not self.dialog.ui.compositions_combo.currentData()
            or not self.dialog.ui.segments_attr_combo.currentText()
            or not self.dialog.ui.compositions_attr_combo.currentText()
        ):
            QMessageBox.warning(
                self.dialog,
                self.tr("Attention"),
                self.tr(
                    "Veuillez sélectionner les couches segments et compositions ainsi que les attributs."
                ),
            )
            return

        segments_layer = self.dialog.layer_manager.selected_segments_layer
        compositions_layer = (
            self.dialog.layer_manager.selected_compositions_layer
        )
        segments_column_name = (
            self.dialog.ui.segments_column_combo.currentText()
        )
        id_column_name = self.dialog.ui.id_column_combo.currentText()
        segments_attr = self.dialog.ui.segments_attr_combo.currentText()
        compositions_attr = (
            self.dialog.ui.compositions_attr_combo.currentText()
        )

        self.attribute_linker = AttributeLinker(
            segments_layer=segments_layer,
            compositions_layer=compositions_layer,
            segments_attr=segments_attr,
            compositions_attr=compositions_attr,
            id_column_name=id_column_name,
            segments_column_name=segments_column_name,
            priority_mode=self.dialog.ui.priority_mode_combo.currentText().lower(),
        )
        self.attribute_linker.update_segments_attr_values()

    def stop_attribute_linking(self):
        """UNUSE. Arrête la liaison des attributs."""
        if hasattr(self, "attribute_linker"):
            self.attribute_linker.stop()
