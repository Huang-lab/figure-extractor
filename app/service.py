# Service layer for running pdffigures2 and parsing output
import subprocess
import os
import logging
import time
import json
import time
from .utils import read_output_file

def parse_json_metadata(metadata_path, processing_time=None, filename=None):
    """Parse JSON metadata file and return structured result for single or batch extraction."""
    if not os.path.exists(metadata_path):
        logging.error(f"Metadata file not found: {metadata_path}")
        return {"error": "Metadata file not found"}

    metadata = read_output_file(metadata_path)
    if not isinstance(metadata, list):
        logging.error(f"Unexpected metadata structure in {metadata_path}")
        return {"error": "Invalid metadata structure"}

    # Extract file names for Figures/Tables
    figure_urls = [
        os.path.basename(fig.get('renderURL'))
        for fig in metadata
        if fig.get('figType') == 'Figure'
    ]
    table_urls = [
        os.path.basename(fig.get('renderURL'))
        for fig in metadata
        if fig.get('figType') == 'Table'
    ]
    doc_name = filename or os.path.splitext(os.path.basename(metadata_path))[0]
    pages = len({fig.get('page', 0) for fig in metadata})

    return {
        "document": doc_name,
        "n_figures": len(figure_urls),
        "n_tables": len(table_urls),
        "pages": pages,
        "time_in_millis": processing_time or 0,
        "metadata_filename": f"{doc_name}.json",
        "figures": figure_urls,
        "tables": table_urls
    }

def parse_stat_file(output_dir):
    """Parse stat_file.json in batch mode, but reuse parse_json_metadata for each entry. - generated for folder processing"""
    stat_file_path = os.path.join(output_dir, 'stat_file.json')
    if not os.path.exists(stat_file_path):
        return []

    with open(stat_file_path, 'r') as stat_file:
        stats = json.load(stat_file)

    result = []
    for stat in stats:
        # Derive metadata filename
        base_name = os.path.splitext(os.path.basename(stat.get('filename', '')))[0]
        metadata_filename = f"{base_name}.json"
        metadata_path = os.path.join(output_dir, metadata_filename)
        time_in_millis = stat.get('timeInMillis', 0)

        parsed = parse_json_metadata(metadata_path, time_in_millis, base_name)
        # Merge any extra info from stat if needed
        if isinstance(parsed, dict) and "error" not in parsed:
            # Overwrite or append to parsed if desired
            parsed["document"] = stat.get('document', parsed["document"])
            result.append(parsed)
        else:
            result.append({"error": f"Failed to parse metadata for {base_name}"})

    return result

def run_pdffigures2(file_path, output_dir):
    java_opts = os.getenv('JAVA_OPTS', '-Xmx12g')
    file_path = os.path.abspath(file_path)
    abs_output = os.path.abspath(output_dir)
    abs_output = abs_output if abs_output.endswith('/') else abs_output + '/'   
    start_time = time.time()
    logging.debug(f"Running pdffigures2 on {file_path}")
    base_command = [
        'java', java_opts, '-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider', '-jar', '/pdffigures2/pdffigures2.jar',
        file_path,
        "-m", output_dir,
        "-d", output_dir,
        "--dpi", "300"
    ]
    result = subprocess.run(base_command, capture_output=True, text=True, cwd="/pdffigures2")
    if result.returncode != 0:
        logging.error(f"Command failed with exit code {result.returncode}")
        logging.error(f"STDOUT: {result.stdout}")
        logging.error(f"STDERR: {result.stderr}")
        return {"error": result.stderr}, 500

    # Build result by parsing JSON metadata (similar to parse_stat_file logic)
    end_time = time.time()
    processing_time = int((end_time - start_time) * 1000)
    logging.debug(f"Processing time: {processing_time} ms")
    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    metadata_filename = f"{base_filename}.json"
    metadata_path = os.path.join(output_dir, metadata_filename)
    logging.debug(f"Metadata file: {metadata_path}")

    return parse_json_metadata(metadata_path, processing_time, base_filename)

def run_pdffigures2_batch(folder_path, output_dir):
    """
    Run pdffigures2 batch processing on a directory of PDFs
    """
    # Ensure absolute paths
    abs_folder = os.path.abspath(folder_path)
    input_dir = abs_folder if abs_folder.endswith('/') else abs_folder + '/'
    abs_output = os.path.abspath(output_dir)
    abs_output = abs_output if abs_output.endswith('/') else abs_output + '/'
    stat_file = os.path.join(abs_output, 'stat_file.json')

    java_opts = os.getenv('JAVA_OPTS', '-Xmx12g')
    
    # Build command with separate arguments
    base_command = [
        'java', java_opts, '-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider', '-jar', '/pdffigures2/pdffigures2.jar',
        input_dir,
        '-s', stat_file,
        '-m', abs_output,
        '-d', abs_output,
        '--dpi', '300'
    ]
    
    try:
        logging.debug(f"Running command: {' '.join(base_command)}")
        start_time = time.time()
        
        result = subprocess.run(
            base_command,
            capture_output=True,
            text=True,
            cwd="/pdffigures2",  
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        num_files_processed = len([name for name in os.listdir(input_dir) if name.endswith('.pdf')])
        logging.info(f"Processing time: {processing_time:.2f} seconds")
        logging.info(f"Number of files processed: {num_files_processed}")
        # average page parsing time per document & per page
        if num_files_processed > 0:
            logging.info(f"Average page parsing time per document: {processing_time / num_files_processed:.2f} seconds")
        
        if result.returncode != 0:
            logging.error(f"Command failed with exit code {result.returncode}")
            logging.error(f"STDOUT: {result.stdout}")
            logging.error(f"STDERR: {result.stderr}")
            return {"error": result.stderr}, 500
        
        logging.debug(f"Command output: {result}, {result.stdout}")

        # return values from stats file
        result = parse_stat_file(abs_output)
        return result
        
    except Exception as e:
        logging.error(f"Failed to run pdffigures2: {str(e)}")
        raise e

def count_figures_and_tables(figures):
    render_urls = {fig.get('renderURL') for fig in figures if fig.get('figType') == 'Table'}
    num_tables = len(render_urls)
    num_figures = sum(1 for fig in figures if fig.get('figType') == 'Figure')
    return num_tables, num_figures