# Gunicorn config file
# https://docs.gunicorn.org/en/stable/settings.html

# Worker settings
workers = 4
worker_class = "sync"

# Server socket
bind = "0.0.0.0:5000"

# Logging
accesslog = "-"
errorlog = "-"

# Timeout
# Default is 30s. Set to 5 minutes for slow uploads.
timeout = 300