from flask import Flask
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv, find_dotenv
from flask_session import Session  # <-- Ajouté
import getpass

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
    
    # Configuration WorldTides API
    app.config["WORLDTIDES_API_KEY"] = os.getenv("WORLDTIDES_API_KEY")
    if not app.config["WORLDTIDES_API_KEY"]:
        app.logger.warning("WORLDTIDES_API_KEY not set. GPX bathymetry conversion will not work.")

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

    # Nettoyage des fichiers de session anciens
    try:
        from .cleanup import cleanup_old_sessions
        cleanup_old_sessions()
    except Exception as e:
        app.logger.warning(f"Échec du nettoyage des sessions : {e}")

    return app
