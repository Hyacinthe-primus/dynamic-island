# Dynamic Island pour Windows

Une île flottante **noire** en haut de l'écran, au style **Windows 11** (coins de 9-10 px,
couleur d'accentuation de Windows, icônes Fluent).

## Utilisation
- **Survol** : ouvre l'île. **Clic** : la garde ouverte. **Clic ailleurs / Échap** : la referme.
- **Ctrl+Alt+V** : presse-papiers avec recherche. **Ctrl+Alt+Espace** : lanceur d'applications.
- **Glissez des fichiers** sur l'île pour les garder en attente ; faites-les glisser de l'île vers une autre appli.
- **Molette** sur la pilule fermée : volume.
- La pilule fermée affiche selon le contexte : heure, minuteur en cours, réunion imminente,
  musique, build en cours. Points verts/orange = caméra / micro utilisés.
- **Permanente** : toujours affichée au-dessus de tout (même en plein écran), lancée avec Windows, et relancée
  automatiquement si elle plante (gardien `island_watchdog.pyw`).
- **Barre des tâches masquée en permanence**, même au survol. Le menu Démarrer reste accessible avec la touche
  Windows. Pour la retrouver : **clic droit sur l'île › décocher « Masquer la barre des tâches »**, ou *Quitter*
  (elle est rétablie comme avant).
- **Clic droit sur l'île** : menu (garder ouvert, démarrage auto, barre des tâches, synchro, quitter).

## Onglets
| Onglet | Contenu |
|---|---|
| **Accueil** | Heure, date, météo, média, prochains événements (bouton *Rejoindre*), anniversaires, tâches du jour, minuteurs actifs |
| **Agenda** | À venir · Semaine · Mois · Comptes. Ajout rapide en français (« Réunion demain 14h30 », « Anniversaire Léa 12/03 »), modification/suppression, rappels, compte à rebours, liens Teams/Zoom/Meet détectés |
| **Minuteurs** | Minuteurs multiples (préréglages ou « 12m thé »), Pomodoro + pauses, mode concentration (active *Ne pas déranger*), chronomètre avec tours, alarmes (« 7h30 Réveil semaine »), statistiques et historique |
| **Tâches** | Aujourd'hui · Toutes · Projets · Notes. « Envoyer devis demain 9h !haute #client » → échéance, rappel, priorité, projet. Notes rapides épinglables avec recherche |
| **Lanceur** | Recherche d'applications (menu Démarrer + Store), favoris, groupes lancés en un clic, applis récemment utilisées dans Windows. Saisie : « + GitHub = https://github.com », « + Notes = notepad.exe C:\notes.txt » (arguments), « + Projets = D:\Code », « > Get-Process » (PowerShell), « py: C:\script.py », « + groupe Travail : Code, Edge, Spotify » |
| **Fichiers** | Étagère (fichiers en attente : ouvrir, copier/déplacer vers…, presse-papiers, glisser vers une appli), téléchargements en cours (% et temps restant pour Chrome/Edge/Brave, taille et vitesse pour Firefox/Zen), récents, dossiers favoris + raccourcis sur le Bureau |
| **Téléphone** | QR code → page web sur le téléphone (même Wi-Fi, HTTPS local, lien secret) : fichiers PC ⇄ téléphone, texte et presse-papiers dans les deux sens, télécommande (musique, volume, diapos, ouvrir un lien), batterie du téléphone. Notifications et appels via « Lien avec Windows ». QR code du Wi-Fi |
| **Finances** | Portefeuille **Binance** en lecture seule (Spot + Financement + Earn, $ / FCFA / €, variation 24 h, historique), mode masqué |
| **Infos** | Widgets personnalisables (*Modifier*) : météo + prévisions + pluie, heure mondiale, statistiques perso, citation du jour, actualités RSS, bourse, photo favorite, calendrier |
| **Dev** | IDE et projet ouverts (VS Code, IntelliJ, PyCharm, WebStorm, Visual Studio…), branche et statut Git, commits, fichiers modifiés, GitHub (PR, issues, CI, déploiements, notifications), Jenkins, build local + erreurs, logs, serveurs/ports locaux, services, projets favoris, terminal |
| **Contrôles** | Wi-Fi, Bluetooth, avion, éclairage nocturne, Ne pas déranger, micro, caméra, sortie audio, verrouiller, veille, volume général et par appli, luminosité, Verr. Maj/Num |
| **Presse-papiers** | Historique textes/liens/images/fichiers, recherche, catégories, épingler, coller directement |

## Connexions (facultatives)
- **Google Agenda / Outlook / Teams** : Agenda › Comptes › coller l'adresse iCal secrète.
- **GitHub** : Dev › GitHub › coller un jeton personnel (notifications + dépôts privés).
  Sans jeton, les dépôts publics fonctionnent.
- **Jenkins** : Dev › Builds › « URL utilisateur jeton ».
- **Synchronisation cloud** : menu de l'icône › *Synchroniser via un dossier cloud…*
  (OneDrive, Google Drive, Dropbox) — synchronise tâches, notes, agenda local, alarmes,
  sessions et presse-papiers entre plusieurs PC.
- **Binance** : onglet Finances › clé API **en lecture seule** + clé secrète.
- **Téléphone** : onglet Téléphone › Activer › scanner le QR. Au premier accès, le navigateur avertit
  (certificat local) : « Paramètres avancés › Continuer ». Windows peut demander d'autoriser Python
  sur le réseau privé : acceptez.
- **Météo** : position estimée via l'adresse IP (ipwho.is) puis Open-Meteo ; changeable dans Infos › Modifier.

## Données
Tout est stocké localement dans `%APPDATA%\DynamicIsland` (ou dans le dossier de synchro).

## Installation
```bash
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
```
Lancer : double-clic sur `start.bat` (lance le gardien, qui lance l'île).
