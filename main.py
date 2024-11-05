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
)
from qgis.PyQt.QtGui import QCloseEvent
from qgis.PyQt.QtCore import Qt, QTimer, QSettings
from typing import Literal, Optional, cast
from .utils import timer_decorator, print_geometry_info, get_features_list

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

    #print(f"ID du segment: {segment_id}")

    if segment_id and has_duplicate_segment_id(segment_id):
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
            segment_lists = get_compositions_list_segments(segment_id)
            #print(f"Nombre de compositions trouvées: {len(segment_lists)}")

            if segment_lists:
                #print(segment_lists)
                next_id = get_next_id()
                #print(f"Nouvel ID à attribuer: {next_id}")

                update_segment_id(fid, next_id)
                segment_unique = None

                for segments_list in segment_lists:
                    if len(segments_list) == 1:
                        segment_unique = True

                if segment_unique == True:
                    #log_debug("Composition à segment unique détectée - Traitement spécial")
                    new_segments = process_single_segment_composition(fid, segment_id, next_id, segments_list)
                    if new_segments is None:
                        pass
                else:
                    update_compositions_segments(segment_id, next_id, original_feature, source_feature, segment_lists)

            else:
                print("ATTENTION: Aucune composition trouvée pour ce segment")
        else:
            print("ERREUR: Segment original non trouvé")
    else:
        print("Le segment n'est pas un doublon ou n'a pas d'id valide")

    last_fid = fid
    clean_invalid_segments()

#@timer_decorator
def get_compositions_list_segments(segment_id):
    """
    Récupère toutes les listes de segments contenant l'id du segment divisé
    """
    if not segment_id:
        return []

    all_segments_lists = []

    #print(f"\nRecherche du segment {segment_id} dans les compositions")

    request = QgsFeatureRequest()
    expression = f"segments LIKE '%,{segment_id},%' OR segments LIKE '{segment_id},%' OR segments LIKE '%,{segment_id}' OR segments = '{segment_id}'"
    request.setFilterExpression(expression)

    features = get_features_list(compositions_layer, request)

    #print(f"Nombre de compositions trouvées avec la requête: {len(features)}")

    for feature in features:
        segments_str = feature['segments']
        #print(f"\nExamen de la composition {feature.id()}:")
        #print(f"Liste brute: {segments_str}")

        if not segments_str:
            #print("Liste vide, ignorée")
            continue

        try:
            segments_ids = [int(id.strip()) for id in str(segments_str).split(',')]
            #print(f"Liste convertie: {segments_ids}")

            if int(segment_id) in segments_ids:
                #print(f"Segment {segment_id} trouvé dans la composition {feature.id()}")
                all_segments_lists.append(segments_ids)
            else:
                print(f"Segment {segment_id} non trouvé dans cette liste")

        except Exception as e:
            print(f"Erreur lors du traitement de la composition {feature.id()}: {str(e)}")

    #print(f"\nNombre total de listes trouvées: {len(all_segments_lists)}")
    return all_segments_lists

#@timer_decorator
def update_compositions_segments(old_id, new_id, original_feature, new_feature, segment_lists):
    """
    Met à jour les compositions après division d'un segment
    """
    #print(f"\nMise à jour des compositions:")
    #print(f"- Ancien ID: {old_id}")
    #print(f"- Nouvel ID: {new_id}")

    compositions_layer.startEditing()

    original_geom = original_feature.geometry()
    new_geom = new_feature.geometry()

    for segments_list in segment_lists:
        #print(f"\nTraitement liste: {segments_list}")
        try:
            old_index = segments_list.index(int(old_id))
            #print(f"Position du segment dans la liste: {old_index}")

            # Vérifier l'orientation
            prev_geom = segments_layer.getFeature(segments_list[old_index - 1]).geometry() if old_index > 0 else None
            next_geom = segments_layer.getFeature(segments_list[old_index + 1]).geometry() if old_index < len(segments_list) - 1 else None

            is_correctly_oriented = check_segment_orientation(
                original_geom if old_index > 0 else new_geom,
                prev_geom,
                next_geom
            )
            #print(f"Orientation correcte: {is_correctly_oriented}")

            new_segments_list = segments_list.copy()

            if is_correctly_oriented:
                new_segments_list[old_index:old_index+1] = [int(old_id), int(new_id)]
            else:
                new_segments_list[old_index:old_index+1] = [int(new_id), int(old_id)]

            #print(f"Nouvelle liste: {new_segments_list}")

            # Mettre à jour la composition
            request = QgsFeatureRequest().setFilterExpression(f"segments = '{','.join(map(str, segments_list))}'")
            composition_feature = next(compositions_layer.getFeatures(request), None)

            if composition_feature:
                result = compositions_layer.changeAttributeValue(
                    composition_feature.id(),
                    compositions_layer.fields().indexOf('segments'),
                    ','.join(map(str, new_segments_list))
                )
                #print(f"Mise à jour réussie: {result}")
            else:
                print("ERREUR: Composition non trouvée")

        except Exception as e:
            print(f"ERREUR lors de la mise à jour: {str(e)}")

