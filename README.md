# Olex2Rtz

Petit micro-site web pour convertir des routes et traces extraites d'Olex en fichier RTZ (Route Transfer Format).

## Installation

1. Cloner ce dépôt :
   git clone git@github.com:Usinouv/olex2rtz.git
   cd Olex2Rtz

2. Créer et activer un environnement virtuel :
   python3 -m venv venv
   source venv/bin/activate  # ou venv\Scriptsctivate sur Windows

3. Installer les dépendances :
   pip install -r requirements.txt

4. Lancer le serveur :
   python app.py

5. Accéder à :
   http://localhost:5000

## Format du fichier texte attendu

Chaque ligne du .txt :
48.8582, 2.2945
51.5074, -0.1278
