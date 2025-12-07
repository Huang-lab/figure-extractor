# Service layer for running pdffigures2 and parsing output
import subprocess
import os
import logging
import time
import json
from pathlib import Path
from .utils import read_output_file
from figure_metadata import parse_json_metadata_from_dict

# Centralized configuration for pdffigures2
PDF_FIGURES2_JAR = os.getenv('PDFFIGURES2_JAR', '/pdffigures2/pdffigures2.jar')
PDF_FIGURES2_CWD = os.getenv('PDF_FIGURES2_CWD', '/pdffigures2')
DEFAULT_DPI = os.getenv('PDFFIGURES2_DPI', '300')
JAVA_OPTS = os.getenv('JAVA_OPTS', '-Xmx12g')
PDFFIGURES2_TIMEOUT = int(os.getenv('PDFFIGURES2_TIMEOUT_SECONDS', '300'))


def _build_pdffigures2_command(
    input_path: str | Path,
    output_dir: str | Path,
    stat_file: str | Path | None = None,
    batch: bool = False,
) -> list[str]:
    """Build the pdffigures2 command for single-file or batch processing.
    
    Args:
        input_path: Path to input PDF file or directory
        output_dir: Directory where output files will be saved
        stat_file: Optional path to stat file for batch processing
        batch: Whether this is batch processing mode
        
    Returns:
        List of command arguments for subprocess
        
    Note:
        pdffigures2 requires directory paths to end with '/' otherwise it treats
        them as filename prefixes, causing files like 'outputfilename.png' instead
        of 'output/filename.png'
    """
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()
    
    # CRITICAL: pdffigures2 requires trailing slash for directories
    # Without it, pdffigures2 treats the path as a filename prefix
    output_dir_str = str(output_dir) + '/'

    cmd: list[str] = [
        'java',
        JAVA_OPTS,
        '-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider',
        '-jar', PDF_FIGURES2_JAR,
        str(input_path),
    ]

    # Batch mode uses a stat file and directory input
    if batch and stat_file is not None:
        stat_file = Path(stat_file).resolve()
        cmd.extend([
            '-s', str(stat_file),
            '-m', output_dir_str,
            '-d', output_dir_str,
            '--dpi', DEFAULT_DPI,
        ])
    else:
        # Single-file mode
        cmd.extend([
            '-m', output_dir_str,
            '-d', output_dir_str,
            '--dpi', DEFAULT_DPI,
        ])

    return cmd


def _normalize_document_summary(summary: dict) -> dict:
    """Ensure a consistent schema for per-document summaries.

    This keeps the service layer stable for both single and batch
    operations, regardless of how the underlying metadata parser evolves.
    """
    if summary is None:
        summary = {}

    # Prefer canonical key names but fall back to older variants
    n_figures = summary.get("n_figures", summary.get("num_figures", 0))
    n_tables = summary.get("n_tables", summary.get("num_tables", 0))

    return {
        "document": summary.get("document"),
        "pages": summary.get("pages", 0),
        "n_figures": n_figures,
        "n_tables": n_tables,
        "metadata_filename": summary.get("metadata_filename"),
        "figures": summary.get("figures", []),
        "tables": summary.get("tables", []),
        "time_in_millis": summary.get("time_in_millis", 0),
    }


def parse_json_metadata(metadata_path: str | Path, processing_time=None, filename=None):
    """Parse JSON metadata file and return structured result.

    This function now delegates the core parsing to the shared
    figure_metadata.parse_json_metadata_from_dict helper, but retains the
    previous diagnostics and return structure.
    
    Args:
        metadata_path: Path to the JSON metadata file
        processing_time: Optional processing time in milliseconds
        filename: Optional filename override
        
    Returns:
        Dictionary with parsed metadata or error information
    """
    metadata_path = Path(metadata_path)
    
    if not metadata_path.exists():
        logging.error(f"Metadata file not found: {metadata_path}")
        # Extra diagnostics: list JSON files in the same directory
        parent_dir = metadata_path.parent
        try:
            if parent_dir.is_dir():
                json_files = [f.name for f in parent_dir.glob('*.json')]
                logging.error(f"Existing JSON files in {parent_dir}: {json_files}")
            else:
                logging.error(f"Parent directory does not exist: {parent_dir}")
        except Exception as diag_err:
            logging.error(f"Failed to list JSON files in {parent_dir}: {diag_err}")
        return {"error": "Metadata file not found"}

    metadata = read_output_file(str(metadata_path))
    if not isinstance(metadata, list):
        logging.error(f"Unexpected metadata format in {metadata_path}: expected list, got {type(metadata)}")
        return {"error": "Invalid metadata format"}

    try:
        parsed = parse_json_metadata_from_dict(metadata)
    except Exception as e:
        logging.error(f"Failed to parse metadata using shared helper: {e}")
        return {"error": "Failed to parse metadata"}

    # Attach additional fields for compatibility and richer summaries
    parsed["time_in_millis"] = processing_time if processing_time is not None else parsed.get("time_in_millis", 0)
    parsed["document"] = filename if filename is not None else parsed.get("document")
    parsed["metadata_filename"] = metadata_path.name

    # Normalize before returning so callers always see the same shape
    return _normalize_document_summary(parsed)


