from flask import Flask
import os
import logging
from flask_swagger_ui import get_swaggerui_blueprint

logging.basicConfig(level=logging.DEBUG)

# Configure Flask app
app = Flask(__name__)

# Use environment variables for directories to keep them consistent with Docker
UPLOAD_ROOT = os.getenv('UPLOAD_DIR', '/app/uploads/')
OUTPUT_ROOT = os.getenv('OUTPUT_DIR', '/app/output/')

app.config['UPLOAD_FOLDER'] = UPLOAD_ROOT
app.config['OUTPUT_FOLDER'] = OUTPUT_ROOT
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

from . import routes

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