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
from . import config

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

    print(f"\n{'='*50}")
    print(f"Traitement nouvelle entité FID={fid}")
    print(f"{'='*50}")

    source_feature = segments_layer.getFeature(fid)
    if not source_feature.isValid():
          print("ERREUR: La feature source n'est pas valide")
          return

    if not source_feature.fields().names():
        print("ERREUR: Pas de champs dans la feature source")
        return

    attributes = source_feature.attributes()
    print(f"Attributs de la feature: {attributes}")
    print(f"Nombre d'attributs: {len(attributes)}")
    field_names = [field.name() for field in segments_layer.fields()]
    print(f"Noms des champs de la couche segments: {field_names}")

    segments_field_index = config.get_segments_field_index()
    print(segments_field_index)

    if len(attributes) <= segments_field_index:
        print(f"ERREUR: segments_field_index ({segments_field_index}) est hors limites pour le nombre d'attributs ({len(attributes)})")
        return

    segment_id = source_feature.attributes()[segments_field_index]

    print(f"ID du segment: {segment_id}")

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
@staticmethod
def start_script():
    global segments_layer, compositions_layer, id_field_index
    try:
        settings = QSettings()
        segments_layer_id = settings.value("network_manager/segments_layer_id", "")
        compositions_layer_id = settings.value("network_manager/compositions_layer_id", "")
        segments_column_name = settings.value("network_manager/segments_column_name", "segments")

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

        if not isinstance(compositions_layer, QgsVectorLayer):
            raise Exception("La couche compositions n'est pas une couche vectorielle")

        fields = compositions_layer.fields()
        field_count = fields.count()

        # Récupération du nom de la colonne segments
        segments_column_name = settings.value("network_manager/segments_column_name", "segments")

        # Vérification de l'existence du champ
        field_index = fields.indexOf(segments_column_name)
        if field_index == -1:
            raise Exception(f"Le champ '{segments_column_name}' n'existe pas dans la couche compositions")

        # Afficher des informations de debug
        log_debug(f"Nombre total de champs: {field_count}")
        log_debug(f"Index du champ '{segments_column_name}': {field_index}")

        # Mise à jour de l'index
        segments_field_index = field_index
        config.set_segments_field_index(segments_field_index)

        print(f"Valeur de segments_field_index dans config.py {config.segments_field_index}")

        log_debug(f"segments_field_index mis à jour: {segments_field_index}")

        # Vérifier les champs requis
        id_field_index = segments_layer.fields().indexOf('id')

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

        # Groupe Configuration colonne segments
        column_group = QGroupBox("Configuration colonne segments")
        column_layout = QVBoxLayout()

        self.segments_column_combo = QComboBox()
        column_layout.addWidget(QLabel("Colonne contenant les segments:"))
        column_layout.addWidget(self.segments_column_combo)

        column_group.setLayout(column_layout)
        layout.addWidget(column_group)

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

        # Connexions des signaux
        self.segments_combo.currentIndexChanged.connect(self.on_layer_selected)
        self.compositions_combo.currentIndexChanged.connect(self.on_layer_selected)
        self.segments_column_combo.currentTextChanged.connect(self.on_column_selected)

        self.setLayout(layout)

    def toggle_script(self):
        """Démarre ou arrête le script"""
        try:
            if not self.script_running:
                # Vérifier que les couches sont sélectionnées
                if not self.segments_combo.currentData() or not self.compositions_combo.currentData():
                    QMessageBox.warning(self, "Attention", "Veuillez sélectionner les couches segments et compositions")
                    return

                if not self.segments_column_combo.currentText():
                    QMessageBox.warning(self, "Attention", "Veuillez sélectionner la colonne segments")
                    return

                # Sauvegarder la colonne segments sélectionnée
                settings = QSettings()
                settings.setValue("network_manager/segments_column_name", self.segments_column_combo.currentText())

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
        if not hasattr(self, 'segments_column_combo'):
            return

        self.segments_column_combo.clear()

        if isinstance(self.selected_compositions_layer, QgsVectorLayer):
            field_names = [field.name() for field in self.selected_compositions_layer.fields()]
            self.segments_column_combo.addItems(field_names)

            # Restaurer la sélection précédente
            settings = QSettings()
            saved_column = settings.value("network_manager/segments_column_name", "segments")
            index = self.segments_column_combo.findText(saved_column)
            if index >= 0:
                self.segments_column_combo.setCurrentIndex(index)

    def on_layer_selected(self):
        """Méthode appelée quand une couche est sélectionnée dans les combobox"""
        segments_id = self.segments_combo.currentData()
        compositions_id = self.compositions_combo.currentData()

        project = QgsProject.instance()
        if project:
            self.selected_segments_layer = project.mapLayer(segments_id)
            self.selected_compositions_layer = project.mapLayer(compositions_id)

            if isinstance(self.selected_compositions_layer, QgsVectorLayer):
                self.populate_field_combo()

            # Sauvegarder les sélections
            settings = QSettings()
            settings.setValue("network_manager/segments_layer_id", segments_id)
            settings.setValue("network_manager/compositions_layer_id", compositions_id)

    def on_column_selected(self):
        """Méthode appelée quand une colonne est sélectionnée"""
        if self.segments_column_combo.currentText():
            selected_column = self.segments_column_combo.currentText()
            settings = QSettings()
            settings.setValue("network_manager/segments_column_name", selected_column)

            if isinstance(self.selected_compositions_layer, QgsVectorLayer):
                fields = self.selected_compositions_layer.fields()
                field_index = fields.indexOf(selected_column)

                if field_index != -1:
                    segments_field_index = field_index
                    config.set_segments_field_index(segments_field_index)
                    log_debug(f"Nouvel index pour le champ segments : {segments_field_index}")
                else:
                    log_debug(f"ERREUR: Champ {selected_column} non trouvé")

    def load_settings(self):
        settings = QSettings()
        segments_layer_id = settings.value("network_manager/segments_layer_id", "")
        compositions_layer_id = settings.value("network_manager/compositions_layer_id", "")
        saved_column = settings.value("network_manager/segments_column_name", "segments")

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
        if hasattr(self, 'segments_column_combo'):
            index = self.segments_column_combo.findText(saved_column)
            if index >= 0:
                self.segments_column_combo.setCurrentIndex(index)

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