def process_single_segment_composition(fid, old_id, new_id, segments_list):
    """Gère le cas d'une composition à segment unique """

    #log_debug(f"\nDémarrage process_single_segment_composition:")
    #log_debug(f"- FID: {fid}")
    #log_debug(f"- Ancien ID: {old_id}")
    #log_debug(f"- Nouvel ID: {new_id}")
    #log_debug(f"- Liste segments: {segments_list}")


    class SingleSegmentDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Vérification nécessaire")
            self.setMinimumWidth(400)
            self.current_segments = [old_id, new_id]
            #log_debug(f"Initialisation dialog avec segments: {self.current_segments}")
            self.setup_ui()

        def setup_ui(self):
            layout = QVBoxLayout()

            # Message d'avertissement
            warning_label = QLabel("Attention, composition d'un seul segment. "
                                 "Veuillez vérifier que la nouvelle composition est bonne.")
            warning_label.setWordWrap(True)
            layout.addWidget(warning_label)

            # Affichage de la proposition
            self.proposal_label = QLabel()
            self.update_proposal_label()
            layout.addWidget(self.proposal_label)

            # Boutons
            buttons_layout = QHBoxLayout()

            invert_button = QPushButton("Inverser l'ordre")
            invert_button.clicked.connect(self.invert_order)
            buttons_layout.addWidget(invert_button)

            ok_button = QPushButton("OK")
            ok_button.clicked.connect(self.accept)
            buttons_layout.addWidget(ok_button)

            cancel_button = QPushButton("Annuler")
            cancel_button.clicked.connect(self.reject)
            buttons_layout.addWidget(cancel_button)

            layout.addLayout(buttons_layout)
            self.setLayout(layout)

        def update_proposal_label(self):
            #log_debug(f"Mise à jour label avec segments: {self.current_segments}")
            self.proposal_label.setText(f"Nouvelle composition proposée: {self.current_segments}")

        def invert_order(self):
            #log_debug(f"Inversion de l'ordre des segments")
            #log_debug(f"Avant inversion: {self.current_segments}")
            self.current_segments.reverse()
            self.update_proposal_label()
            #log_debug(f"Après inversion: {self.current_segments}")
            self.update_proposal_label()

    dialog = SingleSegmentDialog()
    result = dialog.exec_()

    if result == QDialog.Accepted:
        #log_debug("Dialog accepté")
        # Rechercher la composition qui contient ce segment
        expression = f"segments = '{old_id}'"
        #log_debug(f"Recherche composition avec expression: {expression}")
        request = QgsFeatureRequest().setFilterExpression(expression)
        composition_feature = next(compositions_layer.getFeatures(request), None)

        if composition_feature:
            #log_debug(f"Composition trouvée: ID={composition_feature.id()}")
            #log_debug(f"Ancienne valeur segments: {composition_feature['segments']}")

            try:
                new_segments_str = ','.join(map(str, dialog.current_segments))
                #log_debug(f"Nouvelle valeur segments à appliquer: {new_segments_str}")

                compositions_layer.startEditing()
                segments_field_idx = compositions_layer.fields().indexOf('segments')
                #log_debug(f"Index du champ segments: {segments_field_idx}")

                success = compositions_layer.changeAttributeValue(
                    composition_feature.id(),
                    segments_field_idx,
                    new_segments_str
                )

                #log_debug(f"Résultat de la mise à jour: {'Succès' if success else 'Échec'}")

            except Exception as e:
                #log_debug(f"ERREUR lors de la mise à jour: {str(e)}")
                iface.messageBar().pushMessage(
                    "Erreur",
                    f"Erreur lors de la mise à jour de la composition: {str(e)}",
                    level=Qgis.MessageLevel.Critical
                )
        else:
            #log_debug(f"Aucune composition trouvée avec le segment {old_id}")
            iface.messageBar().pushMessage(
                "Attention",
                f"Aucune composition trouvée avec le segment {old_id}",
                level=Qgis.MessageLevel.Warning
            )

        #log_debug(f"Retour des segments: {dialog.current_segments}")
        return dialog.current_segments
    else:
        #log_debug("Dialog annulé")
        return None

