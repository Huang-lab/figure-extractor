from flask import Flask, request, g
import os
import logging
from flask_swagger_ui import get_swaggerui_blueprint
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import uuid
from core.config import (
    LOG_LEVEL, UPLOAD_ROOT, OUTPUT_ROOT, MAX_CONTENT_LENGTH, 
    ALLOWED_EXTENSIONS, ENABLE_CLEANUP, CLEANUP_INTERVAL_SECONDS
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.DEBUG),
    format='%(asctime)s - [%(request_id)s] - %(name)s - %(levelname)s - %(message)s'
)

class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, 'request_id'):
            try:
                record.request_id = g.get('request_id', 'NO-REQUEST-ID')
            except (RuntimeError, AttributeError):
                record.request_id = 'SYSTEM'
        return True

for handler in logging.root.handlers:
    handler.addFilter(RequestIdFilter())
logging.getLogger().addFilter(RequestIdFilter())

app = Flask(__name__)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["2000 per hour", "1000 per minute"],
    storage_uri="memory://",
    strategy="fixed-window"
)

@app.before_request
def add_request_id():
    g.request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))

@app.after_request
def add_request_id_header(response):
    if hasattr(g, 'request_id'):
        response.headers['X-Request-ID'] = g.request_id
    return response

app.config['UPLOAD_FOLDER'] = UPLOAD_ROOT
app.config['OUTPUT_FOLDER'] = OUTPUT_ROOT
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['ALLOWED_EXTENSIONS'] = ALLOWED_EXTENSIONS

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

from . import routes

try:
    from .cleanup import start_cleanup_worker
    CLEANUP_AVAILABLE = True
except ImportError:
    CLEANUP_AVAILABLE = False

if CLEANUP_AVAILABLE and ENABLE_CLEANUP:
    try:
        start_cleanup_worker(UPLOAD_ROOT, OUTPUT_ROOT, CLEANUP_INTERVAL_SECONDS)
        logging.info(f"Cleanup worker enabled (interval: {CLEANUP_INTERVAL_SECONDS}s)")
    except Exception as e:
        logging.error(f"Failed to start cleanup worker: {e}")

SWAGGER_URL = '/api/docs'
API_URL = '/static/openapi.yaml' 
swaggerui_blueprint = get_swaggerui_blueprint(
    SWAGGER_URL,
    API_URL,
    config={'app_name': "Figure Extractor API"}
)
app.register_blueprint(swaggerui_blueprint, url_prefix=SWAGGER_URL)
