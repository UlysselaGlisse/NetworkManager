from PyQt5 import QtCore
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    Qgis,
    QgsFeatureRequest,
    QgsWkbTypes,
    QgsSpatialIndex
)
from qgis.utils import iface
from qgis.PyQt.QtWidgets import (
    QDialog,
    QPushButton,
    QVBoxLayout,
    QLabel,
    QWidget,
    QMessageBox,
    QProgressBar,
    QComboBox,
    QHBoxLayout,
    QGroupBox,
    QCheckBox,
    QLineEdit
)
from qgis.PyQt.QtGui import QCloseEvent
from qgis.PyQt.QtCore import Qt, QTimer, QSettings
from typing import Literal, Optional, cast
from .utils import timer_decorator, print_geometry_info, get_features_list
from .functions import (
    get_compositions_list_segments,
    update_compositions_segments,
    clean_invalid_segments,
    has_duplicate_segment_id,
    get_next_id,
    update_segment_id,
    process_single_segment_composition

)
from .config import segments_field_index

segments_column_name = "segments"
segments_layer = None
compositions_layer = None
last_fid = 0

#@timer_decorator
def feature_added(fid):

    # Empêche Qgis de planter. Sûrement une histoire de priorité de tâche. J'ai trouvé ça pour y parer.'
    QTimer.singleShot(1, lambda: process_new_feature(fid))
#@timer_decorator
def process_new_feature(fid):
    """
    Traite une nouvelle feature ajoutée
    """
    global last_fid

    if last_fid == fid:
        return

    #print(f"\n{'='*50}")
    #print(f"Traitement nouvelle entité FID={fid}")
    #print(f"{'='*50}")

    source_feature = segments_layer.getFeature(fid)
    if not source_feature.fields().names():
        #print("ERREUR: Pas de champs dans la feature source")
        return

    id_idx = source_feature.fields().indexOf('id')
    segment_id = source_feature.attributes()[id_idx]

    # print(f"ID du segment: {segment_id}")

    if segment_id and has_duplicate_segment_id(segments_layer,segment_id):
        #print(f"Segment {segment_id} détecté comme dupliqué")

        new_geometry = source_feature.geometry()
        if not new_geometry or new_geometry.isEmpty():
            #print("ERREUR: Géométrie invalide pour le nouveau segment")
            return

        # Récupérer le segment original
        expression = f"\"id\" = '{segment_id}' AND $id != {fid}"
        request = QgsFeatureRequest().setFilterExpression(expression)
        original_feature = next(segments_layer.getFeatures(request), None)

        if original_feature:
            #print(f"Segment original trouvé: FID={original_feature.id()}")

            # Vérifier les géométries
            # print_geometry_info(original_feature.geometry(), "Segment original")
            # print_geometry_info(new_geometry, "Nouveau segment")

            # Récupérer toutes les compositions contenant ce segment
            segment_lists = get_compositions_list_segments(segment_id, compositions_layer)
            #print(f"Nombre de compositions trouvées: {len(segment_lists)}")

            if segment_lists:
                #print(segment_lists)
                next_id = get_next_id(segments_layer)
                #print(f"Nouvel ID à attribuer: {next_id}")

                update_segment_id(segments_layer, fid, next_id)
                segment_unique = None

                for segments_list in segment_lists:
                    if len(segments_list) == 1:
                        segment_unique = True

                if segment_unique == True:
                    #log_debug("Composition à segment unique détectée - Traitement spécial")
                    new_segments = process_single_segment_composition(segments_layer, compositions_layer, fid, segment_id, next_id, segments_list)
                    if new_segments is None:
                        pass
                else:
                    update_compositions_segments(segments_layer, compositions_layer, segment_id, next_id, original_feature, source_feature, segment_lists)

            else:
                print("ATTENTION: Aucune composition trouvée pour ce segment")
        else:
            print("ERREUR: Segment original non trouvé")
    else:
        print("Le segment n'est pas un doublon ou n'a pas d'id valide")

    last_fid = fid
    clean_invalid_segments(segments_layer, compositions_layer)

def features_deleted(fids):
    """
    Nettoie les compositions des segments supprimés
    """
    clean_invalid_segments(segments_layer, compositions_layer)

