THis README is also available in [:gb: English](https://github.com/UlysselaGlisse/NetworkManager/blob/main/i18n/README-en.md) and [:de: German](https://github.com/UlysselaGlisse/NetworkManager/blob/main/i18n/README-de.md)



Ce plugin Qgis a pour objectif d'offir une assistance lors de la réalisation d'un réseau.
L'exemple le plus évident de réseau est celui des routes :
La départementale 42 est à la fois une seule route et est composée de dizaines de sections différentes.

Ce plugin aide à la conversion entre ces deux identités. Les segments sont ici les sections, et une composition correspond à la départementale.

Tout le travail géographique s'effectue sur les segments, on ne remplie dans les compositions que des attributs et une liste contenant les segments la composant.

En pratique, la première fonction de ce plugin est d'aider au moment de la division d'un segment.
Si le segment fait partie d'une ou plusieurs compositions, il est pénible d'aller chercher dans lesquelles et à quel endroit.
Le plugin s'occupe de cela à votre place. Si deux sections sont fusionnées, le plugin vous assistera de la même manière en supprimant le segment qui a disparu dans la fusion.

https://github.com/user-attachments/assets/847a345d-a748-43bd-8e1c-c4cfd3f3e9d2


# Installation

Télécharger ce répertoire :

```bash
git clone https://github.com/UlysselaGlisse/NetworkManager.git
```

* Linux :

Déplacer le répertoire dans le dossier des plugins de Qgis normalement :

`~.local/share/QGIS/QGIS3/profiles/default/python/plugins.`

* Windows :

`C:\Users\USER\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`

* Mac OS :

`Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins`

---


Dans Qgis, Extensions >  Installer/Gérer les extensions

Taper NetworkManager - s'il n'apparaît pas, redémarrer Qgis - > Cocher la checkbox.

# Utilisation
### Prérequis:
* Deux couches sont requises en entrée, une pour les segments et une autre pour les compositions.
* Les couches peuvent être de n'importe quel format (GeoPackage, Postgresql, shp, geojson, ...).
* Elles peuvent avoir le nom que vous souhaitez
* La seule chose nécessaire est que le champ contenant la liste de segments soit de type string et que la couche des segments ait un champ nommé "id" - celui avec lequel vous construisez vos compositions.

### Usages:
* Cliquer sur l'icone ![icône](icons/icon.png)
* Entrer le nom des deux couches puis du champ de la couche des compositions où se trouve la liste des segments.

![Dialogue_Network_Manager](https://github.com/user-attachments/assets/a4928324-27a8-4dc0-93c9-858c212f5fee)

* Démarrer

Vous pouvez aussi choisir de laisser tourner ce plugin en permanence en cochant la case correspondante.

# Essai
Si vous souhaitez simplement essayer ce plugin, vous trouverez dans le dossier etc/ un Géopackage d'exemple.
Ouvrez-le et essayer. 
