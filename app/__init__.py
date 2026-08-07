from flask import Flask, request, redirect, url_for, flash
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv, find_dotenv
from flask_session import Session  # <-- Ajouté
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.exceptions import RequestEntityTooLarge
import getpass

csrf = CSRFProtect()

def create_app():
    load_dotenv(find_dotenv(), override=True)
    
    app = Flask(__name__, static_folder="../static", template_folder="templates")
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        import secrets
        secret_key = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY not set, using generated key. Set SECRET_KEY in environment for production.")
    app.secret_key = secret_key

    # Limite d'upload configurable (en Mo) pour les fichiers GPX/RTZ volumineux.
    max_content_length_mb_env = os.getenv("MAX_CONTENT_LENGTH_MB", "64")
    try:
        max_content_length_mb = int(max_content_length_mb_env)
    except ValueError:
        max_content_length_mb = 64
        app.logger.warning(
            f"Invalid MAX_CONTENT_LENGTH_MB={max_content_length_mb_env!r}, falling back to 64 MB."
        )
    app.config["MAX_CONTENT_LENGTH"] = max_content_length_mb * 1024 * 1024
    
    # Configuration WorldTides API
    app.config["WORLDTIDES_API_KEY"] = os.getenv("WORLDTIDES_API_KEY")
    if not app.config["WORLDTIDES_API_KEY"]:
        app.logger.warning("WORLDTIDES_API_KEY not set. GPX bathymetry conversion will not work.")

    # Configurer Flask-Session pour stockage sur disque
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = os.path.join(os.getcwd(), ".flask_session")
    app.config["SESSION_PERMANENT"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "true").lower() in {"1", "true", "yes", "on"}
    Session(app)  # <-- Initialisation de Flask-Session
    csrf.init_app(app)

    # Logging : fichier + stdout (docker logs / Dozzle)
    log_handler = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=3)
    log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    logger = logging.getLogger()  # Logger racine
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)
    logger.addHandler(stream_handler)

    # Debug: Log current user and file permissions
    try:
        import getpass
        current_user = getpass.getuser()
        logger.info(f"Current user: {current_user}")
    except Exception as e:
        logger.warning(f"Could not get current user: {e}")

    log_file_path = os.path.join(os.getcwd(), "app.log")
    if os.path.exists(log_file_path):
        try:
            stat_info = os.stat(log_file_path)
            logger.info(f"app.log permissions: {oct(stat_info.st_mode)}")
            logger.info(f"app.log owner UID: {stat_info.st_uid}, GID: {stat_info.st_gid}")
        except Exception as e:
            logger.warning(f"Could not get app.log permissions: {e}")
    else:
        logger.info("app.log does not exist yet, will be created")

    logger.info("Logger configuré avec succès.")
    
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        app.logger.warning(f"CSRF validation failed: {e.description}")
        return "Invalid or missing CSRF token.", 400

    @app.errorhandler(RequestEntityTooLarge)
    def handle_request_entity_too_large(e):
        max_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
        app.logger.warning(f"Upload rejected (too large). Limit: {max_mb} MB. Path: {request.path}")
        flash(f"Fichier trop volumineux. Taille maximale autorisée: {max_mb} Mo.", "error")
        if request.path.startswith("/tools/gpx2xyz"):
            return redirect(url_for("main.gpx2xyz_upload"))
        return redirect(url_for("main.index"))

    # Nettoyage des fichiers de session anciens
    try:
        from .cleanup import cleanup_old_sessions
        cleanup_old_sessions()
    except Exception as e:
        app.logger.warning(f"Échec du nettoyage des sessions : {e}")

    return app
