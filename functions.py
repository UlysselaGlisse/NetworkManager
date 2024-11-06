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
from .utils import get_features_list

def get_compositions_list_segments(segment_id, compositions_layer):
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

def update_compositions_segments(segments_layer, compositions_layer, old_id, new_id, original_feature, new_feature, segment_lists):
    """
    Met à jour les compositions après division d'un segment
    """
    #print(f"\nMise à jour des compositions:")
    #print(f"- Ancien ID: {old_id}")
    #print(f"- Nouvel ID: {new_id}")

    compositions_layer.startEditing()

    original_geom = original_feature.geometry()
    new_geom = new_feature.geometry()

    compositions_dict = {feature['segments']: feature.id() for feature in compositions_layer.getFeatures()}

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
            composition_id = compositions_dict.get(','.join(map(str, segments_list)))
            if composition_id:
                compositions_layer.changeAttributeValue(
                    composition_id,
                    compositions_layer.fields().indexOf('segments'),
                    ','.join(map(str, new_segments_list))
                )
                #print(f"Mise à jour réussie: {result}")
            else:
                print("ERREUR: Composition non trouvée")

        except Exception as e:
            print(f"ERREUR lors de la mise à jour: {str(e)}")


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


def process_single_segment_composition(segments_layer, compositions_layer, fid, old_id, new_id, segments_list):
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
def clean_invalid_segments(segments_layer, compositions_layer) -> None:
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
def has_duplicate_segment_id(segments_layer, segment_id: str) -> bool:
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
def update_segment_id(segments_layer, fid, next_id):
    """
    Met à jour l'id des segments divisés.
    """
    segments_layer.startEditing()
    segments_layer.changeAttributeValue(fid,
        segments_layer.fields().indexOf('id'),
        str(next_id))

#@timer_decorator
def get_next_id(segments_layer):

    next_id = int(segments_layer.maximumValue(segments_layer.fields().indexOf('id')))
    return next_id + 1
