"""Create ui and features to list_constructor by cliking on canvas."""

from qgis.core import (
    QgsApplication,
    QgsCoordinateTransform,
    QgsFeatureRequest,
    QgsGeometry,
    QgsPointXY,
    QgsProject,
    QgsRectangle,
    QgsSpatialIndex,
    QgsVectorLayerUtils,
)
from qgis.gui import (
    QgsAttributeDialog,
    QgsAttributeEditorContext,
    QgsMapTool,
)
from qgis.PyQt.QtCore import QPoint, Qt
from qgis.PyQt.QtGui import QCursor
from qgis.PyQt.QtWidgets import QLabel
from qgis.utils import iface

from .geom_compo import GeomCompo
from .utils import log


class IDsBasket(QgsMapTool):
    def __init__(
        self,
        canvas,
        segments_layer,
        compositions_layer,
        id_column_name,
        segments_column_name,
    ):
        super().__init__(canvas)
        if canvas:
            self.canvas = canvas
        self.segments_layer = segments_layer
        self.compositions_layer = compositions_layer
        self.id_column_name = id_column_name
        self.segment_column_name = segments_column_name
        self.selected_ids = []
        self.removed_ids = []
        self.canvas = canvas

        self.setCursor(QCursor(Qt.PointingHandCursor))  # type: ignore
        self.label = QLabel(self.canvas)
        self.label.setText("")
        self.label.setStyleSheet(
            """
            background-color: rgba(0, 0, 0, 0);
            padding: 0;
            border-radius: 0;
            color: white;
        """
        )
        self.label.hide()

        project = QgsProject.instance()
        if not project:
            return
        self.crs_project = project.crs()
        self.crs_segments_layer = self.segments_layer.crs()

        self.transform = QgsCoordinateTransform(
            self.crs_project, self.crs_segments_layer, QgsProject.instance()
        )

        self.spatial_index = QgsSpatialIndex()
        for feature in self.segments_layer.getFeatures():
            self.spatial_index.addFeature(feature)

        self.connectivity_cache = {}

    def open_attribute_form(self):
        log("r")
        self.compositions_layer.startEditing()
        feature = QgsVectorLayerUtils.createFeature(self.compositions_layer)

        if self.selected_ids:
            if self.segment_column_name != -1:
                ids_text = ",".join(map(str, self.selected_ids))
                feature.setAttribute(self.segment_column_name, ids_text)

        dialog = QgsAttributeDialog(
            self.compositions_layer, feature, True, iface.mainWindow(), True
        )
        dialog.setMode(QgsAttributeEditorContext.AddFeatureMode)  # type: ignore

        if dialog.show() == 1:
            new_feature = dialog.feature()

            if new_feature:
                log("r")
                self.compositions_layer.addFeature(new_feature)
                self.compositions_layer.commitChanges()

        self.selected_ids.clear()
        self.segments_layer.removeSelection()
        self.update_label()

    def canvasReleaseEvent(self, e):
        if not e:
            return
        if e.button() == Qt.RightButton:  # type: ignore
            if self.selected_ids:
                self.open_attribute_form()
                return
            else:
                return

        if e.button() == Qt.LeftButton:  # type: ignore
            click_point = self.toMapCoordinates(e.pos())
            transformed_point = self.transform.transform(click_point)

            search_radius = 80
            search_rectangle = QgsRectangle(
                transformed_point.x() - search_radius,
                transformed_point.y() - search_radius,
                transformed_point.x() + search_radius,
                transformed_point.y() + search_radius,
            )

            request = QgsFeatureRequest()
            request.setFilterRect(search_rectangle)

            closest_feature = None
            min_distance = float("inf")

            for feature in self.segments_layer.getFeatures(request):
                distance = feature.geometry().distance(
                    QgsGeometry.fromPointXY(QgsPointXY(transformed_point))
                )
                if distance <= search_radius and distance < min_distance:
                    min_distance = distance
                    closest_feature = feature

            if closest_feature:
                feature_id = int(closest_feature[self.id_column_name])

                if not self.selected_ids:
                    self.selected_ids.append(feature_id)
                else:
                    # Chercher le chemin entre le dernier point sélectionné et le nouveau
                    last_id = self.selected_ids[-1]
                    if last_id != feature_id:
                        path = self.find_connected_segments(last_id, feature_id)
                        for segment_id in path:
                            if segment_id not in self.selected_ids:
                                self.selected_ids.append(segment_id)
                        if feature_id not in self.selected_ids:
                            self.selected_ids.append(feature_id)

                self.update_label()
                self.highlight_selected_segments()

    def highlight_selected_segments(self):
        """Met en surbrillance (sélection de qgis) les segments sélectionnés"""

        expr = f"\"{self.id_column_name}\" IN ({','.join(map(str, self.selected_ids))})"

        self.segments_layer.selectByExpression(expr)

    def keyPressEvent(self, e):
        if not e:
            return
        if e.key() == Qt.Key_Z:  # type: ignore
            self.remove_last_segment()
        elif e.key() == Qt.Key_E:  # type: ignore
            self.restore_last_removed_segment()

    def remove_last_segment(self):
        if self.selected_ids:
            last_id = self.selected_ids.pop()
            self.removed_ids.append(last_id)
            self.segments_layer.removeSelection()
            self.highlight_selected_segments()
            self.update_label()

    def restore_last_removed_segment(self):
        if self.removed_ids:
            last_removed_id = self.removed_ids.pop()
            self.selected_ids.append(last_removed_id)
            self.highlight_selected_segments()
            self.update_label()

    def find_connected_segments(self, start_id, end_id):
        start_id = int(start_id)
        end_id = int(end_id)

        if start_id == end_id:
            return [start_id]
        # Algorithme de Dijkstra
        distances = {start_id: 0}
        previous = {}
        unvisited = {start_id: 0}
        visited = set()

        while unvisited:
            current_id = min(unvisited, key=lambda k: unvisited[k])
            current_distance = unvisited[current_id]

            if current_id == end_id:
                break

            del unvisited[current_id]
            visited.add(current_id)

            for neighbor_id in self.get_connected_segments(current_id):
                if neighbor_id in visited:
                    continue
                neighbor_feature = next(
                    self.segments_layer.getFeatures(
                        QgsFeatureRequest().setFilterExpression(
                            f'"{self.id_column_name}" = {neighbor_id}'
                        )
                    )
                )
                segment_length = neighbor_feature.geometry().length()
                new_distance = current_distance + segment_length
                if (
                    neighbor_id not in distances
                    or new_distance < distances[neighbor_id]
                ):
                    distances[neighbor_id] = new_distance
                    unvisited[neighbor_id] = new_distance
                    previous[neighbor_id] = current_id

        if end_id not in previous and start_id != end_id:
            return []

        path = []
        current_id = end_id
        while current_id in previous:
            path.insert(0, current_id)
            current_id = previous[current_id]
        path.insert(0, start_id)

        return path

    def get_connected_segments(self, segment_id):
        if segment_id in self.connectivity_cache:
            return self.connectivity_cache[segment_id]

        connected = []

        request = QgsFeatureRequest().setFilterExpression(
            f'"{self.id_column_name}" = {segment_id}'
        )
        current_feature = next(self.segments_layer.getFeatures(request))
        current_geom = current_feature.geometry()

        bbox = current_geom.boundingBox()
        bbox.grow(0.0001)

        candidates = self.spatial_index.intersects(bbox)

        request = QgsFeatureRequest().setFilterFids(candidates)
        for feature in self.segments_layer.getFeatures(request):
            if feature[self.id_column_name] == segment_id:
                continue

            other_geom = feature.geometry()

            if current_geom.touches(other_geom):
                connected.append(int(feature[self.id_column_name]))

        self.connectivity_cache[segment_id] = connected
        return connected

    def update_label(self):
        if self.selected_ids:
            self.label.setText(", ".join(map(str, self.selected_ids)))
            self.label.setStyleSheet(
                """
                background-color: rgba(255, 255, 255, 0.9);
                padding: 5px;
                border-radius: 3px;
                color: black;
            """
            )
        else:
            self.label.setText("")
            self.label.setStyleSheet(
                """
                background-color: rgba(0, 0, 0, 0);
                padding: 0;
                border-radius: 0;
                color: white;
            """
            )

        self.label.adjustSize()

    def canvasMoveEvent(self, e):
        if not e:
            return
        mousePos = e.pos()

        # # TODO : ne marche pas
        # if not mousePos:
        #     self.label.hide()
        #     return

        labelPos = mousePos + QPoint(20, 0)
        if labelPos.x() + self.label.width() > self.canvas.width():  # type: ignore
            labelPos.setX(mousePos.x() - self.label.width() - 5)

        self.label.move(labelPos)
        self.label.show()

    def deactivate(self):
        self.label.hide()
        self.selected_ids = []
        self.segments_layer.removeSelection()
        super().deactivate()
