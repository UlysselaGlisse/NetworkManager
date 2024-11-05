from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import QTimer, QSettings
from qgis.core import QgsApplication, QgsProject
import os.path
from .main import show_dialog, start_script, stop_script

class NetworkManagerTool:
    def __init__(self, iface):
        self.iface = iface
        self.dialog = None
        self.actions = []
        self.menu = 'Network Manager Tool'
        self.toolbar = self.iface.addToolBar('Network Manager')
        self.toolbar.setObjectName('NetworkManagerToolbar')
        self.project_loaded = False
        QgsProject.instance().readProject.connect(self.on_project_load)

    def initGui(self):
        """Crée les actions et ajoute les boutons à la barre d'outils"""
        icon_path = os.path.join(os.path.dirname(__file__), 'icons', 'icon.png')
        show_action = QAction(
            QIcon(icon_path),
            'Ouvrir Network Manager',
            self.iface.mainWindow()
        )
        show_action.triggered.connect(self.show_dialog)
        self.toolbar.addAction(show_action)
        self.actions.append(show_action)

    def on_project_load(self):
        """Fonction appelée quand un projet est chargé"""
        self.project_loaded = True
        project = QgsProject.instance()
        # Vérifier si l'auto-démarrage est activé pour ce projet
        auto_start, _ = project.readBoolEntry("network_manager", "auto_start", False)
        if auto_start:
            QTimer.singleShot(1000, self.auto_start_script)

    def auto_start_script(self):
        project = QgsProject.instance()
        # Vérifier si l'auto-démarrage est activé pour ce projet
        auto_start, _ = project.readBoolEntry("network_manager", "auto_start", False)

        if auto_start and self.check_required_layers():
            start_script()

    def check_required_layers(self):
        settings = QSettings()
        segments_layer_id = settings.value("network_manager/segments_layer_id", "")
        compositions_layer_id = settings.value("network_manager/compositions_layer_id", "")

        project = QgsProject.instance()
        segments_layer = project.mapLayer(segments_layer_id)
        compositions_layer = project.mapLayer(compositions_layer_id)

        return segments_layer is not None and compositions_layer is not None

    def check_and_start(self):
        """Vérifie si les couches nécessaires sont présentes avant de démarrer"""
        if not self.project_loaded:
            return

        project = QgsProject.instance()
        if not project:
            return

        settings = QSettings()
        segments_layer = settings.value("network_manager/segments_layer", "segments")
        compositions_layer = settings.value("network_manager/compositions_layer", "compositions")

        segments_layers = project.mapLayersByName(segments_layer)
        compositions_layers = project.mapLayersByName(compositions_layer)

    def unload(self):
        """Supprime les éléments de l'interface"""
        for action in self.actions:
            self.iface.removeToolBarIcon(action)
            self.iface.removePluginMenu(self.menu, action)
        if self.dialog:
            self.dialog.close()
        del self.toolbar

    def show_dialog(self):
        """Affiche la fenêtre de dialogue"""
        if self.dialog is None:
            self.dialog = show_dialog()
        self.dialog.show()
        self.dialog.activateWindow()
