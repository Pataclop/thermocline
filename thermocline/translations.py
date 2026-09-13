"""Catalogue de traduction: francais (langue source) vers anglais.

Les cles sont les chaines telles qu'elles apparaissent dans le code. Les
champs entre accolades doivent etre repris **a l'identique**, specificateur de
format compris: `{max_depth:.1f}` ne peut pas devenir `{maxDepth:.1f}` ni
`{max_depth}`.

`tests/test_translations.py` verifie qu'aucune chaine n'a ete oubliee et que
les champs correspondent des deux cotes: ajouter un texte a l'interface sans
le traduire fait echouer la suite de tests.
"""

from __future__ import annotations

EN: dict[str, str] = {
    # -- familles et modeles ------------------------------------------------
    "lecture directe de la memoire flash": "direct flash memory read",
    "memoire flash, entete organisee autrement": (
        "flash memory, header laid out differently"
    ),
    "protocole par objets": "object-based protocol",
    ", integration d'air": ", air integration",
    "lecture mémoire": "memory read",
    "famille Smart": "Smart family",
    # -- diagnostic ---------------------------------------------------------
    "Version": "Version",
    "Python": "Python",
    "Système": "System",
    "Exécutable gelé": "Frozen executable",
    "Mode portable": "Portable mode",
    "Langue": "Language",
    "Dossier de données": "Data folder",
    "Base de plongées": "Dive database",
    "Réglages": "Settings file",
    "oui": "yes",
    "non": "no",
    "Ports série": "Serial ports",
    # -- erreurs de protocole ----------------------------------------------
    "Modèle Mares non reconnu (nom lu : {name}). Vous pouvez forcer un modèle "
    "dans les paramètres si vous savez lequel c'est.": (
        "Unrecognised Mares model (name read: {name}). You can force a model in "
        "the settings if you know which one it is."
    ),
    "Le Mares {model} n'expose pas sa mémoire flash : ce modèle communique par "
    "objets, il n'y a rien à recopier.": (
        "The Mares {model} does not expose its flash memory: this model speaks "
        "the object protocol, so there is nothing to dump."
    ),
    "Modèles connus :": "Known models:",
    "Modèle forcé inconnu : {name}.": "Unknown forced model: {name}.",
    # -- import -------------------------------------------------------------
    "Connexion à l'ordinateur…": "Connecting to the dive computer…",
    "Enregistrement en base…": "Saving to the database…",
    "Connecté : {device}": "Connected: {device}",
    "Aucun port série détecté. Branchez le câble USB Mares, vérifiez que le "
    "pilote du convertisseur est installé, puis réessayez.": (
        "No serial port found. Plug in the Mares USB cable, check that the "
        "adapter driver is installed, then try again."
    ),
    "Lecture de la plongée {number}…": "Reading dive {number}…",
    # -- transport ----------------------------------------------------------
    "Sous Windows, vérifiez dans le Gestionnaire de périphériques que le "
    "convertisseur USB-série apparaît sans point d'exclamation, et qu'aucun "
    "autre logiciel (Mares Dive Organizer, Subsurface…) ne tient le port.": (
        "On Windows, check in Device Manager that the USB-to-serial adapter "
        "shows up without a warning icon, and that no other program (Mares Dive "
        "Organizer, Subsurface…) is holding the port."
    ),
    "Sous Linux, l'accès aux ports série demande d'appartenir au groupe "
    "« dialout » : sudo usermod -aG dialout $USER, puis rouvrez votre session.": (
        "On Linux, serial port access requires membership of the \"dialout\" "
        "group: sudo usermod -aG dialout $USER, then log out and back in."
    ),
    "Sous macOS, installez le pilote du convertisseur (CP210x ou CH340 selon le "
    "câble) et autorisez-le dans Réglages Système › Confidentialité et "
    "sécurité.": (
        "On macOS, install the adapter driver (CP210x or CH340 depending on the "
        "cable) and allow it in System Settings › Privacy & Security."
    ),
    "Le port série n'est pas ouvert.": "The serial port is not open.",
    "Écriture partielle ({written}/{total} octets).": (
        "Partial write ({written}/{total} bytes)."
    ),
    "Écriture sur {port} impossible : {error}": "Cannot write to {port}: {error}",
    "Délai dépassé : {got}/{size} octets reçus depuis {port}.": (
        "Timed out: {got}/{size} bytes received from {port}."
    ),
    "Lecture sur {port} interrompue : {error}": "Read from {port} interrupted: {error}",
    "Ouverture de {port} impossible : {error}": "Cannot open {port}: {error}",
    "L'ordinateur ne répond pas. Vérifiez que le clip USB est bien enfoncé sur "
    "les contacts et que l'ordinateur est réveillé (appuyez sur un bouton), "
    "puis relancez. Si cela se reproduit, augmentez le délai d'attente dans "
    "Paramètres › Ordinateur.": (
        "The dive computer is not responding. Check that the USB clip is firmly "
        "seated on the contacts and that the computer is awake (press a button), "
        "then try again. If it keeps happening, raise the timeout in "
        "Settings › Dive computer."
    ),
    # -- import CSV ---------------------------------------------------------
    "{count} plongée trouvée.": "{count} dive found.",
    "{count} plongées trouvées.": "{count} dives found.",
    "{count} ligne ignorée.": "{count} row skipped.",
    "{count} lignes ignorées.": "{count} rows skipped.",
    "Importer un carnet CSV": "Import a CSV logbook",
    "Tout cocher": "Select all",
    "Tout décocher": "Deselect all",
    "Importer la sélection": "Import selection",
    "    (déjà importée)": "    (already imported)",
    "Import CSV": "CSV import",
    "Aucune plongée exploitable dans ce fichier.": (
        "No usable dive in this file."
    ),
    # -- plongees masquees --------------------------------------------------
    "Plongées masquées": "Hidden dives",
    "Ces plongées ont été retirées du carnet et ne seront plus importées, même "
    "lors d'une relecture complète.\nLes restaurer les rend à nouveau "
    "importables : relancez ensuite « Tout relire » pour les récupérer.": (
        "These dives were removed from the logbook and will not be imported "
        "again, even by a full re-read.\nRestoring them makes them importable "
        "again: run \"Re-read everything\" afterwards to get them back."
    ),
    "Restaurer la sélection": "Restore selection",
    "Fermer": "Close",
    "Restaurer": "Restore",
    "Annuler": "Cancel",
    "Aucune plongée masquée.": "No hidden dives.",
    "Sélectionnez au moins une plongée dans la liste.": (
        "Select at least one dive from the list."
    ),
    "    (masquée le {short_date})": "    (hidden on {short_date})",
    "{len} plongée(s) à nouveau importable(s).\n\nLancez « Tout relire » pour "
    "les récupérer depuis l'ordinateur.": (
        "{len} dive(s) importable again.\n\nRun \"Re-read everything\" to fetch "
        "them from the dive computer."
    ),
    "Masquer cette plongée (ne plus l'importer)": (
        "Hide this dive (stop importing it)"
    ),
    "Masquer ces {len} plongées (ne plus les importer)": (
        "Hide these {len} dives (stop importing them)"
    ),
    "Gérer les plongées masquées…": "Manage hidden dives…",
    "Masquer la plongée": "Hide dive",
    "Masquer la plongée du {started_at:%d/%m/%Y à %H:%M} ({max_depth:.1f} m) ?"
    "\n\nElle disparaît du carnet et ne sera plus réimportée, même avec "
    "« Tout relire ». Pratique pour les plongées de l'ancien propriétaire d'un "
    "ordinateur d'occasion.\n\nElle reste dans la mémoire de l'ordinateur, et "
    "le bouton « Masquées » permet de revenir en arrière.": (
        "Hide the dive of {started_at:%d/%m/%Y at %H:%M} ({max_depth:.1f} m)?"
        "\n\nIt leaves the logbook and will not be imported again, even by "
        "\"Re-read everything\". Handy for the previous owner's dives on a "
        "second-hand computer.\n\nIt stays in the computer's memory, and the "
        "\"Hidden\" button lets you undo this."
    ),
    "Masquer ces {len} plongées ?\n\nElles disparaissent du carnet et ne seront "
    "plus réimportées, même avec « Tout relire ». Pratique pour les plongées de "
    "l'ancien propriétaire d'un ordinateur d'occasion.\n\nElles restent dans la "
    "mémoire de l'ordinateur, et le bouton « Masquées » permet de revenir en "
    "arrière.": (
        "Hide these {len} dives?\n\nThey leave the logbook and will not be "
        "imported again, even by \"Re-read everything\". Handy for the previous "
        "owner's dives on a second-hand computer.\n\nThey stay in the computer's "
        "memory, and the \"Hidden\" button lets you undo this."
    ),
    "Plongée masquée ; elle ne sera plus importée.": (
        "Dive hidden; it will not be imported again."
    ),
    "{len} plongées masquées ; elles ne seront plus importées.": (
        "{len} dives hidden; they will not be imported again."
    ),
    # -- fenetre principale -------------------------------------------------
    "Thermocline — carnet de plongée": "Thermocline — dive logbook",
    "&Carnet": "&Logbook",
    "Importer les plongées": "Import dives",
    "Tout relire": "Re-read everything",
    "Importer un CSV…": "Import a CSV…",
    "Exporter le carnet…": "Export logbook…",
    "Exporter le profil…": "Export profile…",
    "Quitter": "Quit",
    "&Outils": "&Tools",
    "Plongées masquées…": "Hidden dives…",
    "Rafraîchir les ports série": "Refresh serial ports",
    "Paramètres…": "Settings…",
    "&Aide": "&Help",
    "Brancher mon ordinateur…": "Connecting my dive computer…",
    "Diagnostic…": "Diagnostics…",
    "À propos de Thermocline": "About Thermocline",
    "Actions": "Actions",
    "Port  ": "Port  ",
    "Rafraîchir": "Refresh",
    "Relire la liste des ports série": "Re-read the list of serial ports",
    "Relit tout l'historique de l'ordinateur, sans s'arrêter à la dernière "
    "plongée connue": (
        "Re-reads the computer's whole history instead of stopping at the last "
        "known dive"
    ),
    "Mode démo": "Demo mode",
    "Importe des plongées simulées, sans ordinateur branché": (
        "Imports simulated dives, with no computer plugged in"
    ),
    "Ajouter des plongées depuis un carnet CSV (le format d'« Exporter le "
    "carnet », ou compatible) ; vous choisissez ensuite lesquelles importer": (
        "Add dives from a CSV logbook (the \"Export logbook\" format, or a "
        "compatible one); you then pick which ones to import"
    ),
    "Exporter le carnet": "Export logbook",
    "Une ligne par plongée, au format CSV": "One row per dive, as CSV",
    "Masquées": "Hidden",
    "Masquées ({hidden})": "Hidden ({hidden})",
    "Consulter les plongées masquées et les rendre à nouveau importables": (
        "Review hidden dives and make them importable again"
    ),
    "Exporter le profil": "Export profile",
    "Toutes les séries calculées de la plongée affichée, au format CSV": (
        "Every computed series of the displayed dive, as CSV"
    ),
    "Paramètres": "Settings",
    "Langue, modèle d'ordinateur, délais de connexion, bloc, seuils…": (
        "Language, computer model, connection timings, tank, thresholds…"
    ),
    "Filtrer : site, binôme, notes, date…": "Filter: site, buddy, notes, date…",
    "Prêt.": "Ready.",
    "Aucun port détecté": "No port found",
    "Aucun port": "No port",
    "Aucun port série n'est sélectionné. Branchez le câble USB Mares puis "
    "cliquez sur Rafraîchir, ou cochez le mode démo.": (
        "No serial port is selected. Plug in the Mares USB cable then click "
        "Refresh, or tick demo mode."
    ),
    "Import en échec.": "Import failed.",
    "Import impossible": "Import failed",
    "Import partiel": "Partial import",
    "Certains enregistrements n'ont pas pu être lus :": (
        "Some records could not be read:"
    ),
    "Notes enregistrées.": "Notes saved.",
    "Export": "Export",
    "Aucune plongée à exporter.": "No dive to export.",
    "Sélectionnez d'abord une plongée.": "Select a dive first.",
    "Carnet exporté vers {path}": "Logbook exported to {path}",
    "Profil exporté vers {path}": "Profile exported to {path}",
    "plongees-{today:%Y%m%d}.csv": "dives-{today:%Y%m%d}.csv",
    "profil-{datetime:%Y%m%d-%H%M}.csv": "profile-{datetime:%Y%m%d-%H%M}.csv",
    # -- onglets ------------------------------------------------------------
    "Profil": "Profile",
    "Analyse": "Analysis",
    "Oxygène et tissus": "Oxygen and tissues",
    "Détails": "Details",
    "Statistiques": "Statistics",
    "Carnet": "Logbook",
    "Aucune plongée sélectionnée": "No dive selected",
    # -- colonnes de la liste ----------------------------------------------
    "Date": "Date",
    "Durée": "Duration",
    "Max": "Max",
    "Temp.": "Temp.",
    "Gaz": "Gas",
    "Site": "Site",
    "Site : {site}": "Site: {site}",
    "Binôme : {buddy}": "Buddy: {buddy}",
    # -- cartes de la fiche -------------------------------------------------
    "Prof. max": "Max depth",
    "Prof. moy": "Avg depth",
    "Temp. min": "Min temp",
    "Remontée max": "Max ascent",
    "Palier 3-6 m": "Stop 3-6 m",
    "Mélange": "Gas mix",
    "ppO2 max": "Max ppO2",
    "CNS": "CNS",
    "OTU": "OTU",
    "Prof. équiv. air": "Equiv. air depth",
    "Conso.": "SAC",
    "Plongée n° {number}": "Dive no. {number}",
    "{long_datetime} · {label} · {water} · un point toutes les "
    "{sample_interval} s": (
        "{long_datetime} · {label} · {water} · one sample every "
        "{sample_interval} s"
    ),
    "eau douce": "fresh water",
    "eau de mer": "salt water",
    "atteinte à {pretty_duration}": "reached at {pretty_duration}",
    "fond {pretty_duration}": "bottom {pretty_duration}",
    "médiane {median_depth:.1f} m": "median {median_depth:.1f} m",
    "max {temp_max:.1f} °C": "max {temp_max:.1f} °C",
    "{ascent_rate_max:.1f} m/min": "{ascent_rate_max:.1f} m/min",
    "{duration} au-delà de {limit:.0f} m/min": "{duration} above {limit:.0f} m/min",
    "dans la limite": "within the limit",
    "{gas_switches} changement(s)": "{gas_switches} switch(es)",
    "{max_ppo2:.2f} bar": "{max_ppo2:.2f} bar",
    "{duration} au-delà de {limit:g} bar": "{duration} above {limit:g} bar",
    "{used:.0f} L consommés": "{used:.0f} L used",
    "{used:.0f} L, pressions mesurées": "{used:.0f} L, measured pressures",
    "supposé {volume:.0f} L, {start:.0f}→{end:.0f} bar": (
        "assumed {volume:.0f} L, {start:.0f}→{end:.0f} bar"
    ),
    "à saisir dans le Carnet": "enter it in the Logbook tab",
    "{sac:.1f} L/min": "{sac:.1f} L/min",
    # -- graphiques ---------------------------------------------------------
    "Vue d'ensemble du profil : déplacez ou redimensionnez la fenêtre claire "
    "pour zoomer sur une phase de la plongée": (
        "Overview of the profile: move or resize the light window to zoom on a "
        "phase of the dive"
    ),
    "Temps (min)": "Time (min)",
    "Profondeur (m)": "Depth (m)",
    "Vitesse (m/min)": "Rate (m/min)",
    "Température (°C)": "Temperature (°C)",
    "Durée (min)": "Duration (min)",
    "Profondeur max (m)": "Max depth (m)",
    "Pression (bar)": "Pressure (bar)",
    "ppO2 (bar)": "ppO2 (bar)",
    "ppO2": "ppO2",
    "CNS (%) · OTU": "CNS (%) · OTU",
    "CNS (%)": "CNS (%)",
    "Sursaturation (% M-value)": "Supersaturation (% of M-value)",
    "Plafond (m)": "Ceiling (m)",
    "Charge (% M-value)": "Loading (% of M-value)",
    "Demi-vie du compartiment (min)": "Compartment half-time (min)",
    "Vitesse verticale": "Vertical rate",
    "Pression du bloc": "Tank pressure",
    "Temps par tranche de 3 m": "Time per 3 m band",
    "Répartition des vitesses verticales": "Vertical rate distribution",
    "Facteur de gradient": "Gradient factor",
    "Pression partielle d'oxygène": "Oxygen partial pressure",
    "Charge CNS et OTU cumulées": "Cumulative CNS and OTU loading",
    "Compartiment directeur et plafond": "Leading compartment and ceiling",
    "Profondeur équivalente air": "Equivalent air depth",
    "Charge des 16 compartiments à la sortie": (
        "Loading of the 16 compartments on surfacing"
    ),
    "Profondeur, durée, vitesses": "Depth, duration, rates",
    "Gaz, oxygène, décompression": "Gas, oxygen, decompression",
    "Température en fonction de la profondeur": "Temperature against depth",
    "Ordinateur et enregistrement": "Dive computer and record",
    "Plongées par mois": "Dives per month",
    "Plongées par année": "Dives per year",
    "Jour de la semaine": "Day of the week",
    "Heure de mise à l'eau": "Entry time",
    "Tranches de profondeur": "Depth bands",
    "plongées": "dives",
    "Tranches de durée": "Duration bands",
    "Sites les plus plongés": "Most dived sites",
    "Profondeur maximale": "Maximum depth",
    "Profondeur moyenne": "Average depth",
    "Durée des plongées": "Dive duration",
    "Température minimale": "Minimum temperature",
    "Temps immergé cumulé": "Cumulative time underwater",
    "Nombre de plongées cumulé": "Cumulative dive count",
    "Plongées sur 12 mois glissants": "Dives over a rolling 12 months",
    "Consommation (SAC)": "Air consumption (SAC)",
    "L/min": "L/min",
    "Intervalles de surface (< 24 h)": "Surface intervals (< 24 h)",
    "Durée en fonction de la profondeur maximale": (
        "Duration against maximum depth"
    ),
    "Temps total par tranche de 3 m": "Total time per 3 m band",
    "Records et repères": "Records and landmarks",
    "Ajuster": "Fit",
    "Revenir à la vue complète. Un double-clic sur un graphique fait la même "
    "chose pour ce graphique seul.": (
        "Back to the full view. Double-clicking a chart does the same for that "
        "chart alone."
    ),
    "Zoom rectangle": "Box zoom",
    "Glisser pour encadrer une zone. Decoche: glisser deplace la vue.": (
        "Drag to frame an area. Unticked, dragging pans the view."
    ),
    "molette : zoom · glisser : déplacer · double-clic : ajuster · clic droit : "
    "export": (
        "wheel: zoom · drag: pan · double-click: fit · right-click: export"
    ),
    "Axes du temps lies": "Linked time axes",
    "Zoomer sur un graphique zoome tous les autres au meme instant": (
        "Zooming one chart zooms every other one to the same moment"
    ),
    "remontée": "ascent",
    "remontée 10 m/min": "ascent 10 m/min",
    "descente 18 m/min": "descent 18 m/min",
    "1,4 bar": "1.4 bar",
    "1,6 bar": "1.6 bar",
    "M-value": "M-value",
    "réserve 50 bar": "reserve 50 bar",
    "Pression mesurée": "Measured pressure",
    "Pression estimée (consommation constante)": (
        "Estimated pressure (constant consumption)"
    ),
    "profondeur réelle": "actual depth",
    "équivalente air": "equivalent air",
    "à la profondeur courante": "at the current depth",
    "si remontée immédiate": "if surfacing right now",
    "Aucune exposition cumulée : la ppO2 est restée sous 0,5 bar.": (
        "No cumulative exposure: ppO2 stayed below 0.5 bar."
    ),
    "Renseignez le bloc et les pressions dans l'onglet Carnet\npour estimer la "
    "courbe de consommation.": (
        "Enter the tank and pressures in the Logbook tab\nto estimate the "
        "consumption curve."
    ),
    "  ·  {pressure:.0f} bar": "  ·  {pressure:.0f} bar",
    # -- infobulles longues -------------------------------------------------
    "<b>Profil de la plongée</b><br>\n"
    '<span style="color:#38bdf8">■</span> profondeur (axe de gauche, inversé)<br>\n'
    '<span style="color:#fb923c">■</span> température (axe de droite)<br>\n'
    '<span style="color:#22c55e">■</span> bande verte : zone du palier de '
    "sécurité, 3 à 6 m<br>\n"
    '<span style="color:#f87171">▲</span> remontée plus rapide que 10 m/min<br>\n'
    "● point blanc : profondeur maximale<br>\n"
    '<span style="color:#f87171">┄</span> plafond théorique, quand le modèle en '
    "impose un<br>\n"
    "<i>Molette pour zoomer, double-clic pour tout réafficher.</i>": (
        "<b>Dive profile</b><br>\n"
        '<span style="color:#38bdf8">■</span> depth (left axis, inverted)<br>\n'
        '<span style="color:#fb923c">■</span> temperature (right axis)<br>\n'
        '<span style="color:#22c55e">■</span> green band: safety stop zone, '
        "3 to 6 m<br>\n"
        '<span style="color:#f87171">▲</span> ascent faster than 10 m/min<br>\n'
        "● white dot: maximum depth<br>\n"
        '<span style="color:#f87171">┄</span> theoretical ceiling, when the '
        "model imposes one<br>\n"
        "<i>Wheel to zoom, double-click to show everything again.</i>"
    ),
    "<b>Vitesse verticale</b>, lissée sur 30 secondes.<br>\n"
    "Au-dessus de zéro : remontée. En dessous : descente.<br>\n"
    "La limite de 10 m/min est celle que Mares recommande à la remontée ;\n"
    "18 m/min est un repère de descente confortable.": (
        "<b>Vertical rate</b>, smoothed over 30 seconds.<br>\n"
        "Above zero: ascent. Below: descent.<br>\n"
        "The 10 m/min limit is the one Mares recommends on ascent;\n"
        "18 m/min is a comfortable descent landmark."
    ),
    "<b>Pression du bloc</b><br>\n"
    "Sur les modèles à intégration d'air, la courbe est <b>mesurée</b> par\n"
    "l'ordinateur.<br>\n"
    "Ailleurs elle est <b>reconstituée</b> à partir du volume du bloc, des "
    "pressions\nsaisies dans l'onglet Carnet et de la profondeur instantanée, en "
    "supposant une\nconsommation régulière : c'est une estimation, pas une "
    "mesure.": (
        "<b>Tank pressure</b><br>\n"
        "On air-integrated models the curve is <b>measured</b> by the dive\n"
        "computer.<br>\n"
        "Elsewhere it is <b>reconstructed</b> from the tank volume, the "
        "pressures\nentered in the Logbook tab and the instantaneous depth, "
        "assuming steady\nbreathing: an estimate, not a measurement."
    ),
    "<b>Temps par tranche de 3 m</b><br>\n"
    "Durée cumulée passée dans chaque tranche de profondeur. Un profil carré\n"
    "concentre tout sur une ou deux barres ; un profil multiniveaux les étale.": (
        "<b>Time per 3 m band</b><br>\n"
        "Cumulative time spent in each depth band. A square profile piles "
        "everything\nonto one or two bars; a multilevel profile spreads them out."
    ),
    "<b>Répartition des vitesses verticales</b><br>\n"
    "Temps passé à chaque vitesse. Une plongée maîtrisée se concentre autour de\n"
    "zéro, avec une queue limitée au-delà de 10 m/min.": (
        "<b>Vertical rate distribution</b><br>\n"
        "Time spent at each rate. A controlled dive clusters around zero, with a\n"
        "short tail beyond 10 m/min."
    ),
    "<b>Pression partielle d'oxygène</b><br>\n"
    "ppO2 = fraction d'O2 du mélange × pression absolue.<br>\n"
    '<span style="color:#f87171">┄</span> <b>1,4 bar</b> : limite habituelle au '
    "fond en plongée loisir.<br>\n"
    '<span style="color:#dc2626">┄</span> <b>1,6 bar</b> : limite d\'exception, '
    "réservée à la décompression.<br>\n"
    "Au-delà, le risque de crise hyperoxique augmente nettement.": (
        "<b>Oxygen partial pressure</b><br>\n"
        "ppO2 = O2 fraction of the mix × absolute pressure.<br>\n"
        '<span style="color:#f87171">┄</span> <b>1.4 bar</b>: usual limit at '
        "depth in recreational diving.<br>\n"
        '<span style="color:#dc2626">┄</span> <b>1.6 bar</b>: exceptional limit, '
        "kept for decompression.<br>\n"
        "Beyond that, the risk of oxygen toxicity rises sharply."
    ),
    "<b>Exposition cumulée à l'oxygène</b> (limites NOAA)<br>\n"
    '<span style="color:#f87171">■</span> <b>CNS</b> : part consommée de la dose '
    "maximale de toxicité\nneurologique. 100 % correspond à la limite "
    "d'exposition unique ; la charge se\ncumule d'une plongée à l'autre et "
    "décroît en surface.<br>\n"
    '<span style="color:#fb923c">■</span> <b>OTU</b> : unités de toxicité '
    "pulmonaire. Repères usuels :\n300 par jour, 850 sur une semaine.<br>\n"
    "Rien ne s'accumule tant que la ppO2 reste sous 0,5 bar.": (
        "<b>Cumulative oxygen exposure</b> (NOAA limits)<br>\n"
        '<span style="color:#f87171">■</span> <b>CNS</b>: share used of the '
        "maximum central nervous system\ntoxicity dose. 100 % is the single "
        "exposure limit; the load carries over from\none dive to the next and "
        "decays at the surface.<br>\n"
        '<span style="color:#fb923c">■</span> <b>OTU</b>: pulmonary toxicity '
        "units. Usual landmarks:\n300 per day, 850 over a week.<br>\n"
        "Nothing accumulates while ppO2 stays below 0.5 bar."
    ),
    "<b>Saturation des tissus — Bühlmann ZH-L16C</b><br>\n"
    "16 compartiments théoriques, de 4 à 635 minutes de demi-vie.<br><br>\n"
    '<span style="color:#4ade80">■</span> <b>À la profondeur courante</b> : '
    "sursaturation du\ncompartiment le plus contraignant, là où vous êtes. Elle "
    "reste basse tant que\nvous descendez ou restez au fond, car la pression "
    "ambiante est élevée.<br>\n"
    '<span style="color:#38bdf8">┄</span> <b>Si remontée immédiate</b> : '
    "sursaturation que vous\nauriez en rejoignant la surface tout de suite. "
    "C'est elle qui indique si la\nremontée directe reste possible.<br>\n"
    '<span style="color:#f87171">━</span> <b>Plafond</b> (axe de droite) : '
    "profondeur minimale\ntolérée à cet instant. Zéro signifie remontée directe "
    "autorisée.<br><br>\n"
    "<b>100 % = M-value</b>, seuil théorique de tolérance du modèle. Le facteur "
    "de\ngradient abaisse ce seuil : 100 % = limites brutes, 70 % = 30 % de "
    "marge.": (
        "<b>Tissue saturation — Bühlmann ZH-L16C</b><br>\n"
        "16 theoretical compartments, from 4 to 635 minutes of half-time."
        "<br><br>\n"
        '<span style="color:#4ade80">■</span> <b>At the current depth</b>: '
        "supersaturation of the\nmost constraining compartment, where you "
        "actually are. It stays low while you\ndescend or sit on the bottom, "
        "because ambient pressure is high.<br>\n"
        '<span style="color:#38bdf8">┄</span> <b>If surfacing right now</b>: '
        "the supersaturation you\nwould have on reaching the surface "
        "immediately. This is the one that tells you\nwhether a direct ascent "
        "is still possible.<br>\n"
        '<span style="color:#f87171">━</span> <b>Ceiling</b> (right axis): the '
        "shallowest depth\ntolerated at that moment. Zero means a direct ascent "
        "is allowed.<br><br>\n"
        "<b>100 % = M-value</b>, the model's theoretical tolerance threshold. "
        "The gradient\nfactor lowers it: 100 % = raw limits, 70 % = 30 % margin."
    ),
    "<b>Charge des 16 compartiments à la sortie de l'eau</b><br>\n"
    "Pour chaque compartiment, sa sursaturation en surface, en % de sa "
    "M-value.<br>\n"
    "Les compartiments rapides (à gauche, 4 à 27 min) se chargent et se vident "
    "en\nquelques dizaines de minutes ; les lents (à droite) gardent l'azote "
    "plusieurs\nheures et pilotent l'intervalle avant l'avion.<br>\n"
    '<span style="color:#4ade80">■</span> sous 60 % &nbsp;\n'
    '<span style="color:#fb923c">■</span> 60 à 85 % &nbsp;\n'
    '<span style="color:#f87171">■</span> 85 % et plus': (
        "<b>Loading of the 16 compartments on surfacing</b><br>\n"
        "For each compartment, its supersaturation at the surface, as a % of "
        "its M-value.<br>\n"
        "Fast compartments (left, 4 to 27 min) fill and empty within tens of\n"
        "minutes; slow ones (right) hold nitrogen for hours and drive the "
        "interval\nbefore flying.<br>\n"
        '<span style="color:#4ade80">■</span> under 60 % &nbsp;\n'
        '<span style="color:#fb923c">■</span> 60 to 85 % &nbsp;\n'
        '<span style="color:#f87171">■</span> 85 % and above'
    ),
    "<b>Profondeur équivalente air</b><br>\n"
    "Profondeur à laquelle on respirerait la même pression partielle d'azote en"
    "\nrespirant de l'air. Avec un nitrox elle est inférieure à la profondeur "
    "réelle,\net c'est ce gain qui allonge la durée sans palier.": (
        "<b>Equivalent air depth</b><br>\n"
        "The depth at which you would breathe the same nitrogen partial "
        "pressure on\nair. On nitrox it is shallower than the actual depth, and "
        "that gain is what\nextends no-stop time."
    ),
    "<b>Température en fonction de la profondeur</b><br>\n"
    "Chaque point est un échantillon du profil. Une rupture de pente marque une"
    "\nthermocline ; un nuage dédoublé indique que l'eau s'est réchauffée entre "
    "la\ndescente et la remontée.": (
        "<b>Temperature against depth</b><br>\n"
        "Each dot is a profile sample. A break in the slope marks a "
        "thermocline; a\nsplit cloud means the water warmed up between the "
        "descent and the ascent."
    ),
    "Modèle Bühlmann ZH-L16C rejoué à titre indicatif sur un profil déjà "
    "réalisé. Ce n'est pas l'algorithme de l'ordinateur Mares, et cela ne doit "
    "jamais servir à planifier une plongée.": (
        "Bühlmann ZH-L16C model replayed for information on a dive already "
        "made. This is not the Mares computer's algorithm, and it must never be "
        "used to plan a dive."
    ),
    "Marge appliquée aux M-values : 100 % = limites Bühlmann brutes, une valeur "
    "plus basse est plus conservatrice": (
        "Margin applied to the M-values: 100 % = raw Bühlmann limits, a lower "
        "value is more conservative"
    ),
    # -- onglet Carnet ------------------------------------------------------
    "Mes notes": "My notes",
    " bar": " bar",
    "Binôme": "Buddy",
    "Note": "Rating",
    "Bloc": "Tank",
    "Pression départ": "Start pressure",
    "Pression fin": "End pressure",
    "Commentaire": "Comment",
    "Quand l'ordinateur ne mesure pas la pression du bloc, saisir ici le bloc "
    "et les pressions permet de calculer la consommation ramenée à la surface "
    "et d'estimer la courbe de pression. Les modèles à intégration d'air "
    "remplissent ces champs tout seuls.": (
        "When the dive computer does not measure tank pressure, entering the "
        "tank and pressures here yields surface air consumption and an "
        "estimated pressure curve. Air-integrated models fill these fields in "
        "by themselves."
    ),
    "Enregistrer": "Save",
    "Historique des imports": "Import history",
    "Aucun import": "No import yet",
    # -- tableau de bord ----------------------------------------------------
    "Plongées": "Dives",
    "Temps immergé": "Time underwater",
    "Record": "Record",
    "Prof. moyenne": "Avg depth",
    "Durée moyenne": "Average duration",
    "Eau la + froide": "Coldest water",
    "Prof. max moyenne": "Avg max depth",
    "Cumul descendu": "Total descended",
    "Jours d'affilée": "Days in a row",
    "Sur 12 mois": "Over 12 months",
    "Sites visités": "Sites visited",
    "Dernière sortie": "Last outing",
    "{count} plongée en base": "{count} dive in the database",
    "{count} plongées en base": "{count} dives in the database",
    "Base vide": "Empty database",
    " · {count} masquée": " · {count} hidden",
    " · {count} masquées": " · {count} hidden",
    "profondeurs max cumulées": "max depths added up",
    "jours consécutifs": "consecutive days",
    "12 mois glissants": "rolling 12 months",
    "aujourd'hui": "today",
    "il y a {count} jour": "{count} day ago",
    "il y a {count} jours": "{count} days ago",
    "depuis le {started_at:%d/%m/%Y}": "since {started_at:%d/%m/%Y}",
    "plus longue {duration_label}": "longest {duration_label}",
    "Plus profonde": "Deepest",
    "Plus longue": "Longest",
    "Eau la plus froide": "Coldest water",
    "Eau la plus chaude": "Warmest water",
    "Première plongée": "First dive",
    "Dernière plongée": "Last dive",
    "Profondeur maximale moyenne": "Average maximum depth",
    "Cumul des profondeurs max": "Maximum depths added up",
    "Temps immergé total": "Total time underwater",
    "Jours consécutifs (record)": "Consecutive days (record)",
    "Journée la plus chargée": "Busiest day",
    "{count} plongée le {date:%d/%m/%Y}": "{count} dive on {date:%d/%m/%Y}",
    "{count} plongées le {date:%d/%m/%Y}": "{count} dives on {date:%d/%m/%Y}",
    "Modes utilisés": "Modes used",
    "Mélanges utilisés": "Gas mixes used",
    "Plongées successives": "Repetitive dives",
    "{len} avec moins de 6 h d'intervalle": "{len} less than 6 h apart",
    " · plus court : {pretty_duration}": " · shortest: {pretty_duration}",
    "Par année": "Per year",
    "plongée n° {number}": "dive no. {number}",
    # -- onglet Details -----------------------------------------------------
    "Début": "Start",
    "Fin": "End",
    "Mode": "Mode",
    "Profondeur max (entête)": "Max depth (header)",
    "Profondeur max (profil)": "Max depth (profile)",
    "Profondeur moyenne (entête)": "Average depth (header)",
    "Profondeur moyenne (profil)": "Average depth (profile)",
    "Profondeur médiane": "Median depth",
    "Temps au fond (> 80 % du max)": "Bottom time (> 80 % of max)",
    "Temps pour atteindre le fond": "Time to reach the bottom",
    "Durée de la remontée": "Ascent duration",
    "Vitesse de descente max": "Max descent rate",
    "Vitesse de descente moyenne": "Average descent rate",
    "Vitesse de remontée max": "Max ascent rate",
    "Vitesse de remontée moyenne": "Average ascent rate",
    "Temps en remontée trop rapide": "Time ascending too fast",
    "Cumul remonté": "Total ascended",
    "Aller-retours verticaux (> 4 m)": "Vertical yo-yos (> 4 m)",
    "Intégrale profondeur-temps": "Depth-time integral",
    "Température": "Temperature",
    "Température au plus profond": "Temperature at the deepest point",
    "Thermocline": "Thermocline",
    "non marquée": "not marked",
    "vers {thermocline_depth:.1f} m": "around {thermocline_depth:.1f} m",
    "{temp_min:.1f} à {temp_max:.1f} °C (moyenne {temp_avg:.1f} °C)": (
        "{temp_min:.1f} to {temp_max:.1f} °C (average {temp_avg:.1f} °C)"
    ),
    "{descent_rate_max:.1f} m/min": "{descent_rate_max:.1f} m/min",
    "{descent_rate_avg:.1f} m/min": "{descent_rate_avg:.1f} m/min",
    "{ascent_rate_avg:.1f} m/min": "{ascent_rate_avg:.1f} m/min",
    "{depth_profile_area:.0f} m.min": "{depth_profile_area:.0f} m.min",
    "Ordinateur": "Dive computer",
    "Numéro de série": "Serial number",
    "Intervalle d'échantillonnage": "Sampling interval",
    "Échantillons enregistrés": "Samples recorded",
    "Échantillons utiles": "Samples used",
    "Unités de l'ordinateur": "Computer units",
    "métriques": "metric",
    "impériales": "imperial",
    "Réglages (brut)": "Settings (raw)",
    "Empreinte matérielle": "Hardware fingerprint",
    "Identifiant interne": "Internal identifier",
    "Taille de l'enregistrement": "Record size",
    "{len} octets": "{len} bytes",
    # -- gaz et decompression ----------------------------------------------
    "Mélange {index}": "Gas mix {index}",
    "{label} — MOD 1,4 : {mod_1_4:.1f} m · MOD 1,6 : {mod_1_6:.1f} m": (
        "{label} — MOD 1.4: {mod_1_4:.1f} m · MOD 1.6: {mod_1_6:.1f} m"
    ),
    "Changements de gaz": "Gas switches",
    "ppO2 minimale": "Minimum ppO2",
    "ppO2 maximale": "Maximum ppO2",
    "{min_ppo2:.2f} bar": "{min_ppo2:.2f} bar",
    "Temps au-delà de {limit:g} bar": "Time above {limit:g} bar",
    "Charge CNS": "CNS loading",
    "Profondeur équivalente air max": "Maximum equivalent air depth",
    "Pression atmosphérique": "Atmospheric pressure",
    "{atmospheric:.3f} bar": "{atmospheric:.3f} bar",
    "Eau": "Water",
    "douce": "fresh",
    "mer": "salt",
    " (valeur par défaut)": " (default value)",
    " (mesuré par l'ordinateur)": " (measured by the dive computer)",
    "Pressions": "Pressures",
    "{pressure_start:.0f} → {pressure_end:.0f} bar": (
        "{pressure_start:.0f} → {pressure_end:.0f} bar"
    ),
    "Gaz consommé": "Gas used",
    "— Modèle ZH-L16C —": "— ZH-L16C model —",
    "facteur de gradient {value} %": "gradient factor {value} %",
    "Sursaturation maximale": "Maximum supersaturation",
    "{max_loading:.1f} % de la M-value": "{max_loading:.1f} % of the M-value",
    "Compartiment directeur": "Leading compartment",
    "n° {index} ({halflife:g} min)": "no. {index} ({halflife:g} min)",
    "Plafond théorique max": "Maximum theoretical ceiling",
    "Temps avec plafond": "Time with a ceiling",
    "Désaturation estimée": "Estimated desaturation",
    "{pretty_duration} (retour à 2 % de l'équilibre)": (
        "{pretty_duration} (back within 2 % of equilibrium)"
    ),
    # -- aide et diagnostic -------------------------------------------------
    "Brancher mon ordinateur": "Connecting my dive computer",
    "<b>Brancher un ordinateur Mares</b><br><br>\n"
    "1. Clipsez le câble USB Mares sur les contacts au dos de l'ordinateur.<br>\n"
    "2. Réveillez l'ordinateur en appuyant sur un bouton, et mettez-le en mode\n"
    "   transfert de données si votre modèle le demande.<br>\n"
    "3. Choisissez le port dans la barre d'outils — un <b>*</b> signale un\n"
    "   convertisseur USB-série reconnu — puis cliquez sur\n"
    "   <b>Importer les plongées</b>.<br><br>\n"
    "<b>Rien ne se passe ?</b><br>\n"
    "• Installez le pilote du convertisseur (FTDI, CP210x, CH340 selon le "
    "câble).<br>\n"
    "• Fermez tout autre logiciel qui pourrait tenir le port.<br>\n"
    "• Les modèles Sirius, Puck 4 et Puck Air 2 ne parlent qu'en Bluetooth : "
    "ils ne\n  sont pas lisibles par câble.<br>\n"
    "• Augmentez le délai d'attente dans <b>Paramètres › Ordinateur</b>.<br>\n"
    "• <b>Aide › Diagnostic</b> résume ce que voit l'application.": (
        "<b>Connecting a Mares dive computer</b><br><br>\n"
        "1. Clip the Mares USB cable onto the contacts on the back of the "
        "computer.<br>\n"
        "2. Wake the computer by pressing a button, and put it into data "
        "transfer\n   mode if your model asks for it.<br>\n"
        "3. Pick the port in the toolbar — a <b>*</b> marks a recognised\n"
        "   USB-to-serial adapter — then click <b>Import dives</b>.<br><br>\n"
        "<b>Nothing happens?</b><br>\n"
        "• Install the adapter driver (FTDI, CP210x or CH340 depending on the "
        "cable).<br>\n"
        "• Close any other program that might be holding the port.<br>\n"
        "• The Sirius, Puck 4 and Puck Air 2 only speak Bluetooth: they cannot "
        "be\n  read over a cable.<br>\n"
        "• Raise the timeout in <b>Settings › Dive computer</b>.<br>\n"
        "• <b>Help › Diagnostics</b> sums up what the application can see."
    ),
    "Diagnostic": "Diagnostics",
    "Copiez ce texte pour toute demande d'aide.": (
        "Copy this text into any request for help."
    ),
    "Copier": "Copy",
    "<b>Thermocline {version}</b><br><br>\n"
    "Carnet de plongée local pour les ordinateurs Mares.<br>\n"
    "Aucun compte, aucun service en ligne : tout reste sur cette machine.<br><br>\n"
    "Le décodage des données dérive de <b>libdivecomputer</b> (LGPL 2.1) ;\n"
    "ce projet est distribué sous la même licence.<br><br>\n"
    "Les calculs de saturation sont <b>indicatifs</b> et ne doivent jamais "
    "servir\nà planifier une plongée.": (
        "<b>Thermocline {version}</b><br><br>\n"
        "A local dive logbook for Mares dive computers.<br>\n"
        "No account, no online service: everything stays on this machine."
        "<br><br>\n"
        "Data decoding derives from <b>libdivecomputer</b> (LGPL 2.1);\n"
        "this project is distributed under the same licence.<br><br>\n"
        "Saturation figures are <b>informational</b> and must never be used\n"
        "to plan a dive."
    ),
    # -- boite Parametres ---------------------------------------------------
    "Interface": "Interface",
    "Données": "Data",
    "Valeurs par défaut": "Factory settings",
    "Remet tous les réglages dans leur état d'origine": (
        "Puts every setting back the way it shipped"
    ),
    "Remettre tous les réglages dans leur état d'origine ?": (
        "Put every setting back the way it shipped?"
    ),
    "Comme le système": "Same as the system",
    "Sombre": "Dark",
    "Clair": "Light",
    "Thème": "Theme",
    "Taille du texte": "Text size",
    "Onglet à l'ouverture": "Tab on startup",
    "Rouvrir la fenêtre à sa taille et à sa place": (
        "Reopen the window at its size and position"
    ),
    "Demander confirmation avant de masquer une plongée": (
        "Ask for confirmation before hiding a dive"
    ),
    "La langue, le thème et la taille du texte s'appliquent au prochain "
    "démarrage.": (
        "Language, theme and text size take effect on the next start."
    ),
    "Enregistré. La langue, le thème et la base de plongées s'appliqueront au "
    "prochain démarrage.": (
        "Saved. Language, theme and dive database will take effect on the next "
        "start."
    ),
    "Paramètres enregistrés.": "Settings saved.",
    "Enregistrement impossible : {error}": "Cannot save: {error}",
    "Connexion": "Connection",
    "Détection automatique (recommandé)": "Automatic detection (recommended)",
    "Détection automatique": "Automatic detection",
    "À n'utiliser que si votre ordinateur n'est pas reconnu : forcer le mauvais "
    "modèle produit des plongées illisibles.": (
        "Only use this if your computer is not recognised: forcing the wrong "
        "model produces unreadable dives."
    ),
    "Modèle": "Model",
    "Port série": "Serial port",
    "Retenir le dernier port utilisé": "Remember the last port used",
    "Quand l'ordinateur répond mal": "When the computer responds poorly",
    "Temps d'attente d'une réponse avant d'abandonner la commande": (
        "How long to wait for an answer before giving up on the command"
    ),
    "Délai d'attente": "Timeout",
    "Nombre de reprises après une trame perdue ou corrompue": (
        "How many retries after a lost or corrupted frame"
    ),
    "Tentatives supplémentaires": "Extra retries",
    "Pause entre deux tentatives": "Pause between retries",
    "Pause après l'ouverture du port, avant la première commande": (
        "Pause after opening the port, before the first command"
    ),
    "Pause à l'ouverture": "Pause on opening",
    "0 = taille conseillée pour le modèle détecté. La réduire aide sur les "
    "câbles capricieux et les concentrateurs USB.": (
        "0 = the size recommended for the detected model. Lowering it helps "
        "with flaky cables and USB hubs."
    ),
    "Taille des paquets": "Packet size",
    "Vitesse": "Baud rate",
    "Lignes de contrôle": "Control lines",
    "Les ordinateurs Mares attendent DTR et RTS relâchés. Ne les activez que si "
    "le vôtre reste muet autrement.": (
        "Mares computers expect DTR and RTS to stay low. Only turn them on if "
        "yours stays silent otherwise."
    ),
    "Mode démonstration": "Demo mode",
    "Modèle imité par le mode démo, pour voir le carnet sans matériel": (
        "Model imitated by demo mode, to see the logbook without hardware"
    ),
    "Modèle simulé": "Simulated model",
    "Tester la connexion": "Test the connection",
    "Connexion en cours…": "Connecting…",
    "Diagnostic copié.": "Diagnostics copied.",
    "Volume du bloc": "Tank volume",
    "Pression de départ": "Start pressure",
    "Pression de fin": "End pressure",
    "Utiliser les pressions mesurées par l'ordinateur quand il y en a": (
        "Use the pressures measured by the dive computer when there are any"
    ),
    "Ces valeurs s'appliquent aux plongées importées ensuite, pour afficher une "
    "consommation dès le premier import. Une plongée déjà en base garde ce "
    "qu'elle a ; vous pouvez toujours saisir les vraies valeurs dans l'onglet "
    "Carnet.": (
        "These values apply to dives imported afterwards, so that consumption "
        "shows up from the very first import. A dive already in the database "
        "keeps what it has; you can always enter the real values in the Logbook "
        "tab."
    ),
    "Marge appliquée aux M-values au chargement d'une plongée": (
        "Margin applied to the M-values when a dive is loaded"
    ),
    "Vitesse de remontée maximale": "Maximum ascent rate",
    "ppO2 d'avertissement": "Warning ppO2",
    "ppO2 critique": "Critical ppO2",
    "Bande du palier de sécurité": "Safety stop band",
    "Palier considéré comme tenu": "Stop counted as held",
    "Plus la fenêtre est large, plus la courbe de vitesse est lisse": (
        "The wider the window, the smoother the rate curve"
    ),
    "Lissage des vitesses": "Rate smoothing",
    "Ces seuils ne servent qu'à l'affichage et aux alertes du carnet. Ils ne "
    "modifient ni les données de l'ordinateur, ni sa décompression.": (
        "These thresholds only drive the logbook's display and warnings. They "
        "change neither the computer's data nor its decompression."
    ),
    "La bande du palier commence plus profond qu'elle ne finit.": (
        "The stop band starts deeper than it ends."
    ),
    "La ppO2 d'avertissement doit rester sous la ppO2 critique.": (
        "The warning ppO2 must stay below the critical ppO2."
    ),
    "Dossier d'export": "Export folder",
    "Ouvrir le dossier de données": "Open the data folder",
    "Actif : les données sont rangées à côté de l'application.": (
        "On: data is kept next to the application."
    ),
    "Inactif. Pour emporter le carnet sur une clé USB, placez un fichier vide "
    "nommé « portable.txt » à côté de l'application.": (
        "Off. To carry the logbook on a USB stick, put an empty file named "
        "\"portable.txt\" next to the application."
    ),
    "Changer de base de plongées prend effet au prochain démarrage.": (
        "Changing the dive database takes effect on the next start."
    ),
    "Actualiser": "Refresh",
    "Si quelque chose ne fonctionne pas sur cet ordinateur, copiez ce texte et "
    "joignez-le à votre demande d'aide.": (
        "If something does not work on this machine, copy this text and attach "
        "it to your request for help."
    ),
    "nombre": "count",
    "heures": "hours",
    "aucun": "none",
    # -- bilan d'import -----------------------------------------------------
    "Aucune nouvelle plongée : la base est à jour.": (
        "No new dive: the database is up to date."
    ),
    "Rien à importer.": "Nothing to import.",
    "{count} plongée importée": "{count} dive imported",
    "{count} plongées importées": "{count} dives imported",
    "{count} déjà connue": "{count} already known",
    "{count} déjà connues": "{count} already known",
    "{count} masquée ignorée": "{count} hidden one skipped",
    "{count} masquées ignorées": "{count} hidden ones skipped",
    "{count} en erreur": "{count} in error",
    # -- import CSV (analyse du fichier) ------------------------------------
    "Le fichier est vide.": "The file is empty.",
    "Aucune colonne reconnue dans l'en-tête. Colonnes attendues : date, "
    "prof_max_m, duree_s, site… (voir « Exporter le carnet »).": (
        "No recognised column in the header. Expected columns: date, "
        "prof_max_m, duree_s, site… (see \"Export logbook\")."
    ),
    "Ligne {line_no} : {exc}": "Row {line_no}: {exc}",
    "date illisible ou manquante": "unreadable or missing date",
    "profondeur maximale illisible ou manquante": (
        "unreadable or missing maximum depth"
    ),
    # -- ligne de commande: aide -------------------------------------------
    "Thermocline — carnet de plongée pour les ordinateurs Mares (familles "
    "IconHD, Smart et Genius/Sirius).": (
        "Thermocline — dive logbook for Mares dive computers (IconHD, Smart and "
        "Genius/Sirius families)."
    ),
    "chemin de la base SQLite (défaut : {path})": (
        "path to the SQLite database (default: {path})"
    ),
    "journal détaillé": "verbose logging",
    "ouvre l'interface graphique (défaut)": "open the graphical interface (default)",
    "liste les ports série disponibles": "list the available serial ports",
    "liste les modèles Mares gérés": "list the supported Mares models",
    "versions, chemins et ports, à joindre à une demande d'aide": (
        "versions, paths and ports, to attach to a request for help"
    ),
    "importe les plongées en base": "import dives into the database",
    "port série (défaut : détection automatique)": (
        "serial port (default: automatic detection)"
    ),
    "utilise l'ordinateur simulé": "use the simulated dive computer",
    "modèle imité en mode démonstration": "model imitated in demo mode",
    "nombre maximum de plongées à lire": "maximum number of dives to read",
    "relit tout l'historique sans s'arrêter à la dernière plongée connue": (
        "re-read the whole history instead of stopping at the last known dive"
    ),
    "affiche les plongées en base": "show the dives in the database",
    "de la plus ancienne à la plus récente": "oldest first",
    "statistiques d'une plongée ou du carnet": (
        "statistics for one dive or for the whole logbook"
    ),
    "numéro de plongée": "dive number",
    "liste les plongées masquées, ou en restaure une": (
        "list hidden dives, or restore one"
    ),
    "EMPREINTE": "FINGERPRINT",
    "NUMERO": "NUMBER",
    "rend une plongée masquée à nouveau importable": (
        "make a hidden dive importable again"
    ),
    "masque la plongée portant ce numéro : elle quitte le carnet et ne sera "
    "plus importée": (
        "hide the dive with this number: it leaves the logbook and will not be "
        "imported again"
    ),
    "copie la mémoire flash dans un fichier": "copy the flash memory to a file",
    "fichier de destination": "destination file",
    # -- ligne de commande: sorties ----------------------------------------
    "Aucun port série détecté.": "No serial port found.",
    "Ports série (* = convertisseur USB reconnu) :": (
        "Serial ports (* = recognised USB adapter):"
    ),
    "    Mares {name}{air}": "    Mares {name}{air}",
    "Échec : {exc}": "Failed: {exc}",
    "Base vide.": "Empty database.",
    "Base vide. Lancez `thermocline import` (ou `--demo`).": (
        "Empty database. Run `thermocline import` (or `--demo`)."
    ),
    "{number:>4} {date:<17} {duration:>7} {max:>7} {avg:>7} {temp:>6}  "
    "{gas:<14} {site}": (
        "{number:>4} {date:<17} {duration:>7} {max:>7} {avg:>7} {temp:>6}  "
        "{gas:<14} {site}"
    ),
    "N°": "No.",
    "Moy": "Avg",
    "Temp": "Temp",
    "Plongées              {total_dives}": "Dives                 {total_dives}",
    "Temps immergé         {total_duration_label}": (
        "Time underwater       {total_duration_label}"
    ),
    "Profondeur max        {max_depth:.1f} m": (
        "Maximum depth         {max_depth:.1f} m"
    ),
    "Profondeur moyenne    {avg_depth:.1f} m": (
        "Average depth         {avg_depth:.1f} m"
    ),
    "Durée moyenne         {pretty_duration}": (
        "Average duration      {pretty_duration}"
    ),
    "Record de profondeur  {max_depth:.1f} m ({where})": (
        "Deepest dive          {max_depth:.1f} m ({where})"
    ),
    "Plus longue           {duration_label} ({where})": (
        "Longest dive          {duration_label} ({where})"
    ),
    "Par année            ": "Per year             ",
    "Modes                ": "Modes                ",
    "Plongée n° {number} — {datetime:%d/%m/%Y %H:%M} — {label}": (
        "Dive no. {number} — {datetime:%d/%m/%Y %H:%M} — {label}"
    ),
    "  Site                  {site}": "  Site                  {site}",
    "  Durée                 {pretty_duration}": (
        "  Duration              {pretty_duration}"
    ),
    "  Profondeur max        {max_depth:.1f} m (atteinte à {pretty_duration})": (
        "  Maximum depth         {max_depth:.1f} m (reached at {pretty_duration})"
    ),
    "  Profondeur moyenne    {avg_depth:.1f} m": (
        "  Average depth         {avg_depth:.1f} m"
    ),
    "  Temps au fond (>80%)  {pretty_duration}": (
        "  Bottom time (>80%)    {pretty_duration}"
    ),
    "  Température           {temp_min:.1f} à {temp_max:.1f} °C": (
        "  Temperature           {temp_min:.1f} to {temp_max:.1f} °C"
    ),
    "  Descente max          {descent_rate_max:.1f} m/min": (
        "  Max descent rate      {descent_rate_max:.1f} m/min"
    ),
    "  Remontée max          {ascent_rate_max:.1f} m/min ({pretty_duration} "
    "au-delà de la limite)": (
        "  Max ascent rate       {ascent_rate_max:.1f} m/min ({pretty_duration} "
        "above the limit)"
    ),
    "  Palier 3-6 m          {pretty_duration}": (
        "  Stop 3-6 m            {pretty_duration}"
    ),
    "  Mélanges              {gas_label}": "  Gas mixes             {gas_label}",
    "  ppO2 max              {max_ppo2:.2f} bar": (
        "  Max ppO2              {max_ppo2:.2f} bar"
    ),
    "  CNS / OTU             {cns:.1f} % / {otu:.0f}": (
        "  CNS / OTU             {cns:.1f} % / {otu:.0f}"
    ),
    "  Prof. équivalente air {ead_max:.1f} m": (
        "  Equivalent air depth  {ead_max:.1f} m"
    ),
    "  Consommation          {sac:.1f} L/min ({gas_used:.0f} L)": (
        "  Consumption           {sac:.1f} L/min ({gas_used:.0f} L)"
    ),
    "  Échantillons          {len} toutes les {sample_interval} s": (
        "  Samples               {len} every {sample_interval} s"
    ),
    "Aucune plongée n° {number}.": "No dive numbered {number}.",
    "Aucune plongée n° {hide}.": "No dive numbered {hide}.",
    "Masquée : {label}": "Hidden: {label}",
    "Elle ne sera plus importée, même avec --full.": (
        "It will not be imported again, even with --full."
    ),
    "Aucune plongée masquée d'empreinte {restore}.": (
        "No hidden dive with fingerprint {restore}."
    ),
    "Restaurée : {label}": "Restored: {label}",
    "Relancez `thermocline import --full` pour la récupérer.": (
        "Run `thermocline import --full` to fetch it back."
    ),
    "{len} plongée(s) masquée(s) :": "{len} hidden dive(s):",
    "\nPour en restaurer une : thermocline hidden --restore <empreinte>": (
        "\nTo restore one: thermocline hidden --restore <fingerprint>"
    ),
    "Connecté : {label}": "Connected: {label}",
    "Lecture de {total} octets, cela prend plusieurs minutes…": (
        "Reading {total} bytes, this takes several minutes…"
    ),
    "{len} octets ecrits dans {output}": "{len} bytes written to {output}",
    # -- petits composants --------------------------------------------------
    "port série": "serial port",
    "Champ": "Field",
    "Valeur": "Value",
    # -- modes de plongee ---------------------------------------------------
    "Air": "Air",
    "Profondimètre": "Gauge",
    "Nitrox": "Nitrox",
    "Apnée": "Freediving",
    "Trimix": "Trimix",
    "Recycleur semi-fermé": "Semi-closed rebreather",
}

#: Tous les catalogues disponibles, par code de langue.
CATALOGS: dict[str, dict[str, str]] = {"en": EN}
