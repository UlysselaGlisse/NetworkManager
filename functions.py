from ast import Raise
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    Qgis,
    QgsFeatureRequest,
    QgsWkbTypes,
    QgsSpatialIndex,
    QgsGeometry
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
from .utils import get_features_list, timer_decorator
from . import config
import traceback


def get_compositions_list_segments(segment_id, compositions_layer, segments_field_name):
    """Récupère toutes les listes de segments contenant l'id du segment divisé"""
    if not segment_id:
        return []

    all_segments_lists = []

    request = QgsFeatureRequest()
    expression = f"{segments_field_name} LIKE '%,{segment_id},%' OR {segments_field_name} LIKE '{segment_id},%' OR {segments_field_name} LIKE '%,{segment_id}' OR {segments_field_name} = '{segment_id}'"
    request.setFilterExpression(expression)

    features = get_features_list(compositions_layer, request)

    for feature in features:
        segments_str = feature[segments_field_name]

        if not segments_str:
            continue

        try:
            segments_ids = [int(id.strip()) for id in str(segments_str).split(',')]

            if int(segment_id) in segments_ids:
                all_segments_lists.append(segments_ids)
            else:
                print(f"Segment {segment_id} non trouvé dans cette liste")

        except Exception as e:
            print(f"Erreur lors du traitement de la composition {feature.id()}: {str(e)}")

    return all_segments_lists

def update_compositions_segments(segments_layer, compositions_layer, segments_field_name, segments_field_index, old_id, new_id, original_feature, new_feature, segment_lists):
    """Met à jour les compositions après division d'un segment"""
    compositions_layer.startEditing()

    original_geom = original_feature.geometry()
    new_geom = new_feature.geometry()

    compositions_dict = {feature[segments_field_name]: feature.id() for feature in compositions_layer.getFeatures()}
    for segments_list in segment_lists:
        try:
            old_index = segments_list.index(int(old_id))

            # Pour vérifier l'orientation du segment on doit d'abord vérifier si c'est le dernier de la liste
            # car une logique différente s'applique dans ce cas.
            if old_index < len(segments_list) - 1:
                segment_geom = original_geom
                original_geometry = True
            else:
                segment_geom = new_geom
                original_geometry = False

            # Vérifier l'orientation
            is_correctly_oriented = check_segment_orientation(segments_layer, segment_geom, original_geometry, segments_list, old_index)

            # On ajuste la nouvelle liste en fonction de l'orientation du segment.'
            new_segments_list = segments_list.copy()
            if is_correctly_oriented:
                new_segments_list[old_index:old_index+1] = [int(old_id), int(new_id)]
            else:
                new_segments_list[old_index:old_index+1] = [int(new_id), int(old_id)]

            # Mettre à jour la composition
            composition_id = compositions_dict.get(','.join(map(str, segments_list)))
            if composition_id:
                compositions_layer.changeAttributeValue(
                    composition_id,
                    segments_field_index,
                    ','.join(map(str, new_segments_list))
            )
        except Exception as e:
            raise Exception("La composition .. n'a pa pu être mis-à-jour")

def check_segment_orientation(segments_layer, segment_geom, old_or_new, segments_list, old_index):
    """Vérifie si un segment est orienté correctement par rapport aux segments adjacents"""
    segment_points = segment_geom.asPolyline()

    if old_or_new == True:
        next_id = segments_list[old_index + 1] if old_index < len(segments_list) - 1 else None

        expression = f"\"id\" = '{next_id}'"
        request = QgsFeatureRequest().setFilterExpression(expression)
        next_feature = next(segments_layer.getFeatures(request), None)

        if next_feature:
            next_geom = next_feature.geometry()
        else:
            next_geom = None

        # Vérifier avec le segment suivant
        if next_geom and not next_geom.isEmpty():
            next_points = next_geom.asPolyline()

            if segment_points[0].distance(next_points[0]) < 0.01 or segment_points[0].distance(next_points[-1]) < 0.01:
                return False

    if old_or_new == False:
        prev_id = segments_list[old_index - 1]

        expression = f"\"id\" = '{prev_id}'"
        request = QgsFeatureRequest().setFilterExpression(expression)
        prev_feature = next(segments_layer.getFeatures(request), None)

        if prev_feature:
            prev_geom = prev_feature.geometry()
        else:
            prev_geom = None
        # Vérifier avec le segment précédent
        if prev_geom and not prev_geom.isEmpty():
            prev_points = prev_geom.asPolyline()
            # Si le dernier point du segment précédent plus éloigné du premier du segment original que du dernier, alors à l'envers.'
            if segment_points[-1].distance(prev_points[0]) < 0.01 or segment_points[-1].distance(prev_points[-1]) < 0.01:
                return False

    return True

