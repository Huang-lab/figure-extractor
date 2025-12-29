from werkzeug.utils import secure_filename
import os
import json
import tempfile
import zipfile
import logging
from pathlib import Path
from flask import current_app, jsonify, request
import uuid
from datetime import datetime

# Error codes for standardized responses
ERROR_CODES = {
    'VALIDATION_ERROR': 'VALIDATION_ERROR',
    'FILE_NOT_FOUND': 'FILE_NOT_FOUND',
    'PROCESSING_ERROR': 'PROCESSING_ERROR',
    'RATE_LIMIT_EXCEEDED': 'RATE_LIMIT_EXCEEDED',
    'INVALID_FILE_TYPE': 'INVALID_FILE_TYPE',
    'FILE_TOO_LARGE': 'FILE_TOO_LARGE',
    'INTERNAL_ERROR': 'INTERNAL_ERROR',
}

def get_request_id():
    """Get or generate request ID for tracking."""
    return request.headers.get('X-Request-ID', str(uuid.uuid4()))

def error_response(message, error_code=None, status_code=400, details=None):
    """Create a standardized error response."""
    request_id = get_request_id()
    response = {
        'success': False,
        'error': {
            'message': message,
            'code': error_code or ERROR_CODES['INTERNAL_ERROR'],
        },
        'request_id': request_id,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    if details:
        response['error']['details'] = details
    logging.error(f"[{request_id}] Error: {message} (code: {error_code})")
    return jsonify(response), status_code

def success_response(data=None, message=None, status_code=200):
    """Create a standardized success response."""
    request_id = get_request_id()
    response = {
        'success': True,
        'request_id': request_id,
        'timestamp': datetime.utcnow().isoformat() + 'Z'
    }
    if data is not None:
        response['data'] = data
    if message:
        response['message'] = message
    return jsonify(response), status_code

def validate_pdf_file(file):
    """Validate uploaded file is a valid PDF."""
    if not file:
        return False, "No file provided"
    if file.filename == '':
        return False, "Empty filename"
    
    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.pdf'):
        return False, f"Invalid file type. Expected PDF, got: {filename}"
    
    file.seek(0)
    header = file.read(5)
    file.seek(0)
    if not header.startswith(b'%PDF-'):
        return False, "File is not a valid PDF (invalid magic bytes)"
    
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 64 * 1024 * 1024)
    if file_size > max_size:
        return False, f"File too large: {file_size} bytes (max: {max_size})"
    
    return True, None

def save_uploaded_file(file):
    """Save an uploaded file to the configured upload folder."""
    upload_root = Path(current_app.config['UPLOAD_FOLDER'])
    upload_root.mkdir(parents=True, exist_ok=True)
    filename = secure_filename(file.filename)
    file_path = upload_root / filename
    file.save(str(file_path))
    return file_path

def save_and_extract_zip(folder):
    """Saves and extracts a zip file to a temporary directory."""
    temp_dir = Path(tempfile.mkdtemp())
    zip_path = temp_dir / secure_filename(folder.filename)
    folder.save(str(zip_path))
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(temp_dir)
    
    # Clean up the zip file itself after extraction
    if zip_path.exists():
        zip_path.unlink()
        
    return temp_dir
