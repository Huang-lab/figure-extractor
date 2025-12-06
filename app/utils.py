from werkzeug.utils import secure_filename
import os
import json
import tempfile, zipfile
import logging
from flask import current_app


def save_uploaded_file(file):
    """Save an uploaded file to the configured upload folder.

    Uses Flask's UPLOAD_FOLDER config, falling back to /app/uploads/ if not set.
    """
    upload_root = getattr(current_app, 'config', {}).get('UPLOAD_FOLDER', '/app/uploads/')
    os.makedirs(upload_root, exist_ok=True)

    filename = secure_filename(file.filename)
    file_path = os.path.join(upload_root, filename)
    file.save(file_path)
    return file_path


def read_output_file(output_file):
    if not os.path.exists(output_file):
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
        str: The path to the temporary directory containing the extracted files.

    Raises:
        Any exceptions raised by the underlying file operations or zip extraction.
    """
    temp_dir = tempfile.mkdtemp()
    zip_path = os.path.join(temp_dir, folder.filename)
    logging.debug(f"Saving zip file to: {zip_path}")
    folder.save(zip_path)

    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        logging.debug(f"Extracting zip file: {zip_path}")
        zip_ref.extractall(temp_dir)

    os.remove(zip_path)
    logging.debug(f"Removed zip file: {zip_path}")
    return temp_dir
