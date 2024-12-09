from flask import request, jsonify, send_from_directory
from . import app
from .utils import save_uploaded_file, read_output_file, save_and_extract_zip
from .service import run_pdffigures2, count_figures_and_tables, run_pdffigures2_batch
import os, logging
import tempfile
import zipfile, shutil

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
        if result.returncode != 0:
            logging.error(f"Error executing command: {result.stderr}")
            return jsonify({"error": result.stderr}), 500

        output_file = os.path.join(output_dir, f"{os.path.splitext(file.filename)[0]}.json")
        figures = read_output_file(output_file)
        if figures is None:
            return jsonify({"error": f"Output file not found: {output_file}"}), 500

        num_tables, num_figures = count_figures_and_tables(figures)
        response = {
            "num_tables": num_tables,
            "num_figures": num_figures,
            "metadata_file": os.path.basename(output_file),
            "figures": [fig['renderURL'] for fig in figures if fig.get('figType') == 'Figure'],
            "tables": [fig['renderURL'] for fig in figures if fig.get('figType') == 'Table']
        }
        return jsonify(response), 200
    

import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG)

@app.route('/extract_batch', methods=['POST'])
def extract_batch():
    logging.info("startint route")
    if 'folder' not in request.files:
        logging.error("No folder part in request")
        return jsonify({"error": "No folder part"}), 400

    folder = request.files['folder']
    if folder.filename == '':
        logging.error("No selected folder")
        return jsonify({"error": "No selected folder"}), 400

    if folder:
        temp_dir = None
        try:
            temp_dir = save_and_extract_zip(folder)
            logging.debug(f"Extracted zip to directory: {temp_dir}")
            
            output_dir = app.config['OUTPUT_FOLDER']
            os.makedirs(output_dir, exist_ok=True)

            # Add trailing slash for pdffigures2
            #input_dir = temp_dir if temp_dir.endswith('/') else temp_dir + '/'
            input_dir = temp_dir
            logging.debug(f"Processing directory: {input_dir}")

            result = run_pdffigures2_batch(input_dir, output_dir)



            if result.returncode != 0:
                logging.error(f"Error executing command: {result.stderr}")
                return jsonify({"error": result.stderr}), 500

            stat_file = os.path.join(output_dir, 'stat_file.json')
            if not os.path.exists(stat_file):
                logging.error(f"Statistics file not found: {stat_file}")
                return jsonify({"error": f"Statistics file not found: {stat_file}"}), 500

            return send_from_directory(output_dir, 'stat_file.json'), 200
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

@app.route('/images', methods=['GET'])
def list_images():
    """
    List all images in the output directory.
    """
    output_dir = app.config['OUTPUT_FOLDER']
    if not os.path.exists(output_dir):
        return jsonify({"error": "Output directory does not exist"}), 500

    images = [f for f in os.listdir(output_dir) if os.path.isfile(os.path.join(output_dir, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
    return jsonify({"images": images}), 200

