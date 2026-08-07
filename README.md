# 🧭 Olex2RTZ – Convertisseur de routes Olex vers RTZ 1.0

**Olex2RTZ** est une application web légère développée avec Flask, permettant de convertir des fichiers de routes `olexplot.gz` générés par le logiciel Olex en fichiers RTZ conformes à la norme RTZ 1.0, utilisée dans la navigation maritime.

---

## 🚀 Fonctionnalités principales

### Conversion Olex → RTZ/GPX
- **Téléversement** d'un fichier `olexplot.gz` ou `.rtz` via une interface web simple.  
- **Extraction** et **conversion** automatique des routes Olex vers le format RTZ 1.0 ou GPX.
- **Affichage** des routes sur une carte interactive. 
- **Téléchargement** du fichier `.rtz` ou `.gpx` généré.

### Conversion GPX Bathymétrique → XYZ/CSV (outil avancé)
- **Traitement** de fichiers GPX contenant des données bathymétriques (profondeur).
- **Correction automatique des marées** via l'API WorldTides.info.
- **Sélection de segments** avec visualisation sur carte.
- **Export** en format XYZ (lat lon sonde) ou CSV (time, lat, lon, depth_m, sonde_m).
- **Cache intelligent** des données de marée pour optimiser les appels API.

---

## 🛠️ Installation locale

### Prérequis

- Python 3.7 ou version ultérieure  
- pip  
- Git

### Étapes

1. **Cloner le dépôt**
   ```bash
   git clone https://github.com/Usinouv/olex2rtz.git
   cd olex2rtz
   ```

2. **Créer et activer un environnement virtuel**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # Sous Windows : venv\Scripts\activate
   ```

3. **Configurer les variables d'environnement**
   ```bash
   cp .env.example .env
   # Éditer .env et ajouter vos clés API si nécessaire
   ```

4. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

5. **Lancer l'application**
    ```bash
    python run.py
    ```

   L'application sera accessible à l'adresse [http://localhost:5000](http://localhost:5000).

---

## ☁️ Déploiement avec Docker Compose

Le projet inclut un fichier `docker-compose.yml` pour faciliter le déploiement de l'application via Docker Compose.

### 1. Cloner le dépôt

```bash
git clone https://github.com/Usinouv/olex2rtz.git
cd olex2rtz
```

### 2. Construire et lancer l'application

Lance la commande suivante pour **construire l'image** localement à partir du `Dockerfile` et **démarrer le service** :

```bash
docker-compose up -d --build
```

Cela va :
- construire l'image Docker à partir du code source,
- créer et démarrer le conteneur,
- exposer le service sur le port `5000` (accessible sur http://localhost:5000 ou depuis l'IP du serveur).

### 3. Arrêter et supprimer les conteneurs

```bash
docker-compose down
```

---

## 🔧 Configuration avancée : GPX Bathymétrie

La fonctionnalité de conversion GPX bathymétrique est accessible via `/tools/gpx2xyz` (page cachée, non listée dans le menu).

### Prérequis
- Une clé API WorldTides (obtenir sur https://www.worldtides.info/)
- Fichiers GPX contenant des données de profondeur (extension `<depth>`)

### Configuration
1. Ajouter la clé API dans le fichier `.env` :
   ```bash
   WORLDTIDES_API_KEY=votre_clé_api_worldtides
   ```

2. Ajuster la taille maximale d'upload si nécessaire (par défaut: `64` Mo) :
   ```bash
   MAX_CONTENT_LENGTH_MB=64
   ```

3. Le cache WorldTides est automatiquement géré dans `./cache/worldtides/`

### Utilisation
1. Accéder à `/tools/gpx2xyz`
2. Uploader un fichier GPX contenant des données bathymétriques
3. Sélectionner le segment à traiter
4. Télécharger le fichier XYZ avec correction de marée

### Format de sortie
- **XYZ** : `latitude longitude sonde` (une ligne par point, séparé par espaces)
- Sonde = profondeur - hauteur de marée (correction WorldTides)

Le fichier généré suit le format : `YYYY-MM-DD_HHhMM_segNN_WT_sonde.{xyz|csv}`

---

## 📁 Structure du projet

```
olex2rtz/
├── app/                      # Application Flask
│   ├── __init__.py           # Configuration et création de l'app
│   ├── routes.py             # Routes et vues
│   ├── converter_service.py  # Logique de conversion Olex→RTZ/GPX
│   ├── gpx_service.py        # Logique GPX bathymétrique + WorldTides
│   ├── exceptions.py         # Exceptions personnalisées
│   ├── utils.py              # Utilitaires généraux
│   ├── cleanup.py            # Nettoyage des sessions
│   └── templates/            # Templates HTML
│       ├── base.html
│       ├── index.html
│       ├── routes.html
│       ├── gpx2xyz_upload.html
│       └── gpx2xyz_segments.html
├── static/                   # Fichiers statiques (CSS, JS, images)
├── cache/                    # Cache WorldTides (ignoré par git)
│   └── worldtides/           # Fichiers JSON de cache
├── run.py                    # Point d'entrée de l'application
├── requirements.txt          # Dépendances Python
├── .env.example              # Exemple de configuration
├── Dockerfile                # Image Docker de l'application
├── docker-compose.yml        # Déploiement simplifié avec Docker Compose
├── README.md                 # Documentation du projet
└── LICENSE                   # Licence MIT
```

---

## 📄 Licence

Ce projet est sous licence [MIT](LICENSE).

---

## 🤝 Contribuer

Les contributions sont les bienvenues ! N'hésitez pas à proposer des améliorations via issues ou pull requests.
