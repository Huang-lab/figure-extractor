from werkzeug.utils import secure_filename
import os
import json
import tempfile, zipfile
import logging
from pathlib import Path
from flask import current_app


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