def parse_stat_file(output_dir: str | Path):
    """Parse stat_file.json in batch mode, but reuse parse_json_metadata for each entry.
    
    Args:
        output_dir: Directory containing the stat_file.json
        
    Returns:
        List of parsed document summaries
    """
    output_dir = Path(output_dir)
    stat_file_path = output_dir / 'stat_file.json'
    
    if not stat_file_path.exists():
        return []

    with open(stat_file_path, 'r') as stat_file:
        stats = json.load(stat_file)

    result = []
    for stat in stats:
        # Derive metadata filename
        filename = stat.get('filename', '')
        base_name = Path(filename).stem
        metadata_filename = f"{base_name}.json"
        metadata_path = output_dir / metadata_filename
        time_in_millis = stat.get('timeInMillis', 0)

        parsed = parse_json_metadata(metadata_path, time_in_millis, base_name)
        # Merge any extra info from stat if needed
        if isinstance(parsed, dict) and "error" not in parsed:
            # Overwrite or append to parsed if desired
            parsed["document"] = stat.get('document', parsed.get("document"))
            # Ensure the schema is normalized even after merging
            result.append(_normalize_document_summary(parsed))
        else:
            logging.error(f"Failed to parse metadata for {base_name}: {parsed}")

    return result


def run_pdffigures2(file_path: str | Path, output_dir: str | Path):
    """Run pdffigures2 on a single PDF and return parsed metadata.

    This function is a pure service function: it raises on failure and
    always returns a dictionary on success.
    
    Args:
        file_path: Path to the PDF file to process
        output_dir: Directory where output files will be saved
        
    Returns:
        Dictionary containing parsed metadata and processing information
        
    Raises:
        RuntimeError: If pdffigures2 fails or times out
    """
    file_path = Path(file_path)
    output_dir = Path(output_dir).resolve()

    logging.debug(f"run_pdffigures2 called with file_path={file_path}, output_dir={output_dir}")

    command = _build_pdffigures2_command(file_path, output_dir, batch=False)
    logging.debug(f"pdffigures2 command: {' '.join(command)} (cwd={PDF_FIGURES2_CWD})")

    start_time = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=PDF_FIGURES2_CWD,
            timeout=PDFFIGURES2_TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        logging.error(
            f"pdffigures2 timed out after {PDFFIGURES2_TIMEOUT} seconds for file {file_path}: {e}"
        )
        raise RuntimeError(
            f"pdffigures2 timed out after {PDFFIGURES2_TIMEOUT} seconds for file {file_path.name}"
        ) from e

    end_time = time.time()

    if result.returncode != 0:
        logging.error(f"pdffigures2 failed with exit code {result.returncode}")
        logging.error(f"STDOUT: {result.stdout}")
        logging.error(f"STDERR: {result.stderr}")
        raise RuntimeError(f"pdffigures2 failed: {result.stderr}")

    processing_time_ms = int((end_time - start_time) * 1000)
    logging.debug(f"Processing time: {processing_time_ms} ms")

    base_filename = file_path.stem
    metadata_filename = f"{base_filename}.json"
    metadata_path = output_dir / metadata_filename
    logging.debug(f"Expected metadata file: {metadata_path}")

    # Extra diagnostics: list files in output directory after run
    try:
        if output_dir.is_dir():
            files_after = [f.name for f in output_dir.iterdir()]
            logging.debug(f"Files in output directory {output_dir}: {files_after}")
        else:
            logging.error(f"Output directory does not exist after run: {output_dir}")
    except Exception as diag_err:
        logging.error(f"Failed to list files in output directory {output_dir}: {diag_err}")

    # Delegate JSON parsing and summary creation, which also normalizes the schema
    return parse_json_metadata(metadata_path, processing_time_ms, base_filename)


def run_pdffigures2_batch(folder_path: str | Path, output_dir: str | Path):
    """Run pdffigures2 batch processing on a directory of PDFs.

    Returns a list of per-document summaries parsed from the stat file.
    
    Args:
        folder_path: Path to directory containing PDF files
        output_dir: Directory where output files will be saved
        
    Returns:
        List of dictionaries containing parsed metadata for each document
        
    Raises:
        RuntimeError: If pdffigures2 batch processing fails or times out
    """
    folder_path = Path(folder_path).resolve()
    output_dir = Path(output_dir).resolve()
    
    # For batch mode, pdffigures2 expects input directory to end with /
    input_dir = str(folder_path) + '/'
    stat_file = output_dir / 'stat_file.json'

    command = _build_pdffigures2_command(input_dir, output_dir, stat_file=stat_file, batch=True)

    try:
        logging.debug(f"Running pdffigures2 batch command: {' '.join(command)}")
        start_time = time.time()
        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=PDF_FIGURES2_CWD,
                timeout=PDFFIGURES2_TIMEOUT,
            )
        except subprocess.TimeoutExpired as e:
            logging.error(
                f"pdffigures2 batch timed out after {PDFFIGURES2_TIMEOUT} seconds for folder {folder_path}: {e}"
            )
            raise RuntimeError(
                f"pdffigures2 batch timed out after {PDFFIGURES2_TIMEOUT} seconds for folder {folder_path}"
            ) from e

        end_time = time.time()

        processing_time = end_time - start_time
        num_files_processed = len(list(folder_path.glob('*.pdf')))
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

        # Build per-document summaries from the stat file and normalize them
        summaries = parse_stat_file(output_dir)
        return [
            _normalize_document_summary(summary) for summary in summaries if isinstance(summary, dict)
        ]

    except Exception as e:
        logging.error(f"Failed to run pdffigures2 batch: {e}")
        raise


def count_figures_and_tables(figures):
    render_urls = {fig.get('renderURL') for fig in figures if fig.get('figType') == 'Table'}
    num_tables = len(render_urls)
    num_figures = sum(1 for fig in figures if fig.get('figType') == 'Figure')
    return num_tables, num_figures