def process_single_segment_composition(segments_layer, compositions_layer, segments_field_name, segments_field_index, fid, old_id, new_id, segments_list):
    """Gère le cas d'une composition d'un seul segment"""

    class SingleSegmentDialog(QDialog):
        def __init__(self, parent=None):
            super().__init__(parent)
            self.setWindowTitle("Vérification nécessaire")
            self.setMinimumWidth(400)
            self.current_segments = [old_id, new_id]
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
            self.proposal_label.setText(f"Nouvelle composition proposée: {self.current_segments}")

        def invert_order(self):
            self.current_segments.reverse()
            self.update_proposal_label()
            self.update_proposal_label()

    dialog = SingleSegmentDialog()
    result = dialog.exec_()

    if result == QDialog.Accepted:
        # Rechercher la composition qui contient ce segment
        expression = f"{segments_field_name} = '{old_id}'"
        request = QgsFeatureRequest().setFilterExpression(expression)
        composition_feature = next(compositions_layer.getFeatures(request), None)

        if composition_feature:
            try:
                new_segments_str = ','.join(map(str, dialog.current_segments))
                compositions_layer.startEditing()
                success = compositions_layer.changeAttributeValue(
                    composition_feature.id(),
                    segments_field_index,
                    new_segments_str
                )
            except Exception as e:
                iface.messageBar().pushMessage(
                    "Erreur",
                    f"Erreur lors de la mise à jour de la composition: {str(e)}",
                    level=Qgis.MessageLevel.Critical
                )
        else:
            iface.messageBar().pushMessage(
                "Attention",
                f"Aucune composition trouvée avec le segment {old_id}",
                level=Qgis.MessageLevel.Warning
            )
        return dialog.current_segments
    else:
        return None

def clean_invalid_segments(segments_layer, compositions_layer, segments_field_name, segments_field_index) -> None:
    """Supprime les références aux segments qui n'existent plus dans la table segments"""
    valid_segments_ids = {str(f['id']) for f in get_features_list(segments_layer) if f['id'] is not None}
    compositions = get_features_list(compositions_layer)

    compositions_layer.startEditing()
    for composition in compositions:
        segments_str = composition[segments_field_name]
        if segments_str is None or str(segments_str).upper() == 'NULL' or not segments_str:
            continue

        segments_list = str(segments_str).split(',')
        valid_segments = [seg.strip() for seg in segments_list if seg.strip() in valid_segments_ids]

        if len(valid_segments) != len(segments_list):
            new_segments_str = ','.join(valid_segments)
            compositions_layer.changeAttributeValue(
                composition.id(),
                segments_field_index,
                new_segments_str
            )

def has_duplicate_segment_id(segments_layer, segment_id) -> bool:
    """Vérifie si un id de segments existe plusieurs fois. Si oui, il s'agit d'un segment divisé."""

    expression = f"\"id\" = '{segment_id}'"
    request = QgsFeatureRequest().setFilterExpression(expression)
    request.setLimit(2)

    features = get_features_list(segments_layer, request)
    return len(features) > 1

def update_segment_id(segments_layer, fid, next_id, id_field_index):
    """Met à jour l'id des segments divisés."""
    segments_layer.startEditing()
    segments_layer.changeAttributeValue(fid,
        id_field_index,
        str(next_id))

def get_next_id(segments_layer, id_field_index):
    next_id = int(segments_layer.maximumValue(id_field_index))
    return next_id + 1
