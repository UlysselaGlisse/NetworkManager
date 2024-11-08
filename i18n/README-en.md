# NetworkManager/README.md

This QGIS plugin aims to assist in the creation of a network. The most obvious example of a network is that of roads: departmental road 42 is both a single road and is composed of dozens of different sections.

This plugin helps in the conversion between these two identities. Segments here refer to the sections, and a composition corresponds to the departmental road.

All geographical work is carried out on the segments; attributes and a list containing the segments composing it are filled in only in the compositions.

In practice, the main function of this plugin is to assist during the division of a segment. If the segment is part of one or more compositions, it can be cumbersome to find out which ones and at what point. The plugin takes care of this for you. If two sections are merged, the plugin will assist in the same way by removing the segment that has disappeared in the merge.

https://github.com/user-attachments/assets/847a345d-a748-43bd-8e1c-c4cfd3f3e9d2

# Installation

Download this repository:

```bash
git clone https://github.com/UlysselaGlisse/NetworkManager.git
```

* Linux:

Move the directory to the QGIS plugins folder, usually located at:

`~/.local/share/QGIS/QGIS3/profiles/default/python/plugins.`

* Windows:

`C:\Users\USER\AppData\Roaming\QGIS\QGIS3\profiles\default\python\plugins`

* Mac OS:

`Library/Application Support/QGIS/QGIS3/profiles/default/python/plugins`

---

In QGIS, go to Plugins > Manage and Install Plugins

Type NetworkManager - if it does not appear, restart QGIS - then check the checkbox.

## Usage
### Prerequisites:
* Two input layers are required, one for segments and the other for compositions.
* The layers can be in any format (GeoPackage, PostgreSQL, shp, geojson, ...).
* They can have any name you want.
* The only requirement is that the field containing the list of segments must be of type string, and the segment layer must have a field named "id" - the one with which you build your compositions.

### Use Cases:
* Click on the icon ![icon](icons/icon.png)
* Enter the names of the two layers, then the field from the composition layer that contains the list of segments.

![Dialogue_Network_Manager](https://github.com/user-attachments/assets/a4928324-27a8-4dc0-93c9-858c212f5fee)

* Start

You can also choose to keep this plugin running continuously by checking the corresponding box.
