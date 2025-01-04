import subprocess
import os
import logging
import time
import json
from .utils import read_output_file

def parse_stat_file(output_dir):
    stat_file_path = os.path.join(output_dir, 'stat_file.json')
    if os.path.exists(stat_file_path):
        with open(stat_file_path, 'r') as stat_file:
            stats = json.load(stat_file)
            logging.debug(f"Stats: {stats}")
            result = []
            for stat in stats:  # Iterate over the list of dictionaries
                logging.debug(f"Stat: {stat}")
                metadata_filename = os.path.splitext(os.path.basename(stat.get('filename', '')))[0] + '.json'
                logging.debug(f"Metadata filename: {metadata_filename}")
                metadata_path = os.path.join(output_dir, metadata_filename)
                logging.debug(f"Metadata path: {metadata_path}")
                if os.path.exists(metadata_path):
                    logging.debug(f"Metadata file exists: {metadata_path}")
                    metadata = read_output_file(metadata_path)
                    if isinstance(metadata, list):  
                        # Extract file names for Figures
                        figure_urls = [
                            os.path.basename(fig.get('renderURL')) 
                            for fig in metadata 
                            if fig.get('figType') == 'Figure'
                        ]                
                        # Extract file names for Tables
                        table_urls = [
                            os.path.basename(fig.get('renderURL')) 
                            for fig in metadata 
                            if fig.get('figType') == 'Table'
                        ]
                        # Debug log extracted URLs
                        logging.debug(f"Figure URLs: {figure_urls}")
                        logging.debug(f"Table URLs: {table_urls}")
                    else:
                        logging.error(f"Unexpected metadata structure: {type(metadata)}")
                        figure_urls = []
                        table_urls = []


                num_figures = stat.get('numFigures', 0)
                num_tables = stat.get('numPages', 0)  
                logging.debug(f"Figures: {num_figures}, Tables: {num_tables}")  
                logging.debug(f"Metadata: {metadata_filename}, Figures: {figure_urls}, Tables: {table_urls}")
                logging.debug(f"Time in millis: {stat.get('timeInMillis', 0)}")
                result.append({
                    "document": os.path.splitext(os.path.basename(stat.get('filename', '')))[0],
                    "n_figures": len(figure_urls),
                    "n_tables": len(table_urls),
                    "pages": stat.get('numPages', 0),
                    "time_in_millis": stat.get('timeInMillis', 0),
                    "metadata_filename": os.path.splitext(os.path.basename(stat.get('filename', '')))[0] + '.json',
                    "figures": figure_urls,
                    "tables": table_urls
                })
            return result

def run_pdffigures2(file_path, output_dir):
    java_opts = os.getenv('JAVA_OPTS', '-Xmx12g')
    base_command = [
        'java', java_opts, '-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider', '-jar', '/pdffigures2/pdffigures2.jar',
        file_path,
        "-m", output_dir,
        "-d", output_dir,
        "--dpi", "300"
    ]
    result = subprocess.run(base_command, capture_output=True, text=True)
    return result

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
            cwd="/pdffigures2",  # Run from pdffigures2 directory
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