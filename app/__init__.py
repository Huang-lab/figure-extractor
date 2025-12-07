from flask import Flask
import os
import logging
from flask_swagger_ui import get_swaggerui_blueprint

# Configure logging level from environment
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Configure Flask app
app = Flask(__name__)

# Use environment variables for directories to keep them consistent with Docker
UPLOAD_ROOT = os.getenv('UPLOAD_DIR', '/app/uploads/')
OUTPUT_ROOT = os.getenv('OUTPUT_DIR', '/app/output/')

app.config['UPLOAD_FOLDER'] = UPLOAD_ROOT
app.config['OUTPUT_FOLDER'] = OUTPUT_ROOT
# Enforce a maximum upload size (64 MB by default, overridable via env)
app.config['MAX_CONTENT_LENGTH'] = int(os.getenv('MAX_CONTENT_LENGTH', 64 * 1024 * 1024))
# Allowed file extensions for single-file uploads (can be overridden via env)
app.config['ALLOWED_EXTENSIONS'] = set(
    ext.strip().lower() for ext in os.getenv('ALLOWED_EXTENSIONS', 'pdf').split(',') if ext.strip()
)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

from . import routes

# Start background cleanup worker
from .cleanup import start_cleanup_worker

if os.getenv('ENABLE_CLEANUP', 'true').lower() == 'true':
    cleanup_interval = int(os.getenv('CLEANUP_INTERVAL_SECONDS', '3600'))
    try:
        start_cleanup_worker(UPLOAD_ROOT, OUTPUT_ROOT, cleanup_interval)
        logging.info(f"Cleanup worker enabled (interval: {cleanup_interval}s)")
    except Exception as e:
        logging.error(f"Failed to start cleanup worker: {e}")
else:
    logging.info("Cleanup worker disabled (ENABLE_CLEANUP=false)")

# Documentation via Swagger UI
SWAGGER_URL = '/api/docs'  # URL for exposing Swagger UI
API_URL = '/static/openapi.yaml' 

# Call factory function to create our blueprint
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={  # Swagger UI config overrides
        'app_name': "Figure Extractor API"
    }
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)