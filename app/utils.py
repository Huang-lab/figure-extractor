from werkzeug.utils import secure_filename
import os
import json
import tempfile, zipfile

def save_uploaded_file(file):
    filename = secure_filename(file.filename)
    file_path = os.path.join('/app/uploads/', filename)
    file.save(file_path)
    return file_path

def read_output_file(output_file):
    if not os.path.exists(output_file):
        return None
    with open(output_file, 'r') as f:
        output_data = f.read()
    return json.loads(output_data)


import logging
import requests

# Configure logging
logging.basicConfig(level=logging.DEBUG)


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

def process_command_result(result):
    try:
        structured_output = []
        for item in result:
            try:
                metadata_file = item['filename'] + '.json'
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                file_metadata = {
                    "filename": os.path.basename(item['filename']),
                    "num_figures": item['numFigures'],
                    "num_pages": item['numPages'],
                    "time_in_millis": item['timeInMillis'],
                    "metadata_file": item['filename'] + '.json',
                    "figures": [fig['renderURL'] for fig in metadata if fig.get('figType') == 'Figure'],
                    "tables": [fig['renderURL'] for fig in metadata if fig.get('figType') == 'Table']
                }
                structured_output.append(file_metadata)
            except json.JSONDecodeError:
                logging.error("Failed to decode metadata file as JSON")
                return {"error": "Failed to decode metadata file as JSON"}, 500

        response = {
            "documents": structured_output,
            "metadata_file": 'stat_file.json'
        }
        return response, 200
    except Exception as e:  
        logging.error(f"An error occurred: {str(e)}")
        return {"error": str(e)}, 500
