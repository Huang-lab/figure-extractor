from flask import Flask
import os
import logging

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = '/app/uploads/'
app.config['OUTPUT_FOLDER'] = '/app/outputs/'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)

# Configure logging
logging.basicConfig(level=logging.INFO)

from . import routes