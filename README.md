# 🧭 Olex2RTZ – Convertisseur de routes Olex vers RTZ 1.0

**Olex2RTZ** est une application web légère développée avec Flask, permettant de convertir des fichiers de routes `olexplot.gz` générés par le logiciel Olex en fichiers RTZ conformes à la norme RTZ 1.0, utilisée dans la navigation maritime.

---

## 🚀 Fonctionnalités principales

- **Téléversement** d’un fichier `olexplot.gz` via une interface web simple.  
- **Extraction** et **conversion** automatique des routes Olex vers le format RTZ 1.0.
- **Affichage** des routes sur une cartes. 
- **Téléchargement** du fichier `.rtz` généré.

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

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Lancer l'application**
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

### 2. Construire et lancer l’application

Lance la commande suivante pour **construire l’image** localement à partir du `Dockerfile` et **démarrer le service** :

```bash
docker-compose up -d --build
```

Cela va :
- construire l’image Docker à partir du code source,
- créer et démarrer le conteneur,
- exposer le service sur le port `5000` (accessible sur http://localhost:5000 ou depuis l’IP du serveur).

### 3. Arrêter et supprimer les conteneurs

```bash
docker-compose down
```

---

## 📁 Structure du projet

```
olex2rtz/
├── app/                  # Application Flask
│   ├── __init__.py       # Configuration et création de l'app
│   ├── routes.py         # Routes et vues
│   ├── converter_service.py # Logique de conversion
│   ├── email_utils.py    # Utilitaires email
│   ├── exceptions.py     # Exceptions personnalisées
│   ├── utils.py          # Utilitaires généraux
│   ├── cleanup.py        # Nettoyage des sessions
│   └── templates/        # Templates HTML
├── static/               # Fichiers statiques (CSS, JS, images)
├── run.py                # Point d'entrée de l'application
├── requirements.txt      # Dépendances Python
├── Dockerfile            # Image Docker de l'application
├── docker-compose.yml    # Déploiement simplifié avec Docker Compose
├── README.md             # Documentation du projet
└── LICENSE               # Licence MIT
```

---

## 📄 Licence

Ce projet est sous licence [MIT](LICENSE).

---

## 🤝 Contribuer

Les contributions sont les bienvenues ! N'hésitez pas à proposer des améliorations via issues ou pull requests.
