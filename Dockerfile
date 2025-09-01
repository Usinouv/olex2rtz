# Build stage
FROM python:alpine AS builder

# Installer les dépendances système nécessaires pour la compilation
RUN apk add --no-cache gcc musl-dev libffi-dev

# Définir le répertoire de travail
WORKDIR /app

# Copier requirements et installer les dépendances Python
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# Production stage
FROM python:alpine

# Installer uniquement les dépendances runtime nécessaires
RUN apk add --no-cache libffi

# Créer un utilisateur non-root
RUN addgroup -g 1001 -S appuser && \
    adduser -u 1001 -S appuser -G appuser

# Définir le répertoire de travail
WORKDIR /app

# Copier les dépendances installées depuis le stage builder
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# Copier le contenu du projet
COPY . .

# Changer les permissions
RUN chown -R appuser:appuser /app
USER appuser

# Exposer le port
EXPOSE 5000

# Démarrer avec Gunicorn
CMD ["gunicorn", "-c", "gunicorn.conf.py", "run:app"]