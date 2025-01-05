from flask import Flask
import os
import logging
from flask_swagger_ui import get_swaggerui_blueprint

logging.basicConfig(level=logging.DEBUG)

# Configure Flask app
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/app/uploads/'
app.config['OUTPUT_FOLDER'] = '/app/outputs/'
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