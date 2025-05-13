from flask import Flask
import os
import logging
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv, find_dotenv
from flask_session import Session  # <-- Ajouté

def create_app():
    load_dotenv(find_dotenv(), override=True)
    
    app = Flask(__name__, static_folder="../static", template_folder="templates")
    app.secret_key = os.getenv("SECRET_KEY", "default_dev_secret_JQ$5xWp5")
    app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024  # 8 MB

    # Configurer Flask-Session pour stockage sur disque
    app.config["SESSION_TYPE"] = "filesystem"
    app.config["SESSION_FILE_DIR"] = os.path.join(os.getcwd(), ".flask_session")
    app.config["SESSION_PERMANENT"] = False
    Session(app)  # <-- Initialisation de Flask-Session

    # Logging
    log_handler = RotatingFileHandler("app.log", maxBytes=5 * 1024 * 1024, backupCount=3)
    log_handler.setLevel(logging.INFO)
    log_handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
    logging.basicConfig(level=logging.INFO, handlers=[log_handler, logging.StreamHandler()])

    from .routes import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app
