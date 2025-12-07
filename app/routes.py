from flask import request, jsonify, send_from_directory, g
from . import app, limiter
from .utils import (
    save_uploaded_file, read_output_file, save_and_extract_zip,
    error_response, success_response, validate_pdf_file, 
    sanitize_filename, ERROR_CODES
)
from .service import run_pdffigures2, count_figures_and_tables, run_pdffigures2_batch
import logging
import shutil
from pathlib import Path


def allowed_file(filename: str) -> bool:
    """Check if the uploaded file has an allowed extension."""
    allowed = app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


@app.route('/extract', methods=['POST'])
@limiter.limit("10 per minute")
def extract_figures():
    """Extract figures and tables from a single PDF file.
    
    Rate limit: 10 requests per minute
    
    Returns:
        JSON response with extraction results or error message
    """
    # Validate file presence
    if 'file' not in request.files:
        return error_response(
            "No file uploaded",
            error_code=ERROR_CODES['VALIDATION_ERROR'],
            status_code=400
        )

    file = request.files['file']
    
    # Validate PDF file
    is_valid, error_msg = validate_pdf_file(file)
    if not is_valid:
        return error_response(
            error_msg,
            error_code=ERROR_CODES['INVALID_FILE_TYPE'],
            status_code=400
        )

    file_path = None
    try:
        # Save with sanitized filename
        file_path = save_uploaded_file(file)
        output_dir = Path(app.config['OUTPUT_FOLDER'])
        output_dir.mkdir(parents=True, exist_ok=True)

        # run_pdffigures2 now raises on error and returns a summary dict
        result = run_pdffigures2(file_path, output_dir)
        
        logging.info(f"Successfully extracted figures from {file.filename}")

        # Build response data
        data = {
            "num_tables": result.get("n_tables", 0),
            "num_figures": result.get("n_figures", 0),
            "metadata_file": result.get("metadata_filename"),
            "metadata_filename": result.get("metadata_filename"),
            "figures": result.get("figures", []),
            "tables": result.get("tables", []),
            "pages": result.get("pages", 0),
            "time_in_millis": result.get("time_in_millis", 0),
            "document": result.get("document"),
        }
        
        return success_response(
            data=data,
            message="Figures extracted successfully"
        )
        
    except Exception as e:
        logging.error(f"Error executing pdffigures2: {e}")
        return error_response(
            f"Failed to extract figures: {str(e)}",
            error_code=ERROR_CODES['PROCESSING_ERROR'],
            status_code=500
        )
        
    finally:
        # CRITICAL: Clean up uploaded file to prevent disk space exhaustion
        if file_path and file_path.exists():
            try:
                file_path.unlink()
                logging.debug(f"Cleaned up uploaded file: {file_path}")
            except Exception as cleanup_error:
                logging.error(f"Failed to cleanup {file_path}: {cleanup_error}")


@app.route('/extract_batch', methods=['POST'])
@limiter.limit("5 per minute")
def extract_batch():
    """Extract figures and tables from multiple PDF files in a ZIP archive.
    
    Rate limit: 5 requests per minute (more intensive than single file)
    
    Returns:
        JSON response with extraction results for all PDFs or error message
    """
    logging.info("Starting batch extraction route")
    
    # Validate file presence
    if 'folder' not in request.files:
        return error_response(
            "No ZIP file uploaded",
            error_code=ERROR_CODES['VALIDATION_ERROR'],
            status_code=400
        )

    folder = request.files['folder']
    
    if folder.filename == '':
        return error_response(
            "Empty filename",
            error_code=ERROR_CODES['VALIDATION_ERROR'],
            status_code=400
        )

    # Enforce ZIP file type
    if not folder.filename.lower().endswith('.zip'):
        return error_response(
            "Invalid file type. Please upload a .zip file containing PDFs.",
            error_code=ERROR_CODES['INVALID_FILE_TYPE'],
            status_code=400
        )

    if folder:
        temp_dir = None
        logging.debug(f"Received folder: {folder.filename}")
        try:
            temp_dir = save_and_extract_zip(folder)
            logging.debug(f"Extracted zip to directory: {temp_dir}")
            
            output_dir = Path(app.config['OUTPUT_FOLDER'])
            output_dir.mkdir(parents=True, exist_ok=True)

            logging.info(f"Processing batch directory: {temp_dir}")

            result = run_pdffigures2_batch(temp_dir, output_dir)
            logging.info(f"Batch extraction completed successfully")

            return success_response(
                data=result,
                message="Batch extraction completed"
            )
        
        except Exception as e:
            logging.error(f"Batch extraction error: {str(e)}")
            return error_response(
                f"Batch extraction failed: {str(e)}",
                error_code=ERROR_CODES['PROCESSING_ERROR'],
                status_code=500
            )
        
        finally:
            if temp_dir and temp_dir.exists():
                try:
                    shutil.rmtree(temp_dir)
                    logging.debug(f"Cleaned up temp directory: {temp_dir}")
                except Exception as cleanup_error:
                    logging.error(f"Failed to cleanup {temp_dir}: {cleanup_error}")


@app.route('/download/<filename>', methods=['GET'])
@limiter.limit("30 per minute")
def download_file(filename):
    """Download the extracted file.
    
    Rate limit: 30 requests per minute
    
    Args:
        filename: Name of the file to download
        
    Returns:
        File download response or error
    """
    try:
        directory = Path(app.config['OUTPUT_FOLDER'])
        file_path = directory / filename
        
        # Security: prevent directory traversal
        if not file_path.resolve().is_relative_to(directory.resolve()):
            return error_response(
                "Invalid filename",
                error_code=ERROR_CODES['VALIDATION_ERROR'],
                status_code=400
            )
        
        if not file_path.exists():
            return error_response(
                f"File not found: {filename}",
                error_code=ERROR_CODES['FILE_NOT_FOUND'],
                status_code=404
            )
        
        return send_from_directory(str(directory), filename)
        
    except Exception as e:
        logging.error(f"Download error: {e}")
        return error_response(
            "Failed to download file",
            error_code=ERROR_CODES['INTERNAL_ERROR'],
            status_code=500
        )


@app.route('/health', methods=['GET'])
@limiter.exempt
def health():
    """Health check endpoint for load balancers and orchestrators.
    
    No rate limit applied to health checks.
    
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
@limiter.exempt
def readiness():
    """Readiness check - verify all dependencies are available.
    
    No rate limit applied to readiness checks.
    
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


# Custom error handler for rate limiting
@app.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limit exceeded errors with standardized response."""
    return error_response(
        "Rate limit exceeded. Please try again later.",
        error_code=ERROR_CODES['RATE_LIMIT_EXCEEDED'],
        status_code=429,
        details={
            "retry_after": getattr(e, 'description', 'Please wait before retrying')
        }
    )

