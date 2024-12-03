from flask import request, jsonify, send_from_directory
from . import app
from .utils import save_uploaded_file, read_output_file
from .service import run_pdffigures2, count_figures_and_tables
import os, logging

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

@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """
    Download the extracted file.
    """
    directory = app.config['OUTPUT_FOLDER']
    return send_from_directory(directory, filename)