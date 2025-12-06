from flask import request, jsonify, send_from_directory
from . import app
from .utils import save_uploaded_file, read_output_file, save_and_extract_zip
from .service import run_pdffigures2, count_figures_and_tables, run_pdffigures2_batch
import os, logging, shutil
import logging


def allowed_file(filename: str) -> bool:
    """Check if the uploaded file has an allowed extension."""
    allowed = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


@app.route('/extract', methods=['POST'])
def extract_figures():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Only PDF files are allowed."}), 400

    if file:
        file_path = save_uploaded_file(file)
        output_dir = app.config['OUTPUT_FOLDER']
        os.makedirs(output_dir, exist_ok=True)

        try:
            # run_pdffigures2 now raises on error and returns a summary dict
            result = run_pdffigures2(file_path, output_dir)
        except Exception as e:
            logging.error(f"Error executing pdffigures2: {e}")
            return jsonify({"error": str(e)}), 500

        logging.debug(f"Returned by pdffigures2 in /extract {result}")

        # Build response directly from the parsed metadata summary
        response = {
            "num_tables": result.get("n_tables", 0),
            "num_figures": result.get("n_figures", 0),
            "metadata_file": result.get("metadata_filename"),
            "metadata_filename": result.get("metadata_filename"),
            "figures": result.get("figures", []),  # basenames
            "tables": result.get("tables", []),    # basenames
            "pages": result.get("pages", 0),
            "time_in_millis": result.get("time_in_millis", 0),
            "document": result.get("document"),
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

    # Optional: enforce that the uploaded batch is a ZIP file
    if not folder.filename.lower().endswith('.zip'):
        logging.error("Invalid folder upload type (expected .zip)")
        return jsonify({"error": "Invalid folder type. Please upload a .zip file containing PDFs."}), 400

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
    """Download the extracted file."""
    directory = app.config['OUTPUT_FOLDER']
    return send_from_directory(directory, filename)


