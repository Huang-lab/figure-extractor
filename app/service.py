# Service layer for running pdffigures2 and parsing output
import logging
from pathlib import Path
from typing import List, Dict, Any, Union
from core.extractor import run_pdffigures2 as core_run_pdffigures2
from core.extractor import run_pdffigures2_batch as core_run_pdffigures2_batch

logger = logging.getLogger(__name__)

def run_pdffigures2(file_path: Union[str, Path], output_dir: Union[str, Path]) -> Dict[str, Any]:
    """Run pdffigures2 on a single PDF and return parsed metadata."""
    return core_run_pdffigures2(file_path, output_dir)

def run_pdffigures2_batch(folder_path: Union[str, Path], output_dir: Union[str, Path]) -> List[Dict[str, Any]]:
    """Run pdffigures2 batch processing on a directory of PDFs."""
    return core_run_pdffigures2_batch(folder_path, output_dir)

def count_figures_and_tables(figures: List[Dict[str, Any]]):
    """Count unique tables and figures based on renderURL and figType."""
    render_urls = {fig.get('renderURL') for fig in figures if fig.get('figType') == 'Table'}
    num_tables = len(render_urls)
    num_figures = sum(1 for fig in figures if fig.get('figType') == 'Figure')
    return num_tables, num_figures
