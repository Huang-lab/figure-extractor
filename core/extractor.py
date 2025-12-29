import subprocess
import os
import logging
import time
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union
from .config import PDF_FIGURES2_JAR, PDF_FIGURES2_CWD, DEFAULT_DPI, JAVA_OPTS, PDFFIGURES2_TIMEOUT
from .metadata import parse_json_metadata_from_dict

logger = logging.getLogger(__name__)

def _build_pdffigures2_command(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    stat_file: Optional[Union[str, Path]] = None,
    batch: bool = False,
) -> List[str]:
    """Build the pdffigures2 command for single-file or batch processing."""
    input_path = Path(input_path).resolve()
    output_dir = Path(output_dir).resolve()
    
    # CRITICAL: pdffigures2 requires trailing slash for directories
    output_dir_str = str(output_dir) + os.sep

    cmd: List[str] = [
        'java',
        JAVA_OPTS,
        '-Dsun.java2d.cmm=sun.java2d.cmm.kcms.KcmsServiceProvider',
        '-jar', PDF_FIGURES2_JAR,
        str(input_path),
    ]

    if batch and stat_file is not None:
        stat_file = Path(stat_file).resolve()
        cmd.extend([
            '-s', str(stat_file),
            '-m', output_dir_str,
            '-d', output_dir_str,
            '--dpi', DEFAULT_DPI,
        ])
    else:
        cmd.extend([
            '-m', output_dir_str,
            '-d', output_dir_str,
            '--dpi', DEFAULT_DPI,
        ])

    return cmd

def run_pdffigures2(file_path: Union[str, Path], output_dir: Union[str, Path]) -> Dict[str, Any]:
    """Run pdffigures2 on a single PDF and return parsed metadata."""
    file_path = Path(file_path)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    command = _build_pdffigures2_command(file_path, output_dir, batch=False)
    logger.debug(f"Running pdffigures2: {' '.join(command)}")

    start_time = time.time()
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=PDF_FIGURES2_CWD if os.path.exists(PDF_FIGURES2_CWD) else None,
            timeout=PDFFIGURES2_TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        logger.error(f"pdffigures2 timed out for {file_path}")
        raise RuntimeError(f"pdffigures2 timed out for {file_path.name}") from e

    end_time = time.time()

    if result.returncode != 0:
        logger.error(f"pdffigures2 failed: {result.stderr}")
        raise RuntimeError(f"pdffigures2 failed: {result.stderr}")

    processing_time_ms = int((end_time - start_time) * 1000)
    
    base_filename = file_path.stem
    metadata_path = output_dir / f"{base_filename}.json"

    if not metadata_path.exists():
        logger.error(f"Metadata file not found: {metadata_path}")
        return {"error": "Metadata file not found"}

    with open(metadata_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)

    parsed = parse_json_metadata_from_dict(metadata, processing_time=processing_time_ms, filename=base_filename)
    parsed["metadata_filename"] = metadata_path.name
    
    return parsed

def run_pdffigures2_batch(folder_path: Union[str, Path], output_dir: Union[str, Path]) -> List[Dict[str, Any]]:
    """Run pdffigures2 batch processing on a directory of PDFs."""
    folder_path = Path(folder_path).resolve()
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    stat_file = output_dir / 'stat_file.json'
    # For batch mode, pdffigures2 expects input directory to end with /
    input_dir_str = str(folder_path) + os.sep

    command = _build_pdffigures2_command(input_dir_str, output_dir, stat_file=stat_file, batch=True)

    try:
        logger.debug(f"Running pdffigures2 batch: {' '.join(command)}")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            cwd=PDF_FIGURES2_CWD if os.path.exists(PDF_FIGURES2_CWD) else None,
            timeout=PDFFIGURES2_TIMEOUT,
        )

        if result.returncode != 0:
            logger.error(f"pdffigures2 batch failed: {result.stderr}")
            raise RuntimeError(f"pdffigures2 batch failed: {result.stderr}")

        if not stat_file.exists():
            return []

        with open(stat_file, 'r', encoding='utf-8') as f:
            stats = json.load(f)

        summaries = []
        for stat in stats:
            filename = stat.get('filename', '')
            base_name = Path(filename).stem
            metadata_path = output_dir / f"{base_name}.json"
            
            if metadata_path.exists():
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                parsed = parse_json_metadata_from_dict(
                    metadata, 
                    processing_time=stat.get('timeInMillis', 0), 
                    filename=base_name
                )
                parsed["metadata_filename"] = metadata_path.name
                summaries.append(parsed)
        
        return summaries

    except Exception as e:
        logger.error(f"Failed to run pdffigures2 batch: {e}")
        raise
