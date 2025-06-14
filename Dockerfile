# Image légère Python avec Alpine
FROM python:alpine

# Définir le répertoire de travail
WORKDIR /app

# Copier le contenu du projet dans l'image
COPY . /app

# Installer les dépendances système nécessaires (compilation, SSL, etc.)
RUN apk add --no-cache gcc musl-dev libffi-dev && \
    pip install --no-cache-dir -r requirements.txt

# Exposer le port de l'application Flask via Gunicorn
EXPOSE 5000

# Démarrer avec Gunicorn et charger l'application depuis run.py
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]