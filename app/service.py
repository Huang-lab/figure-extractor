import subprocess
import os
import logging
import time

def run_pdffigures2(file_path, output_dir):
    base_command = [
        'java', '-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider', '-jar', '/pdffigures2/pdffigures2.jar',
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
    
    # Build command with separate arguments
    base_command = [
        'java', '-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider', '-jar', '/pdffigures2/pdffigures2.jar',
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
        
        logging.debug(f"Command output: {result}, {result.stdout}")
        return result
        
    except Exception as e:
        logging.error(f"Failed to run pdffigures2: {str(e)}")
        raise e

def count_figures_and_tables(figures):
    render_urls = {fig.get('renderURL') for fig in figures if fig.get('figType') == 'Table'}
    num_tables = len(render_urls)
    num_figures = sum(1 for fig in figures if fig.get('figType') == 'Figure')
    return num_tables, num_figures