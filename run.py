from app import create_app
import os

app = create_app()

if __name__ == "__main__":
    debug_mode = os.getenv("FLASK_DEBUG", "false").lower() in {"1", "true", "yes", "on"}
    app.run(debug=debug_mode, host="0.0.0.0")