#@timer_decorator
def start_script():
    global segments_layer, compositions_layer, id_field_index, segments_field_index, segments_column_name

    try:
        settings = QSettings()
        segments_layer_id = settings.value("network_manager/segments_layer_id", "")
        compositions_layer_id = settings.value("network_manager/compositions_layer_id", "")
        # segments_column_name = settings.value("network_manager/segments_column_name", "")

        log_debug(f"Démarrage du script avec:")
        log_debug(f"- ID segments: {segments_layer_id}")
        log_debug(f"- ID compositions: {compositions_layer_id}")
        log_debug(f"- Nom de la colonne segments: {segments_column_name}")

        project = QgsProject.instance()
        if not project:
            log_debug("Pas de projet QGIS ouvert")
            raise Exception("Aucun projet QGIS n'est ouvert")

        segments_layer = project.mapLayer(segments_layer_id)
        compositions_layer = project.mapLayer(compositions_layer_id)

        log_debug(f"Couches récupérées:")
        log_debug(f"- Segments: {segments_layer.name() if segments_layer else 'None'}")
        log_debug(f"- Compositions: {compositions_layer.name() if compositions_layer else 'None'}")

        if not segments_layer:
            log_debug("Couche segments non trouvée")
            raise Exception("Veuillez sélectionner une couche de segments valide")
        if not compositions_layer:
            log_debug("Couche compositions non trouvée")
            raise Exception("Veuillez sélectionner une couche de compositions valide")

        # Vérifier que ce sont des couches vectorielles
        if not isinstance(segments_layer, QgsVectorLayer):
            raise Exception("La couche de segments n'est pas une couche vectorielle valide")
        if not isinstance(compositions_layer, QgsVectorLayer):
            raise Exception("La couche de compositions n'est pas une couche vectorielle valide")

        log_debug(f"Segments Column Name: {segments_column_name}")
        # Vérifier les champs requis
        id_field_index = segments_layer.fields().indexOf('id')
        segments_field_index = compositions_layer.fields().indexOf(segments_column_name)

        if id_field_index == -1:
            raise Exception("Le champ 'id' n'a pas été trouvé dans la couche segments")
        if segments_field_index == -1:
            raise Exception(f"Le champ '{segments_column_name}' n'a pas été trouvé dans la couche compositions")

        segments_layer.featureAdded.connect(feature_added)
        segments_layer.featuresDeleted.connect(features_deleted)
        iface.messageBar().pushMessage("Info", "Le suivi par NetworkManager a démarré", level=Qgis.Info)
        return True

    except Exception as e:
        log_debug(f"Erreur lors du démarrage: {str(e)}")
        iface.messageBar().pushMessage("Erreur", str(e), level=Qgis.Critical)
        return False

def stop_script():
    global segments_layer, compositions_layer

    try:
        if segments_layer:
            segments_layer.featureAdded.disconnect(feature_added)
            segments_layer.featuresDeleted.disconnect(feature_deleted)
        segments_layer = None
        compositions_layer = None
    except:
        pass  # Ignore si déjà déconnecté
    iface.messageBar().pushMessage("Info", "Le suivi par NetworkManager est arrêté", level=Qgis.Info)

def show_dialog():
    dialog = NetworkManagerDialog(iface.mainWindow())
    dialog.show()
    return dialog

class NetworkManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Gestionnaire de réseaux")
        self.setMinimumWidth(400)
        self.script_running = False
        self.init_ui()
        self.load_settings()
        # Auto-démarrer le script au lancement si l'on coche la case correspondante.'
        project = QgsProject.instance()
        auto_start, _ = project.readBoolEntry("network_manager", "auto_start", False)
        self.auto_start_checkbox.setChecked(auto_start)

        # Auto-démarrer le script si configuré dans le projet
        if auto_start:
            QTimer.singleShot(100, self.toggle_script)

    def init_ui(self):
        layout = QVBoxLayout()

        # Groupe Configuration des couches
        layers_group = QGroupBox("Configuration des couches")
        layers_layout = QVBoxLayout()

        # Combo pour la couche segments
        segments_layout = QHBoxLayout()
        segments_layout.addWidget(QLabel("Couche segments:"))
        self.segments_combo = QComboBox()
        self.populate_layers_combo(self.segments_combo)
        segments_layout.addWidget(self.segments_combo)
        layers_layout.addLayout(segments_layout)

        # Combo pour la couche compositions
        compositions_layout = QHBoxLayout()
        compositions_layout.addWidget(QLabel("Couche compositions:"))
        self.compositions_combo = QComboBox()
        self.populate_layers_combo(self.compositions_combo)
        compositions_layout.addWidget(self.compositions_combo)
        layers_layout.addLayout(compositions_layout)

        layers_group.setLayout(layers_layout)
        layout.addWidget(layers_group)

        self.segments_column_combo = QComboBox()
        self.segments_column_combo.setPlaceholderText("Sélectionnez un champ")
        layout.addWidget(QLabel("Nom de l'attribut où sont renseignés les listes de segments:"))
        layout.addWidget(self.segments_column_combo)

        # Status
        self.status_label = QLabel("Status: Arrêté")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # Boutons de contrôle
        buttons_layout = QHBoxLayout()

        # Bouton Démarrer/Arrêter
        self.start_button = QPushButton("Démarrer")
        self.start_button.clicked.connect(self.toggle_script)
        self.start_button.setStyleSheet(self.get_start_button_style())
        buttons_layout.addWidget(self.start_button)

        # Bouton Info
        info_button = QPushButton("Info")
        info_button.clicked.connect(self.show_info)
        info_button.setStyleSheet("""
            QPushButton {
                background-color: #008CBA;
                color: white;
                padding: 5px;
                border-radius: 3px;
            }
            QPushButton:hover {
                background-color: #007399;
            }
        """)
        buttons_layout.addWidget(info_button)

        layout.addLayout(buttons_layout)

        # Style global
        self.setStyleSheet("""
            QDialog {
                background-color: #f0f0f0;
            }
            QLabel {
                color: #333;
            }
            QGroupBox {
                font-weight: bold;
                border: 1px solid #cccccc;
                margin-top: 1ex;
                padding-top: 1ex;
            }
        """)

        self.setLayout(layout)

        # Auto-start y/n
        self.auto_start_checkbox = QCheckBox("Démarrer automatiquement au lancement du projet")
        settings = QSettings()
        auto_start = settings.value("network_manager/auto_start", True, type=bool)
        self.auto_start_checkbox.setChecked(auto_start)
        self.auto_start_checkbox.stateChanged.connect(self.save_auto_start_setting)
        layout.addWidget(self.auto_start_checkbox)

        self.setLayout(layout)

        self.segments_combo.currentIndexChanged.connect(self.on_layer_selected)
        self.compositions_combo.currentIndexChanged.connect(self.on_layer_selected)

    def toggle_script(self):
        """Démarre ou arrête le script"""
        try:
            if not self.script_running:
                # Vérifier que les couches sont sélectionnées
                if not self.segments_combo.currentData() or not self.compositions_combo.currentData():
                    QMessageBox.warning(self, "Attention", "Veuillez sélectionner les couches segments et compositions")
                    return

                global segments_field_index
                segments_field_index = self.selected_compositions_layer.fields().indexOf(self.segments_column_combo.currentText())

                success = start_script()
                if success:
                    self.script_running = True
            else:
                stop_script()
                self.script_running = False
            self.update_ui_state()
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Une erreur est survenue: {str(e)}")

    def update_ui_state(self):
        """Met à jour l'interface selon l'état du script"""
        if self.script_running:
            self.start_button.setText("Arrêter")
            self.status_label.setText("Status: En cours d'exécution")
        else:
            self.start_button.setText("Démarrer")
            self.status_label.setText("Status: Arrêté")
        self.start_button.setStyleSheet(self.get_start_button_style())

    def populate_layers_combo(self, combo):
        combo.clear()
        log_debug(f"Remplissage du combo {combo.objectName()}")

        # Récupérer toutes les couches du projet
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                combo.addItem(layer.name(), layer.id())
                log_debug(f"Ajout couche: {layer.name()} (ID: {layer.id()})")

    def populate_field_combo(self):
        composition_layer = self.selected_compositions_layer
        if composition_layer:
            self.segments_column_combo.clear()
            field_names = composition_layer.fields().names()
            self.segments_column_combo.addItems(field_names)

    def on_layer_selected(self):
        """Méthode appelée quand une couche est sélectionnée dans les combobox"""
        segments_id = self.segments_combo.currentData()
        compositions_id = self.compositions_combo.currentData()

        log_debug(f"Sélection des couches:")
        log_debug(f"- ID couche segments: {segments_id}")
        log_debug(f"- ID couche compositions: {compositions_id}")

        self.selected_segments_layer = QgsProject.instance().mapLayer(segments_id)
        self.selected_compositions_layer = QgsProject.instance().mapLayer(compositions_id)

        self.populate_field_combo()
        if self.segments_column_combo.currentText():  # Vérifiez que quelque chose est sélectionné
            global segments_field_index
            segments_field_index = self.selected_compositions_layer.fields().indexOf(self.segments_column_combo.currentText())

        log_debug(f"Couches récupérées:")
        log_debug(f"- Segments: {self.selected_segments_layer.name() if self.selected_segments_layer else 'None'}")
        log_debug(f"- Compositions: {self.selected_compositions_layer.name() if self.selected_compositions_layer else 'None'}")

        # Sauvegarder les sélections
        settings = QSettings()
        settings.setValue("network_manager/segments_layer_id", segments_id)
        settings.setValue("network_manager/compositions_layer_id", compositions_id)
        settings.setValue("network_manager/segments_column_name", self.segments_column_combo.currentText())

        log_debug("Settings sauvegardés")

    def load_settings(self):
        settings = QSettings()
        segments_layer_id = settings.value("network_manager/segments_layer_id", "")
        compositions_layer_id = settings.value("network_manager/compositions_layer_id", "")

        log_debug(f"Chargement des settings:")
        log_debug(f"- ID segments sauvegardé: {segments_layer_id}")
        log_debug(f"- ID compositions sauvegardé: {compositions_layer_id}")

        segments_index = self.segments_combo.findData(segments_layer_id)
        compositions_index = self.compositions_combo.findData(compositions_layer_id)

        log_debug(f"Index trouvés:")
        log_debug(f"- Index segments: {segments_index}")
        log_debug(f"- Index compositions: {compositions_index}")

        if segments_index >= 0:
            self.segments_combo.setCurrentIndex(segments_index)
            log_debug(f"Index segments défini: {segments_index}")
        if compositions_index >= 0:
            self.compositions_combo.setCurrentIndex(compositions_index)
            log_debug(f"Index compositions défini: {compositions_index}")

    def save_settings(self):
        settings = QSettings()
        settings.setValue("network_manager/segments_layer", self.segments_combo.currentText())
        settings.setValue("network_manager/compositions_layer", self.compositions_combo.currentText())
        settings.setValue("network_manager/segments_column_name", self.segments_column_combo.currentText())

    def get_start_button_style(self):
        if not self.script_running:
            return """
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
            """
        else:
            return """
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    padding: 5px;
                    border-radius: 3px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
            """

    def show_info(self):
        info_text = """
        Gestionnaire de réseaux

        Ce plugin apporte une assistance dans
        la réalisation de réseaux en mettant à jour
        les compositions de segments en fonction
        des modifications faites sur les segments.

        Instructions :
        1. Sélectionnez les couches à utiliser
            (La couche des compositions doit avoir
            un champ nommé "segments")
        2. Cliquez sur 'Démarrer' pour activer le suivi
        3. Effectuez vos modifications sur les segments
        4. Les compositions seront mises à jour automatiquement
        5. Cliquez sur 'Arrêter' pour désactiver le suivi
        """
        QMessageBox.information(self, "Information", info_text)

    def closeEvent(self, a0):
        a0.accept()

    def save_auto_start_setting(self, state):
        project = QgsProject.instance()
        project.writeEntry("network_manager", "auto_start", bool(state))
        # Marquer le projet comme modifié pour s'assurer que le changement est sauvegardé
        project.setDirty(True)

def log_debug(message):
    """Fonction utilitaire pour le logging"""
    print(f"[DEBUG] {message}")