#@timer_decorator
def clean_invalid_segments() -> None:
    """
    Supprime les références aux segments qui n'existent plus dans la table segments
    """
    valid_segments_ids = {str(f['id']) for f in get_features_list(segments_layer) if f['id'] is not None}
    compositions = get_features_list(compositions_layer)

    compositions_layer.startEditing()
    for composition in compositions:
        segments_str = composition['segments']
        if segments_str is None or str(segments_str).upper() == 'NULL' or not segments_str:
            continue

        segments_list = str(segments_str).split(',')
        valid_segments = [seg.strip() for seg in segments_list if seg.strip() in valid_segments_ids]

        if len(valid_segments) != len(segments_list):
            new_segments_str = ','.join(valid_segments)
            compositions_layer.changeAttributeValue(
                composition.id(),
                composition.fields().indexOf('segments'),
                new_segments_str
            )

#@timer_decorator
def has_duplicate_segment_id(segment_id: str) -> bool:
    """
    Vérifie si un id de segments existe plusieurs fois. Si oui, il s'agit d'un segment divisé.
    Args:
    """

    expression = f"\"id\" = '{segment_id}'"
    request = QgsFeatureRequest().setFilterExpression(expression)
    request.setLimit(2)

    features = get_features_list(segments_layer, request)
    return len(features) > 1

#@timer_decorator
def update_segment_id(fid, next_id):
    """
    Met à jour l'id des segments divisés.
    """
    segments_layer.startEditing()
    segments_layer.changeAttributeValue(fid,
        segments_layer.fields().indexOf('id'),
        str(next_id))

#@timer_decorator
def get_next_id():

    next_id = int(segments_layer.maximumValue(segments_layer.fields().indexOf('id')))
    return next_id + 1

#@timer_decorator
def check_segment_orientation(segment_geom, prev_segment_geom=None, next_segment_geom=None):
    """
    Vérifie si un segment est orienté correctement par rapport aux segments adjacents.
    """
    if segment_geom.isEmpty():
        return True

    segment_points = segment_geom.asPolyline()

    # Vérifier avec le segment précédent
    if prev_segment_geom and not prev_segment_geom.isEmpty():
        prev_points = prev_segment_geom.asPolyline()
        if prev_points[-1].distance(segment_points[0]) > prev_points[-1].distance(segment_points[-1]):
            return False

    # Vérifier avec le segment suivant
    if next_segment_geom and not next_segment_geom.isEmpty():
        next_points = next_segment_geom.asPolyline()
        if segment_points[-1].distance(next_points[0]) > segment_points[0].distance(next_points[0]):
            return False

    return True

#@timer_decorator
def start_script():
    global segments_layer, compositions_layer, id_field_index, segments_field_index

    try:
        settings = QSettings()
        segments_layer_id = settings.value("network_manager/segments_layer_id", "")
        compositions_layer_id = settings.value("network_manager/compositions_layer_id", "")

        #log_debug(f"Démarrage du script avec:")
        #log_debug(f"- ID segments: {segments_layer_id}")
        #log_debug(f"- ID compositions: {compositions_layer_id}")

        project = QgsProject.instance()
        if not project:
            #log_debug("Pas de projet QGIS ouvert")
            raise Exception("Aucun projet QGIS n'est ouvert")

        # Correction ici : on assigne directement à segments_layer et compositions_layer
        segments_layer = project.mapLayer(segments_layer_id)
        compositions_layer = project.mapLayer(compositions_layer_id)

        #log_debug(f"Couches récupérées:")
        #log_debug(f"- Segments: {segments_layer.name() if segments_layer else 'None'}")
        #log_debug(f"- Compositions: {compositions_layer.name() if compositions_layer else 'None'}")

        if not segments_layer:
            #log_debug("Couche segments non trouvée")
            raise Exception("Veuillez sélectionner une couche de segments valide")
        if not compositions_layer:
            #log_debug("Couche compositions non trouvée")
            raise Exception("Veuillez sélectionner une couche de compositions valide")

        # Vérifier que ce sont des couches vectorielles
        if not isinstance(segments_layer, QgsVectorLayer):
            raise Exception("La couche de segments n'est pas une couche vectorielle valide")
        if not isinstance(compositions_layer, QgsVectorLayer):
            raise Exception("La couche de compositions n'est pas une couche vectorielle valide")

        # Vérifier les champs requis
        id_field_index = segments_layer.fields().indexOf('id')
        segments_field_index = compositions_layer.fields().indexOf('segments')

        if id_field_index == -1:
            raise Exception("Le champ 'id' n'a pas été trouvé dans la couche segments")
        if segments_field_index == -1:
            raise Exception("Le champ 'segments' n'a pas été trouvé dans la couche compositions")

        segments_layer.featureAdded.connect(feature_added)
        iface.messageBar().pushMessage("Info", "Le suivi par NetworkManager a démarré", level=Qgis.Info)
        return True

    except Exception as e:
        #log_debug(f"Erreur lors du démarrage: {str(e)}")
        iface.messageBar().pushMessage("Erreur", str(e), level=Qgis.Critical)
        return False

