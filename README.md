# 📍 OlexPlot.gz ➔ RTZ Converter

Ce projet est une application web simple utilisant **Flask** pour convertir des fichiers `olexplot.gz` en fichiers **RTZ** conformes à la norme RTZ 1.0.

---

## 🔥 Fonctionnalités

- Upload d'un fichier `olexplot.gz`
- Décompression et lecture du contenu
- Extraction **seulement** des routes contenant `Plottsett 8`
- Choix de la route à convertir s'il y en a plusieurs
- Conversion des waypoints (min latitude/longitude ➔ degrés décimaux)
- Génération d'un fichier **RTZ** propre
- Téléchargement immédiat du fichier `.rtz`

---

## 🚀 Installation

### 1. Clone du projet

```bash
git clone git@github.com:Usinouv/olex2rtz.git
cd olex2rtz
```

### 2. Création et activation d'un environnement virtuel

```bash
python3 -m venv venv
source venv/bin/activate   # (Linux/Mac)
venv\Scripts\activate      # (Windows)
```

### 3. Installation des dépendances

```bash
pip install -r requirements.txt
```

---

## 📄 Fichier `requirements.txt`

Contenu :

```
Flask
```

---

## ⚙️ Utilisation

### 1. Lancer l'application Flask

```bash
python app.py
```

### 2. Accéder à l'interface web

Ouvre ton navigateur à l'adresse :

```
http://127.0.0.1:5000/
```

### 3. Utilisation

- Uploade ton fichier `.olexplot.gz`
- Sélectionne la route à convertir
- Télécharge ton fichier `.rtz`

---

## 🐳 Utilisation avec Docker

### 1. Construire l'image Docker

Assurez-vous d'avoir Docker installé sur votre machine. Ensuite, exécutez la commande suivante pour construire l'image Docker :

```bash
docker build -t olex2rtz .
```

### 2. Lancer le conteneur

Pour exécuter l'application dans un conteneur Docker, utilisez la commande suivante :

```bash
docker run -p 5000:5000 olex2rtz
```

L'application sera accessible à l'adresse [http://localhost:5000](http://localhost:5000).

### 3. Utilisation avec `docker-compose`

Si vous préférez utiliser `docker-compose`, exécutez simplement :

```bash
docker-compose up --build
```

Cela construira l'image et lancera le conteneur. L'application sera également accessible à [http://localhost:5000](http://localhost:5000).

---

## ✏️ Notes techniques

- Seules les routes avec **Plottsett 8** sont prises en compte
- Les fichiers `.gz` sont lus sans avoir besoin d'être manuellement décompressés
- Si plusieurs routes valides sont présentes, l'utilisateur doit choisir
- RTZ généré conforme sans balises inutiles (`extensions`, `schedules` supprimés)

---

## 🛠️ Structure du projet

```
olex2rtz/
│
├── app.py             # Application Flask principale
├── index.html         # Formulaire web
├── requirements.txt   # Dépendances Python
├── Dockerfile         # Fichier pour construire l'image Docker
├── docker-compose.yml # Fichier pour gérer les conteneurs avec Docker Compose
├── .dockerignore      # Fichiers ignorés lors de la construction Docker
├── README.md          # Ce fichier
└── venv/              # Environnement virtuel (non versionné)
```