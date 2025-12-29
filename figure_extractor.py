import argparse
import os
import requests
import tempfile
import zipfile
import json
import logging
from pathlib import Path
from urllib.parse import urljoin
from typing import List, Dict, Any, Optional

# Try to import core modules for local mode
try:
    from core.extractor import run_pdffigures2, run_pdffigures2_batch
    from core.metadata import get_figure_metadata
    CORE_AVAILABLE = True
except ImportError:
    CORE_AVAILABLE = False

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_API_URL = "http://localhost:5001"

class RemoteExtractor:
    def __init__(self, base_url: str = DEFAULT_API_URL):
        self.base_url = base_url.rstrip('/')

    def extract_file(self, file_path: str, output_dir: str) -> Dict[str, Any]:
        url = f"{self.base_url}/extract"
        logger.info(f"Sending {file_path} to {url}")
        
        with open(file_path, 'rb') as f:
            files = {'file': f}
            response = requests.post(url, files=files)
        
        response.raise_for_status()
        data = response.json()
        
        if not data.get('success'):
            raise RuntimeError(f"API Error: {data.get('error', {}).get('message', 'Unknown error')}")
        
        extraction_data = data['data']
        self._download_results(extraction_data, output_dir)
        return extraction_data

    def extract_batch(self, folder_path: str, output_dir: str) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/extract_batch"
        logger.info(f"Sending batch from {folder_path} to {url}")
        
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        try:
            with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, _, files in os.walk(folder_path):
                    for file in files:
                        if file.lower().endswith('.pdf'):
                            zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))
            
            with open(temp_zip.name, 'rb') as f:
                files = {'folder': ('batch.zip', f, 'application/zip')}
                response = requests.post(url, files=files)
            
            response.raise_for_status()
            data = response.json()
            
            if not data.get('success'):
                raise RuntimeError(f"API Error: {data.get('error', {}).get('message', 'Unknown error')}")
            
            documents = data['data']
            for doc in documents:
                self._download_results(doc, output_dir)
            return documents
        finally:
            if os.path.exists(temp_zip.name):
                os.unlink(temp_zip.name)

    def _download_results(self, doc_data: Dict[str, Any], output_dir: str):
        os.makedirs(output_dir, exist_ok=True)
        
        # Download metadata
        metadata_filename = doc_data['metadata_filename']
        self._download_file(f"download/{metadata_filename}", os.path.join(output_dir, metadata_filename))
        
        # Download figures and tables
        for fig in doc_data.get('figures', []):
            filename = os.path.basename(fig['renderURL']) if isinstance(fig, dict) else os.path.basename(fig)
            self._download_file(f"download/{filename}", os.path.join(output_dir, filename))
            
        for tab in doc_data.get('tables', []):
            filename = os.path.basename(tab['renderURL']) if isinstance(tab, dict) else os.path.basename(tab)
            self._download_file(f"download/{filename}", os.path.join(output_dir, filename))

    def _download_file(self, path: str, output_path: str):
        url = urljoin(self.base_url + '/', path)
        response = requests.get(url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

def main():
    parser = argparse.ArgumentParser(description="Extract figures and tables from PDF documents.")
    parser.add_argument('input', help="Path to PDF file or directory.")
    parser.add_argument('--output-dir', default='output', help="Output directory.")
    parser.add_argument('--url', default=DEFAULT_API_URL, help="API URL (default: http://localhost:5001).")
    parser.add_argument('--local', action='store_true', help="Run locally without API (requires pdffigures2.jar).")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    
    try:
        if args.local:
            if not CORE_AVAILABLE:
                print("❌ Local mode modules not found. Run 'python setup_local.py' first.")
                return
            
            if input_path.is_file():
                result = run_pdffigures2(input_path, output_dir)
                print(json.dumps(result, indent=2))
            elif input_path.is_dir():
                results = run_pdffigures2_batch(input_path, output_dir)
                print(json.dumps(results, indent=2))
            else:
                print(f"❌ Input path {input_path} not found.")
        else:
            extractor = RemoteExtractor(args.url)
            if input_path.is_file():
                result = extractor.extract_file(str(input_path), str(output_dir))
                print(json.dumps(result, indent=2))
            elif input_path.is_dir():
                results = extractor.extract_batch(str(input_path), str(output_dir))
                print(json.dumps(results, indent=2))
            else:
                print(f"❌ Input path {input_path} not found.")
                
    except Exception as e:
        logger.error(f"Extraction failed: {e}")
        if not args.local:
            logger.info("Try running with --local if you have pdffigures2 installed locally.")

if __name__ == "__main__":
    main()