def stop_script():
    global segments_layer, compositions_layer

    try:
        if segments_layer:
            segments_layer.featureAdded.disconnect(feature_added)
        segments_layer = None
        compositions_layer = None
    except:
        pass  # Ignore si déjà déconnecté
    iface.messageBar().pushMessage("Info", "Le suivi par NetworkManager est arrêté", level=Qgis.Info)

def show_dialog():
    dialog = SplitMergeDialog(iface.mainWindow())
    dialog.show()
    return dialog

class SplitMergeDialog(QDialog):
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
        #log_debug(f"Remplissage du combo {combo.objectName()}")

        # Récupérer toutes les couches du projet
        for layer in QgsProject.instance().mapLayers().values():
            if isinstance(layer, QgsVectorLayer):
                combo.addItem(layer.name(), layer.id())
                #log_debug(f"Ajout couche: {layer.name()} (ID: {layer.id()})")

    def on_layer_selected(self):
        """Méthode appelée quand une couche est sélectionnée dans les combobox"""
        segments_id = self.segments_combo.currentData()
        compositions_id = self.compositions_combo.currentData()

        #log_debug(f"Sélection des couches:")
        #log_debug(f"- ID couche segments: {segments_id}")
        #log_debug(f"- ID couche compositions: {compositions_id}")

        self.selected_segments_layer = QgsProject.instance().mapLayer(segments_id)
        self.selected_compositions_layer = QgsProject.instance().mapLayer(compositions_id)

        #log_debug(f"Couches récupérées:")
        #log_debug(f"- Segments: {self.selected_segments_layer.name() if self.selected_segments_layer else 'None'}")
        #log_debug(f"- Compositions: {self.selected_compositions_layer.name() if self.selected_compositions_layer else 'None'}")

        # Sauvegarder les sélections
        settings = QSettings()
        settings.setValue("network_manager/segments_layer_id", segments_id)
        settings.setValue("network_manager/compositions_layer_id", compositions_id)

        #log_debug("Settings sauvegardés")

    def load_settings(self):
        settings = QSettings()
        segments_layer_id = settings.value("network_manager/segments_layer_id", "")
        compositions_layer_id = settings.value("network_manager/compositions_layer_id", "")

        #log_debug(f"Chargement des settings:")
        #log_debug(f"- ID segments sauvegardé: {segments_layer_id}")
        #log_debug(f"- ID compositions sauvegardé: {compositions_layer_id}")

        segments_index = self.segments_combo.findData(segments_layer_id)
        compositions_index = self.compositions_combo.findData(compositions_layer_id)

        #log_debug(f"Index trouvés:")
        #log_debug(f"- Index segments: {segments_index}")
        #log_debug(f"- Index compositions: {compositions_index}")

        if segments_index >= 0:
            self.segments_combo.setCurrentIndex(segments_index)
            #log_debug(f"Index segments défini: {segments_index}")
        if compositions_index >= 0:
            self.compositions_combo.setCurrentIndex(compositions_index)
            #log_debug(f"Index compositions défini: {compositions_index}")

    def save_settings(self):
        settings = QSettings()
        settings.setValue("network_manager/segments_layer", self.segments_combo.currentText())
        settings.setValue("network_manager/compositions_layer", self.compositions_combo.currentText())

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

# def #log_debug(message):
#     """Fonction utilitaire pour le logging"""
#     print(f"[DEBUG] {message}")
