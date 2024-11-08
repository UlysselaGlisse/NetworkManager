# NetworkManager/README.md

Dieses QGIS-Plugin zielt darauf ab, bei der Erstellung eines Netzwerks zu unterstützen. Das offensichtlichste Beispiel für ein Netzwerk sind Straßen: Die Departementstraße 42 ist sowohl eine einzelne Straße als auch aus Dutzenden von verschiedenen Abschnitten zusammengesetzt.

Dieses Plugin hilft bei der Umwandlung zwischen diesen beiden Identitäten. Segmente beziehen sich hier auf die Abschnitte, und eine Komposition entspricht der Departementstraße.

Alle geografischen Arbeiten werden an den Segmenten durchgeführt; in den Kompositionen werden nur Attribute und eine Liste, die die darin enthaltenen Segmente auflistet, ausgefüllt.

In der Praxis besteht die Hauptfunktion dieses Plugins darin, während der Teilung eines Segments zu helfen. Wenn das Segment Teil einer oder mehrerer Kompositionen ist, kann es mühsam sein, herauszufinden, in welchen und an welcher Stelle. Das Plugin kümmert sich darum für Sie. Wenn zwei Abschnitte zusammengeführt werden, wird das Plugin Ihnen ebenfalls helfen, indem es das Segment entfernt, das in der Fusion verschwunden ist.

https://github.com/user-attachments/assets/847a345d-a748-43bd-8e1c-c4cfd3f3e9d2

# Installation

Laden Sie dieses Repository herunter:

```bash
git clone https://github.com/UlysselaGlisse/NetworkManager.git
```

* Linux:

Verschieben Sie das Verzeichnis in den QGIS-Plugin-Ordner, der sich normalerweise befindet:

`~/.local/share/QGIS/QGIS3/profiles/default/python/plugins.`

* Windows:

`C:\Users\USER\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`

* Mac OS:

`Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins`

---

In QGIS gehen Sie zu Plugins > Plugins verwalten und installieren

Geben Sie NetworkManager ein - wenn es nicht angezeigt wird, starten Sie QGIS neu - und aktivieren Sie dann das Kontrollkästchen.

## Nutzung
### Voraussetzungen:
* Für den Input sind zwei Ebenen erforderlich, eine für Segmente und eine für Kompositionen.
* Die Ebenen können in jedem Format vorliegen (GeoPackage, PostgreSQL, shp, geojson, ...).
* Sie können jeden gewünschten Namen haben.
* Die einzige Anforderung ist, dass das Feld, das die Liste der Segmente enthält, vom Typ String sein muss, und die Segmentebene muss ein Feld mit dem Namen "id" haben - das, mit dem Sie Ihre Kompositionen erstellen.

### Anwendungsfälle:
* Klicken Sie auf das Symbol ![Symbol](icons/icon.png)
* Geben Sie die Namen der beiden Ebenen sowie das Feld aus der Kompositionsebene ein, das die Segmentliste enthält.

![Dialog_Network_Manager](https://github.com/user-attachments/assets/a4928324-27a8-4dc0-93c9-858c212f5fee)

* Starten

Sie können auch wählen, dieses Plugin dauerhaft laufen zu lassen, indem Sie das entsprechende Kontrollkästchen aktivieren.
