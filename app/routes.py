from flask import request, jsonify, send_from_directory
from . import app
from .utils import save_uploaded_file, read_output_file, save_and_extract_zip
from .service import run_pdffigures2, count_figures_and_tables, run_pdffigures2_batch
import logging
import shutil
from pathlib import Path


def allowed_file(filename: str) -> bool:
    """Check if the uploaded file has an allowed extension."""
    allowed = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


@app.route('/extract', methods=['POST'])
def extract_figures():
    """Extract figures and tables from a single PDF file.
    
    Returns:
        JSON response with extraction results or error message
    """
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if not allowed_file(file.filename):
        return jsonify({"error": "Invalid file type. Only PDF files are allowed."}), 400

    file_path = None
    try:
        file_path = save_uploaded_file(file)
        output_dir = Path(app.config['OUTPUT_FOLDER'])
        output_dir.mkdir(parents=True, exist_ok=True)

        # run_pdffigures2 now raises on error and returns a summary dict
        result = run_pdffigures2(file_path, output_dir)
        
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
        
    except Exception as e:
        logging.error(f"Error executing pdffigures2: {e}")
        return jsonify({"error": str(e)}), 500
        
    finally:
        # CRITICAL: Clean up uploaded file to prevent disk space exhaustion
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logging.debug(f"Cleaned up uploaded file: {file_path}")
            except Exception as cleanup_error:
                logging.error(f"Failed to cleanup {file_path}: {cleanup_error}")


@app.route('/extract_batch', methods=['POST'])
def extract_batch():
    """Extract figures and tables from multiple PDF files in a ZIP archive.
    
    Returns:
        JSON response with extraction results for all PDFs or error message
    """
    logging.info("Starting batch extraction route")
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
            
            output_dir = Path(app.config['OUTPUT_FOLDER'])
            output_dir.mkdir(parents=True, exist_ok=True)

            logging.debug(f"Processing directory: {temp_dir}")

            response = run_pdffigures2_batch(temp_dir, output_dir)
            logging.debug(f"Command result: {response}")

            return jsonify(response), 200
        
        except Exception as e:
            logging.error(f"An error occurred: {str(e)}")
            return jsonify({"error": str(e)}), 500
        
        finally:
            if temp_dir and temp_dir.exists():
                shutil.rmtree(temp_dir)


@app.route('/download/<filename>', methods=['GET'])
def download_file(filename):
    """Download the extracted file.
    
    Args:
        filename: Name of the file to download
        
    Returns:
        File download response
    """
    directory = app.config['OUTPUT_FOLDER']
    return send_from_directory(directory, filename)


@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint for load balancers and orchestrators.
    
    Returns:
        JSON with status and HTTP 200 if healthy
    """
    import time
    return jsonify({
        "status": "healthy",
        "service": "figure-extractor",
        "version": "1.0.0",
        "timestamp": time.time()
    }), 200


@app.route('/ready', methods=['GET'])
def readiness():
    """Readiness check - verify all dependencies are available.
    
    Returns:
        JSON with status and HTTP 200 if ready, 503 if not ready
    """
    import os
    import time
    
    checks = {
        "pdffigures2_jar": False,
        "output_dir_writable": False,
        "upload_dir_writable": False,
    }
    
    try:
        # Check if pdffigures2 JAR exists
        jar_path = Path(os.getenv('PDFFIGURES2_JAR', '/pdffigures2/pdffigures2.jar'))
        checks["pdffigures2_jar"] = jar_path.exists()
        
        # Check output directory is writable
        output_dir = Path(app.config['OUTPUT_FOLDER'])
        checks["output_dir_writable"] = output_dir.exists() and os.access(output_dir, os.W_OK)
        
        # Check upload directory is writable
        upload_dir = Path(app.config['UPLOAD_FOLDER'])
        checks["upload_dir_writable"] = upload_dir.exists() and os.access(upload_dir, os.W_OK)
        
        # All checks must pass
        if all(checks.values()):
            return jsonify({
                "status": "ready",
                "checks": checks,
                "timestamp": time.time()
            }), 200
        else:
            return jsonify({
                "status": "not_ready",
                "checks": checks,
                "timestamp": time.time()
            }), 503
            
    except Exception as e:
        logging.error(f"Readiness check failed: {e}")
        return jsonify({
            "status": "error",
            "error": str(e),
            "checks": checks,
            "timestamp": time.time()
        }), 503

