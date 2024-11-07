Ce plugin Qgis a pour objectif d'offir une assistance lors de la réalisation d'un réseau, c'est-à-dire d'une composition de segments. 

Il permet de mettre à jour automatiquement les compositions lorsque des segments sont divisés ou fusionnés. 


https://github.com/user-attachments/assets/641ae2c7-7495-4797-b587-7feb17073933


# Installation 

Télécharger ce répertoire : 

```bash
git clone https://github.com/UlysselaGlisse/NetworkManager.git
```

### Linux : 

Déplacer le répertoire dans le dossier des plugins de Qgis normalement :

`~.local/share/QGIS/QGIS3/profiles/default/python/plugins.`

### Windows : 

`C:\Users\USER\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`

### Mac OS :

`Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins`

---


Dans Qgis, Extensions >  Installer/Gérer les extensions

Taper NetworkManager - s'il n'apparaît pas, redémarrer Qgis - > Installer l'extension.

## Utilisation

Deux couches sont requises en entrée, une pour les segments et une autre pour les compositions. Les couches peuvent être de n'importe quel format - pourvu que Qgis les accepte ! Elles peuvent avoir le nom que vous souhaitez, la seule chose nécessaire est qu'il existe dans la couche des compositions un champ nommé "segments" et que la couche des segments ait un champ nommé "id" - celui avec lequel vous construisez vos compositions.
