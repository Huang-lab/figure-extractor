from flask import request, jsonify, send_from_directory
from . import app
from .utils import save_uploaded_file, read_output_file, save_and_extract_zip
from .service import run_pdffigures2, count_figures_and_tables, run_pdffigures2_batch
import os, logging, shutil
import logging

MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
ALLOWED_EXTENSIONS = {'pdf'}

@app.route('/extract', methods=['POST'])
def extract_figures():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file:
        file_path = save_uploaded_file(file)
        output_dir = app.config['OUTPUT_FOLDER']
        os.makedirs(output_dir, exist_ok=True)

        result = run_pdffigures2(file_path, output_dir)
        if 'error' in result:
            logging.error(f"Error executing command: {result['error']}")
            return jsonify({"error": result['error']}), 500

        output_file = os.path.join(output_dir, f"{os.path.splitext(file.filename)[0]}.json")
        figures = read_output_file(output_file)
        if figures is None:
            return jsonify({"error": f"Output file not found: {output_file}"}), 500
        
        logging.debug(f"Returned by pdffigures2 in /extract {result}")

        num_tables, num_figures = count_figures_and_tables(figures)
        response = {
            "num_tables": num_tables,
            "num_figures": num_figures,
            "metadata_file": os.path.basename(output_file),
            "figures": [fig['renderURL'] for fig in figures if fig.get('figType') == 'Figure'],
            "tables": [fig['renderURL'] for fig in figures if fig.get('figType') == 'Table'],
            "metadata_filename": os.path.basename(output_file),
            "pages": 0
        }
        return jsonify(response), 200

@app.route('/extract_batch', methods=['POST'])
def extract_batch():
    logging.info("Starting route")
    if 'folder' not in request.files:
        logging.error("No folder part in request")
        return jsonify({"error": "No folder part"}), 400

    folder = request.files['folder']
    if folder.filename == '':
        logging.error("No selected folder")
        return jsonify({"error": "No selected folder"}), 400

    if folder:
        temp_dir = None
        logging.debug(f"Received folder: {folder.filename}")
        try:
            temp_dir = save_and_extract_zip(folder)
            logging.debug(f"Extracted zip to directory: {temp_dir}")
            
            output_dir = app.config['OUTPUT_FOLDER']
            os.makedirs(output_dir, exist_ok=True)

            input_dir = temp_dir
            logging.debug(f"Processing directory: {input_dir}")

            response = run_pdffigures2_batch(input_dir, output_dir)
            logging.debug(f"Command result: {response}")

            return jsonify(response), 200
        
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            return jsonify({"error": str(e)}), 500
        
        finally:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """
    Download the extracted file.
    """
    directory = app.config['OUTPUT_FOLDER']
    return send_from_directory(directory, filename)


