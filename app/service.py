# Service layer for running pdffigures2 and parsing output
import subprocess
import os
import logging
import time
import json
from .utils import read_output_file
from figure_metadata import parse_json_metadata_from_dict

# Centralized configuration for pdffigures2
PDF_FIGURES2_JAR = os.getenv('PDFFIGURES2_JAR', '/pdffigures2/pdffigures2.jar')
PDF_FIGURES2_CWD = os.getenv('PDF_FIGURES2_CWD', '/pdffigures2')
DEFAULT_DPI = os.getenv('PDFFIGURES2_DPI', '300')
JAVA_OPTS = os.getenv('JAVA_OPTS', '-Xmx12g')


def _build_pdffigures2_command(
    input_path: str,
    output_dir: str,
    stat_file: str | None = None,
    batch: bool = False,
) -> list[str]:
    """Build the pdffigures2 command for single-file or batch processing."""
    input_path = os.path.abspath(input_path)
    output_dir = os.path.abspath(output_dir)

    cmd: list[str] = [
        'java',
        JAVA_OPTS,
        '-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider',
        '-jar', PDF_FIGURES2_JAR,
        input_path,
    ]

    # Batch mode uses a stat file and directory input
    if batch and stat_file is not None:
        cmd.extend([
            '-s', os.path.abspath(stat_file),
            '-m', output_dir,
            '-d', output_dir,
            '--dpi', DEFAULT_DPI,
        ])
    else:
        # Single-file mode
        cmd.extend([
            '-m', output_dir,
            '-d', output_dir,
            '--dpi', DEFAULT_DPI,
        ])

    return cmd


def parse_json_metadata(metadata_path, processing_time=None, filename=None):
    """Parse JSON metadata file and return structured result.

    This function now delegates the core parsing to the shared
    figure_metadata.parse_json_metadata_from_dict helper, but retains the
    previous diagnostics and return structure.
    """
    if not os.path.exists(metadata_path):
        logging.error(f"Metadata file not found: {metadata_path}")
        # Extra diagnostics: list JSON files in the same directory
        parent_dir = os.path.dirname(metadata_path)
        try:
            if os.path.isdir(parent_dir):
                json_files = [f for f in os.listdir(parent_dir) if f.lower().endswith('.json')]
                logging.error(f"Existing JSON files in {parent_dir}: {json_files}")
            else:
                logging.error(f"Parent directory does not exist: {parent_dir}")
        except Exception as diag_err:
            logging.error(f"Failed to list JSON files in {parent_dir}: {diag_err}")
        return {"error": "Metadata file not found"}

    metadata = read_output_file(metadata_path)
    if not isinstance(metadata, list):
        logging.error(f"Unexpected metadata structure in {metadata_path}")
        return {"error": "Invalid metadata structure"}

    doc_name = filename or os.path.splitext(os.path.basename(metadata_path))[0]
    return parse_json_metadata_from_dict(
        metadata,
        processing_time=processing_time or 0,
        filename=doc_name,
    )


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
    """Run pdffigures2 on a single PDF and return parsed metadata.

    This function is a pure service function: it raises on failure and
    always returns a dictionary on success.
    """
    abs_output = os.path.abspath(output_dir)
    abs_output = abs_output if abs_output.endswith('/') else abs_output + '/'

    logging.debug(f"run_pdffigures2 called with file_path={file_path}, output_dir={output_dir}")
    logging.debug(f"Resolved abs_output={abs_output}")

    command = _build_pdffigures2_command(file_path, abs_output, batch=False)
    logging.debug(f"pdffigures2 command: {' '.join(command)} (cwd={PDF_FIGURES2_CWD})")

    start_time = time.time()
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=PDF_FIGURES2_CWD,
    )
    end_time = time.time()

    if result.returncode != 0:
        logging.error(f"pdffigures2 failed with exit code {result.returncode}")
        logging.error(f"STDOUT: {result.stdout}")
        logging.error(f"STDERR: {result.stderr}")
        raise RuntimeError(f"pdffigures2 failed: {result.stderr}")

    processing_time_ms = int((end_time - start_time) * 1000)
    logging.debug(f"Processing time: {processing_time_ms} ms")

    base_filename = os.path.splitext(os.path.basename(file_path))[0]
    metadata_filename = f"{base_filename}.json"
    metadata_path = os.path.join(abs_output, metadata_filename)
    logging.debug(f"Expected metadata file: {metadata_path}")

    # Extra diagnostics: list files in output directory after run
    try:
        if os.path.isdir(abs_output):
            files_after = os.listdir(abs_output)
            logging.debug(f"Files in output directory {abs_output}: {files_after}")
        else:
            logging.error(f"Output directory does not exist after run: {abs_output}")
    except Exception as diag_err:
        logging.error(f"Failed to list files in output directory {abs_output}: {diag_err}")

    return parse_json_metadata(metadata_path, processing_time_ms, base_filename)


def run_pdffigures2_batch(folder_path, output_dir):
    """Run pdffigures2 batch processing on a directory of PDFs.

    Returns a list of per-document summaries parsed from the stat file.
    Raises an exception on failure.
    """
    abs_folder = os.path.abspath(folder_path)
    input_dir = abs_folder if abs_folder.endswith('/') else abs_folder + '/'
    abs_output = os.path.abspath(output_dir)
    abs_output = abs_output if abs_output.endswith('/') else abs_output + '/'
    stat_file = os.path.join(abs_output, 'stat_file.json')

    command = _build_pdffigures2_command(input_dir, abs_output, stat_file=stat_file, batch=True)

    try:
        logging.debug(f"Running pdffigures2 batch command: {' '.join(command)}")
        start_time = time.time()
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=PDF_FIGURES2_CWD,
        )
        end_time = time.time()

        processing_time = end_time - start_time
        num_files_processed = len([name for name in os.listdir(input_dir) if name.endswith('.pdf')])
        logging.info(f"Batch processing time: {processing_time:.2f} seconds")
        logging.info(f"Number of files processed: {num_files_processed}")
        if num_files_processed > 0:
            logging.info(
                f"Average page parsing time per document: {processing_time / num_files_processed:.2f} seconds"
            )

        if result.returncode != 0:
            logging.error(f"pdffigures2 batch failed with exit code {result.returncode}")
            logging.error(f"STDOUT: {result.stdout}")
            logging.error(f"STDERR: {result.stderr}")
            raise RuntimeError(f"pdffigures2 batch failed: {result.stderr}")

        logging.debug(f"pdffigures2 batch output: {result.stdout}")

        # Build per-document summaries from the stat file
        return parse_stat_file(abs_output)

    except Exception as e:
        logging.error(f"Failed to run pdffigures2 batch: {e}")
        raise


def count_figures_and_tables(figures):
    render_urls = {fig.get('renderURL') for fig in figures if fig.get('figType') == 'Table'}
    num_tables = len(render_urls)
    num_figures = sum(1 for fig in figures if fig.get('figType') == 'Figure')
    return num_tables, num_figures