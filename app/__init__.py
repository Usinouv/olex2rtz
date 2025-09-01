from flask import Flask
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv, find_dotenv
from flask_session import Session  # <-- Ajouté

def create_app():
    load_dotenv(find_dotenv(), override=True)
    
    app = Flask(__name__, static_folder="../static", template_folder="templates")
    secret_key = os.getenv("SECRET_KEY")
    if not secret_key:
        import secrets
        secret_key = secrets.token_hex(32)
        app.logger.warning("SECRET_KEY not set, using generated key. Set SECRET_KEY in environment for production.")
    app.secret_key = secret_key
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB

    # Configurer Flask-Session pour stockage sur disque
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = os.path.join(os.getcwd(), ".flask_session")
    app.config["SESSION_PERMANENT"] = False
    Session(app)  # <-- Initialisation de Flask-Session

    # Logging : fichier + stdout (docker logs / Dozzle)
    log_handler = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=3)
    log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))

    logger = logging.getLogger()  # Logger racine
    logger.setLevel(logging.INFO)
    logger.addHandler(log_handler)
    logger.addHandler(stream_handler)
    logger.info("Logger configuré avec succès.")
    
    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    # Nettoyage des fichiers de session anciens
    try:
        from .cleanup import cleanup_old_sessions
        cleanup_old_sessions()
    except Exception as e:
        app.logger.warning(f"Échec du nettoyage des sessions : {e}")

    return app
