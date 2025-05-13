# cleanup.py
import os
import time

SESSION_DIR = "/app/.flask_session"
MAX_AGE_SECONDS = 7 * 24 * 3600  # 7 jours

def cleanup_old_sessions():
    now = time.time()
    if not os.path.exists(SESSION_DIR):
        return

    for filename in os.listdir(SESSION_DIR):
        path = os.path.join(SESSION_DIR, filename)
        if os.path.isfile(path):
            age = now - os.path.getmtime(path)
            if age > MAX_AGE_SECONDS:
                try:
                    os.remove(path)
                    print(f"🧹 Supprimé : {path}")
                except Exception as e:
                    print(f"Erreur suppression {path}: {e}")
