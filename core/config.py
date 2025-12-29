import os
from pathlib import Path

# Base directory of the project
BASE_DIR = Path(__file__).resolve().parent.parent

# pdffigures2 configuration
PDF_FIGURES2_JAR = os.getenv('PDFFIGURES2_JAR', str(BASE_DIR / 'pdffigures2' / 'pdffigures2.jar'))
PDF_FIGURES2_CWD = os.getenv('PDF_FIGURES2_CWD', str(BASE_DIR / 'pdffigures2'))
DEFAULT_DPI = os.getenv('PDFFIGURES2_DPI', '300')
JAVA_OPTS = os.getenv('JAVA_OPTS', '-Xmx2g')
PDFFIGURES2_TIMEOUT = int(os.getenv('PDFFIGURES2_TIMEOUT_SECONDS', '300'))

# Flask app configuration
UPLOAD_ROOT = os.getenv('UPLOAD_DIR', str(BASE_DIR / 'uploads'))
OUTPUT_ROOT = os.getenv('OUTPUT_DIR', str(BASE_DIR / 'output'))
MAX_CONTENT_LENGTH = int(os.getenv('MAX_CONTENT_LENGTH', 64 * 1024 * 1024))
ALLOWED_EXTENSIONS = set(
    ext.strip().lower() for ext in os.getenv('ALLOWED_EXTENSIONS', 'pdf').split(',') if ext.strip()
)

# Cleanup configuration
ENABLE_CLEANUP = os.getenv('ENABLE_CLEANUP', 'true').lower() == 'true'
CLEANUP_INTERVAL_SECONDS = int(os.getenv('CLEANUP_INTERVAL_SECONDS', '3600'))

# Logging configuration
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
