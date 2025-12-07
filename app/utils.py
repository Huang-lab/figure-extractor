from werkzeug.utils import secure_filename
import os
import json
import tempfile, zipfile
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
    """Get or generate request ID for tracking.
    
    Returns:
        str: Request ID from header or newly generated UUID
    """
    return request.headers.get('X-Request-ID', str(uuid.uuid4()))


def error_response(message, error_code=None, status_code=400, details=None):
    """Create a standardized error response.
    
    Args:
        message: Human-readable error message
        error_code: Machine-readable error code from ERROR_CODES
        status_code: HTTP status code (default: 400)
        details: Optional additional details (dict)
        
    Returns:
        tuple: (JSON response, status_code)
    """
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
    """Create a standardized success response.
    
    Args:
        data: Response data (dict, list, or any JSON-serializable)
        message: Optional success message
        status_code: HTTP status code (default: 200)
        
    Returns:
        tuple: (JSON response, status_code)
    """
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
    """Validate uploaded file is a valid PDF.
    
    Args:
        file: FileStorage object from Flask request
        
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not file:
        return False, "No file provided"
    
    if file.filename == '':
        return False, "Empty filename"
    
    # Check file extension
    filename = secure_filename(file.filename)
    if not filename.lower().endswith('.pdf'):
        return False, f"Invalid file type. Expected PDF, got: {filename}"
    
    # Check magic bytes (PDF signature)
    file.seek(0)
    header = file.read(5)
    file.seek(0)  # Reset for later processing
    
    if not header.startswith(b'%PDF-'):
        return False, "File is not a valid PDF (invalid magic bytes)"
    
    # Check file size
    file.seek(0, os.SEEK_END)
    file_size = file.tell()
    file.seek(0)
    
    max_size = current_app.config.get('MAX_CONTENT_LENGTH', 100 * 1024 * 1024)
    if file_size > max_size:
        return False, f"File too large: {file_size} bytes (max: {max_size})"
    
    if file_size < 100:  # Minimum reasonable PDF size
        return False, f"File too small to be a valid PDF: {file_size} bytes"
    
    return True, None


def sanitize_filename(filename):
    """Sanitize filename and add uniqueness.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename with timestamp prefix
    """
    # Use werkzeug's secure_filename
    safe_name = secure_filename(filename)
    
    # Add timestamp prefix for uniqueness
    timestamp = datetime.utcnow().strftime('%Y%m%d_%H%M%S')
    unique_id = str(uuid.uuid4())[:8]
    
    name_parts = safe_name.rsplit('.', 1)
    if len(name_parts) == 2:
        return f"{timestamp}_{unique_id}_{name_parts[0]}.{name_parts[1]}"
    else:
        return f"{timestamp}_{unique_id}_{safe_name}"


def save_uploaded_file(file):
    """Save an uploaded file to the configured upload folder.

    Uses Flask's UPLOAD_FOLDER config, falling back to /app/uploads/ if not set.
    
    Args:
        file: FileStorage object from Flask request
        
    Returns:
        Path: Path object pointing to the saved file
    """
    upload_root = Path(getattr(current_app, 'config', {}).get('UPLOAD_FOLDER', '/app/uploads/'))
    upload_root.mkdir(parents=True, exist_ok=True)

    filename = secure_filename(file.filename)
    file_path = upload_root / filename
    file.save(str(file_path))
    return file_path


def read_output_file(output_file):
    """Read and parse a JSON output file.
    
    Args:
        output_file: Path to the JSON file (string or Path object)
        
    Returns:
        Parsed JSON data or None if file doesn't exist
    """
    output_file = Path(output_file)
    if not output_file.exists():
        return None
    with open(output_file, 'r') as f:
        output_data = f.read()
    return json.loads(output_data)


def save_and_extract_zip(folder):
    """
    Saves the uploaded zip file to a temporary directory, extracts its contents,
    and then removes the zip file.

    Args:
        folder (werkzeug.datastructures.FileStorage): The uploaded zip file.

    Returns:
        Path: Path object pointing to the temporary directory containing the extracted files.

    Raises:
        Any exceptions raised by the underlying file operations or zip extraction.
    """
    temp_dir = Path(tempfile.mkdtemp())
    zip_path = temp_dir / folder.filename
    logging.debug(f"Saving zip file to: {zip_path}")
    folder.save(str(zip_path))

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        logging.debug(f"Extracting zip file: {zip_path}")
        zip_ref.extractall(temp_dir)

    zip_path.unlink()
    logging.debug(f"Removed zip file: {zip_path}")
    return temp_dir
