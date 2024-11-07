import time
from functools import wraps
from qgis.core import (
    QgsProject,
    QgsVectorLayer,
    QgsFeature,
    Qgis,
    QgsFeatureRequest,
    QgsWkbTypes,
    QgsSpatialIndex
)
from qgis.PyQt.QtCore import (
    QTranslator,
    QCoreApplication
)

def timer_decorator(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.time()
        result = func(*args, **kwargs)
        end = time.time()
        print(f"{func.__name__} a pris {(end - start)*1000:.2f} ms")
        return result
    return wrapper

def get_features_list(layer, request=None):
    features = []
    if request:
        iterator = layer.getFeatures(request)
    else:
        iterator = layer.getFeatures()

    feature = next(iterator, None)
    while feature:
        features.append(feature)
        feature = next(iterator, None)
    return features

def print_geometry_info(geometry, label):
    """Affiche les informations détaillées sur une géométrie"""
    if not geometry or geometry.isEmpty():
        print(f"{label}: Géométrie invalide ou vide")
        return

    points = geometry.asPolyline()
    print(f"""
    {label}:
    - Type: {geometry.wkbType()}
    - Longueur: {geometry.length():.2f}
    - Nombre de points: {len(points)}
    - Premier point: {points[0]}
    - Dernier point: {points[-1]}
    """)

def tr(message):
    return QCoreApplication.translate('NetworkManager', message)
