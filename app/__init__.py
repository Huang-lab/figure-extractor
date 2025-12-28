from flask import Flask, request, g
import os
import logging
from flask_swagger_ui import get_swaggerui_blueprint
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import uuid

# Configure logging level from environment
LOG_LEVEL = os.getenv('LOG_LEVEL', 'DEBUG').upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format='%(asctime)s - [%(request_id)s] - %(name)s - %(levelname)s - %(message)s'
)

# Custom logging filter to add request_id to log records
class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            # Safely get request_id, handling cases outside of request context
            try:
                record.request_id = g.get('request_id', 'NO-REQUEST-ID')
            except (RuntimeError, AttributeError):
                # Outside of application/request context (e.g., startup, background threads)
                record.request_id = 'SYSTEM'
        return True

# Add filter to root logger
for handler in logging.root.handlers:
    handler.addFilter(RequestIdFilter())
logging.getLogger().addFilter(RequestIdFilter())

# Configure Flask app
app = Flask(__name__)

# Initialize rate limiter
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000 per hour", "1000 per minute"],
    storage_uri="memory://",
    strategy="fixed-window"
)

# Request ID middleware - runs before each request
@app.before_request
def add_request_id():
    """Add request ID to Flask's g object for logging."""
    g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

# Response middleware - runs after each request
@app.after_request
def add_request_id_header(response):
    """Add request ID to response headers."""
    if hasattr(g, 'request_id'):
        response.headers['X-Request-ID'] = g.request_id
    return response

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

# Start background cleanup worker (optional feature)
try:
    from .cleanup import start_cleanup_worker
    CLEANUP_AVAILABLE = True
except ImportError:
    CLEANUP_AVAILABLE = False
    logging.warning("Cleanup module not available - automatic cleanup disabled")

if CLEANUP_AVAILABLE and os.getenv('ENABLE_CLEANUP', 'true').lower() == 'true':
    cleanup_interval = int(os.getenv('CLEANUP_INTERVAL_SECONDS', '3600'))
    try:
        start_cleanup_worker(UPLOAD_ROOT, OUTPUT_ROOT, cleanup_interval)
        logging.info(f"Cleanup worker enabled (interval: {cleanup_interval}s)")
    except Exception as e:
        logging.error(f"Failed to start cleanup worker: {e}")
else:
    if not CLEANUP_AVAILABLE:
        logging.info("Cleanup worker not available (module not found)")
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