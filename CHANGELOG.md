# Journal des versions · Changelog

Le format suit [Keep a Changelog](https://keepachangelog.com/fr/1.1.0/).

## 1.1.0

### Français

**Tous les ordinateurs Mares, pas seulement le Quad.** Vingt-deux modèles
répartis en trois familles de protocole :

- **IconHD** — Quad, Quad Air, Puck Pro, Puck 2, Matrix, Nemo Wide 2,
  Icon HD, Icon AIR : lecture directe de la mémoire flash ;
- **Smart** — Smart, Smart Air, Smart Apnea : même mémoire, mais le type de
  plongée et le nombre d'échantillons sont rangés à l'autre bout de l'en-tête,
  et la géométrie dépend du mode ;
- **Genius / Sirius** — Genius, Horizon, Sirius, Sirius L, **Quad Ci**,
  **Quad2**, Puck 4, Puck Air 2 : plus de lecture de mémoire du tout, un
  protocole par objets numérotés avec profils à enregistrements typés et CRC.

**Menu Paramètres** (`Ctrl+,`), six volets :

- **Interface** — langue, thème clair ou sombre, taille du texte, onglet
  d'ouverture, mémoire de la fenêtre ;
- **Ordinateur** — modèle forcé, port série, et surtout les délais : temps
  d'attente, nombre de tentatives, pause entre deux essais, pause à
  l'ouverture, taille des paquets, vitesse, lignes DTR/RTS. C'est ce qu'on
  règle quand un ordinateur reste muet ou se bloque en cours d'import ;
- **Bloc** — volume et pressions par défaut, appliqués aux plongées importées
  ensuite ;
- **Analyse** — facteur de gradient, vitesse de remontée maximale, seuils
  ppO2, bande et durée du palier, lissage des vitesses ;
- **Données** — emplacement de la base et du dossier d'export ;
- **Diagnostic** — versions, chemins et ports, à copier dans une demande
  d'aide.

**Ajouté**

- Interface, ligne de commande et messages d'erreur en **français et en
  anglais**, choisis automatiquement d'après la langue du système.
- **Intégration d'air** : sur les modèles qui la mesurent, la pression du bloc
  est lue depuis l'ordinateur et la fiche indique « mesuré » au lieu de
  « supposé ».
- **Trimix** et **recycleur semi-fermé** reconnus (famille Genius).
- **Mode portable** : un fichier `portable.txt` posé à côté de l'application
  range la base et les réglages au même endroit — pratique sur clé USB ou sur
  un poste où le dossier personnel est verrouillé.
- **Test de connexion** dans les paramètres : vérifie câble, pilote et modèle
  sans rien écrire en base.
- Aide **« Brancher mon ordinateur »** et fenêtre de diagnostic.
- Thème clair.
- Mode démonstration paramétrable : Quad, Puck Pro, Smart, Quad Air, Quad2 ou
  Sirius.
- Exécutables Windows, macOS (Apple Silicon et Intel) et Linux publiés à
  chaque version.
- Commandes `thermocline models` et `thermocline diagnostic`.

**Modifié**

- Le projet s'appelle **Thermocline** ; le paquet Python passe de `maresquad`
  à `thermocline`. Un carnet laissé dans `~/.maresquad` est repris
  automatiquement au premier démarrage.
- Les seuils d'analyse ne sont plus figés dans le code.
- Le protocole série lit ses délais dans les réglages.
- Messages d'erreur de connexion complétés par le conseil correspondant au
  système (groupe `dialout` sous Linux, pilote CP210x sous macOS,
  Gestionnaire de périphériques sous Windows).

### English

**Every Mares dive computer, not just the Quad.** Twenty-two models across
three protocol families: **IconHD** (flash memory read), **Smart** (same
memory, header laid out differently) and **Genius / Sirius** (object protocol,
which covers the **Quad Ci** and **Quad2**).

**Added**

- A **Settings** dialog (`Ctrl+,`) with six panes: interface, dive computer
  (model, port and all the timings you reach for when a computer answers
  poorly), tank defaults, analysis thresholds, data locations and diagnostics.
- **French and English** throughout — interface, command line and error
  messages — picked from the system language.
- **Air integration**: tank pressure read from the computer where it is
  measured, shown as "measured" rather than "assumed".
- **Trimix** and **semi-closed rebreather** modes (Genius family).
- **Portable mode** via a `portable.txt` file next to the application.
- **Connection test** in the settings, a **"Connecting my dive computer"**
  help page and a **diagnostics** window.
- Light theme, configurable demo model.
- Windows, macOS (Apple Silicon and Intel) and Linux executables built for
  every release.

**Changed**

- The project is now called **Thermocline**; the Python package moved from
  `maresquad` to `thermocline`. An existing logbook in `~/.maresquad` is
  picked up automatically on first start.
- Analysis thresholds and serial timings are settings, no longer constants.

## 1.0.0

Première version : import USB depuis un Mares Quad, base SQLite, profil,
analyses, oxygène et tissus, statistiques du carnet, plongées masquées,
exports CSV.

First release: USB import from a Mares Quad, SQLite database, profile,
analysis, oxygen and tissues, logbook statistics, hidden dives, CSV exports.
