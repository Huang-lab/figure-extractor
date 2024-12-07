import argparse
import os
import requests
import shutil
import tempfile
import zipfile
import json

import logging  
logging.basicConfig(level=logging.DEBUG)

def download_file(download_url, output_path):
    """
    Download a file from the server.

    :param download_url: URL of the download service.
    :param output_path: Path to save the downloaded file.
    """
    try:
        response = requests.get(download_url, stream=True)
        response.raise_for_status()
        with open(output_path, 'wb') as file:
            for chunk in response.iter_content(chunk_size=8192):
                file.write(chunk)
        print(f"File downloaded: {output_path}")
    except requests.RequestException as e:
        print(f"Error downloading file: {str(e)}")
        raise

def extract_pdf(file_path, url):
    """
    Extract figures and tables from a PDF file by sending it to the server.

    :param file_path: Path to the PDF file to be extracted.
    :param url: URL of the extraction service.
    :return: Response from the server.
    """
    try:
        with open(file_path, 'rb') as file:
            files = {'file': file}
            response = requests.post(url, files=files)
        response.raise_for_status()
        return response
    except requests.RequestException as e:
        print(f"Error extracting PDF: {str(e)}")
        raise

def extract_file(file_path, output_dir, url):
    response = extract_pdf(file_path, url)
    if response.status_code == 200:
        response_data = response.json()
        metadata_filename = response_data['metadata_file']
        metadata_download_url = f"http://localhost:5001/download/{metadata_filename}"
        metadata_output_path = os.path.join(output_dir, metadata_filename)
        download_file(metadata_download_url, metadata_output_path)

        figures = response_data.get('figures', [])
        for figure_url in figures:
            figure_filename = os.path.basename(figure_url)
            figure_download_url = f"http://localhost:5001/download/{figure_filename}"
            download_file(figure_download_url, os.path.join(output_dir, figure_filename))
    else:
        print(f"Error: {response.status_code}")
        print(response.text)

def zip_directory(folder_path):
    logging.debug(f"Zipping directory: {folder_path}")
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, _, files in os.walk(folder_path):
            for file in files:
                zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))
    logging.debug(f"Created zip file: {temp_zip.name}")
    return temp_zip.name

def extract_batch(folder_path, output_dir, url):
    """
    Extract figures from PDF files in a directory using a remote server.
    
    Args:
        folder_path (str): Path to directory containing PDF files
        output_dir (str): Directory to save extracted figures
        url (str): URL of the extraction service
    """
    try:
        # Create a temporary zip file
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        # Add only PDF files to the zip
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        file_path = os.path.join(root, file)
                        # Preserve the relative path structure
                        arc_name = os.path.relpath(file_path, folder_path)
                        logging.debug(f"Adding {arc_name} to zip")
                        zipf.write(file_path, arc_name)
        
        logging.debug(f"Created zip file: {temp_zip.name}")
        
        # Send the request with multipart form data
        with open(temp_zip.name, 'rb') as zip_file:
            files = {
                'folder': ('batch.zip', zip_file, 'application/zip'),
                'output_dir': (None, output_dir),
                'format': (None, 'json')
            }
            logging.debug(f"Sending request to {url}")
            response = requests.post(url, files=files)
            response.raise_for_status()
            # Let's download the documents
            if response.status_code == 200:
                response_data = response.json()
                metadata_filename = response_data['metadata_file']
                metadata_download_url = f"http://localhost:5001/download/{metadata_filename}"
                metadata_output_path = os.path.join(output_dir, metadata_filename)
                stat_file_path = os.path.join(output_dir, 'stat_file.json')
                # check the stat file and print the number of figures and tables
                if os.path.exists(stat_file_path):
                    with open(stat_file_path, 'r') as stat_file:
                        stats = json.load(stat_file)
                        for doc, stat in stats.items():
                            num_figures = stat.get('figures', 0)
                            num_tables = stat.get('tables', 0)
                            print(f"Document: {doc}, Figures: {num_figures}, Tables: {num_tables}")
                
                # Download the figures
                download_file(metadata_download_url, metadata_output_path)

                figures = response_data.get('figures', [])
                for figure_url in figures:
                    figure_filename = os.path.basename(figure_url)
                    figure_download_url = f"http://localhost:5001/download/{figure_filename}"
                    download_file(figure_download_url, os.path.join(output_dir, figure_filename))
            else:
                logging.error(f"Error: {response.status_code}")
                logging.error(response.text)

            
        logging.info(f"Batch extraction completed. Statistics saved to {stat_file_path}")
        
    except requests.RequestException as e:
        logging.error(f"Error extracting batch: {str(e)}")
        if hasattr(e.response, 'content'):
            logging.error(f"Response content: {e.response.content}")
        raise
    finally:
        # Clean up temporary file
        if os.path.exists(temp_zip.name):
            os.unlink(temp_zip.name)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract figures and tables from a PDF file or a directory of PDF files.')
    parser.add_argument('path', type=str, help='Path to the PDF file or directory containing PDF files.')
    parser.add_argument('--url', type=str, default='http://localhost:5001/extract', help='URL of the extraction service for single PDF files.')
    parser.add_argument('--batch-url', type=str, default='http://localhost:5001/extract_batch', help='URL of the extraction service for batch processing.')
    parser.add_argument('--output-dir', type=str, default='./output', help='Directory to save the output files.')
    parser.add_argument('--is-directory', action='store_true', help='Specify if the path is a directory containing PDF files.')

    args = parser.parse_args()

    if args.is_directory:
        extract_batch(args.path, args.output_dir, args.batch_url)
    else:
        extract_file(args.path, args.output_dir, args.url)


