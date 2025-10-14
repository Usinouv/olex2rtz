# Intégration GPX2XYZ - Documentation Technique

## Vue d'ensemble

Cette documentation décrit l'intégration de la fonctionnalité de conversion GPX bathymétrique avec correction de marée dans l'application Olex2RTZ.

## Fichiers créés

### 1. Service principal : `app/gpx_service.py`
**576 lignes** - Module complet de traitement GPX avec WorldTides API

**Fonctionnalités principales :**
- Parsing de fichiers GPX avec extraction des segments
- Calcul des statistiques de segments (points totaux, valides, période, coordonnées médianes)
- Intégration API WorldTides avec système de cache (mémoire + disque)
- Interpolation linéaire des hauteurs de marée
- Génération de fichiers XYZ et XYZ uniquement avec correction de marée
- Gestion d'erreurs robuste

### 2. Templates HTML

#### `app/templates/gpx2xyz_upload.html` (145 lignes)
- Page d'upload GPX (étape 1)
- Formulaire simple avec validation
- Instructions claires pour l'utilisateur
- Design cohérent avec l'application existante

#### `app/templates/gpx2xyz_segments.html` (349 lignes)
- Page de sélection de segment (étape 2)
- Dropdown pour sélection de segment
- Affichage des statistiques (points totaux, valides, période)
- Carte Leaflet affichant TOUS les segments avec couleurs différentes
- Bouton principal "Exporter en XYZ" + dropdown pour XYZ uniquement
- Design responsive et moderne

### 3. Routes Flask : modifications dans `app/routes.py`
**Ajout de 3 nouvelles routes :**
- `GET /tools/gpx2xyz` : Page d'upload
- `POST /tools/gpx2xyz/upload` : Traitement de l'upload et analyse
- `GET /tools/gpx2xyz/segments` : Page de sélection
- `POST /tools/gpx2xyz/convert` : Conversion et téléchargement

### 4. Configuration

#### `.env.example`
Ajout de la variable `WORLDTIDES_API_KEY` avec instructions

#### `app/__init__.py`
Configuration de la clé API WorldTides dans l'application Flask

#### `requirements.txt`
Ajout de `requests>=2.31.0`

#### `docker-compose.yml`
Ajout du volume `./cache:/app/cache` pour dev et prod

#### `.gitignore`
Ajout de `cache/` pour ignorer le cache WorldTides

## Architecture technique

### Flux de données

```
1. Upload GPX
   ↓
2. Parse XML → Extraction segments avec stats
   ↓
3. Stockage en session Flask
   ↓
4. Affichage segments + carte
   ↓
5. Sélection segment par utilisateur
   ↓
6. Appel WorldTides API (avec cache)
   ↓
7. Interpolation marée pour chaque point
   ↓
8. Calcul sonde = profondeur - marée
   ↓
9. Génération XYZ ou XYZ uniquement
   ↓
10. Téléchargement fichier
```

### Cache WorldTides

**Stratégie de cache à 2 niveaux :**

1. **Mémoire** : Dictionnaire Python (`_memory_cache`)
   - Plus rapide
   - Réinitialisé à chaque redémarrage

2. **Disque** : Fichiers JSON dans `./cache/worldtides/`
   - Persistant entre redémarrages
   - Partagé entre dev et prod
   - TTL configurable (défaut : illimité)

**Clé de cache :** SHA256 de `{url, lat, lon, start, end, step, datum}`

### Format de données

#### Entrée : Fichier GPX
```xml
<trkpt lat="XX.XXXXXX" lon="XX.XXXXXX">
  <time>2024-01-15T10:30:00Z</time>
  <extensions>
    <depth>15.5</depth>
  </extensions>
</trkpt>
```

#### Sortie XYZ
```
58.12345678 10.98765432 12.3
58.12346789 10.98766543 12.5
...
```

#### Sortie XYZ uniquement
```csv
time,lat,lon,depth_m,sonde_m
2024-01-15T10:30:00Z,58.12345678,10.98765432,15.5,12.3
2024-01-15T10:30:10Z,58.12346789,10.98766543,15.8,12.5
...
```

## Sécurité

### Page cachée
- URL `/tools/gpx2xyz` non listée dans la navigation
- Accessible uniquement par lien direct
- Protection future possible via authentification

### Validation des entrées
- Extension de fichier vérifiée (.gpx)
- Parsing XML sécurisé avec gestion d'erreurs
- Validation des coordonnées et timestamps
- Sanitisation des noms de fichiers

### Clé API
- Stockée dans variable d'environnement
- Non exposée dans le code
- Warning si manquante (pas d'erreur fatale)

## Performance

### Optimisations
- Cache WorldTides évite les appels API répétés
- Cache mémoire + disque pour vitesse maximale
- Interpolation linéaire simple et rapide
- Pas de stockage des points XML en session (sérialisation légère)

### Limites
- Taille max fichier : 16 MB (config Flask)
- Pas de limite sur nombre de segments
- Pas de limite sur nombre de points par segment
- WorldTides API : limites selon votre plan

## Tests recommandés

### Tests fonctionnels
1. ✅ Upload GPX valide avec plusieurs segments
2. ✅ Sélection d'un segment
3. ✅ Conversion en XYZ
4. ✅ Conversion en XYZ uniquement
5. ⚠️ Vérifier le cache (2e conversion = pas d'API call)
6. ⚠️ Test avec GPX sans depth → erreur claire
7. ⚠️ Test avec GPX sans time → erreur claire
8. ⚠️ Test sans clé API → message d'erreur approprié

### Tests Docker
1. ⚠️ Vérifier que le volume cache est bien monté
2. ⚠️ Vérifier le partage du cache entre dev et prod
3. ⚠️ Tester la persistence du cache après redémarrage

## Maintenance

### Mise à jour de l'API WorldTides
- URL API configurable (défaut : https://www.worldtides.info/api/v3)
- Datum configurable (défaut : CD - Chart Datum)
- Step configurable (défaut : 10 minutes)

### Purge du cache
Manuellement : `rm -rf ./cache/worldtides/*.json`

### Logs
- Tous les appels WorldTides sont loggés
- Erreurs avec stack traces
- Cache hit/miss loggé en mode debug

## Évolutions futures possibles

1. **Authentification** : Ajouter protection par mot de passe
2. **Batch processing** : Traiter plusieurs segments simultanément
3. **Visualisation avancée** : Graphique de marée sur la page de sélection
4. **Export additionnel** : Formats KML, GeoJSON
5. **Options utilisateur** : Choix du datum, du step, etc.
6. **API REST** : Endpoint JSON pour intégration externe
7. **Historique** : Liste des conversions récentes

## Support

Pour toute question ou problème :
1. Vérifier les logs de l'application (`app.log`)
2. Vérifier la configuration `.env`
3. Vérifier que la clé WorldTides est valide
4. Tester l'API WorldTides directement avec curl

## Références

- WorldTides API : https://www.worldtides.info/apidocs
- GPX Format : https://www.topografix.com/gpx.asp
- Flask Documentation : https://flask.palletsprojects.com/
- Leaflet Maps : https://leafletjs.com/

---

**Date d'intégration :** 2025-01-14  
**Version :** 1.0  
**Auteur :** Kilo Code (Assistant IA)