import argparse
import os
import requests
import shutil
import tempfile
import zipfile
import json
from urllib.parse import urljoin

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

# def download_file(url, output_dir):
#     response = requests.get(url)
#     if response.status_code == 200:
#         filename = os.path.basename(url)
#         output_path = os.path.join(output_dir, filename)
        
#         with open(output_path, 'wb') as file:
#             file.write(response.content)
#         logging.debug(f"Downloaded {url} to {output_path}")
#     else:
#         logging.error(f"Failed to download {url}: {response.status_code}")

def download_figures(item, output_dir, base_url="http://localhost:5001"):
    figures = item.get('figures', [])
    if not figures:
        logging.info("No figures found to download")
        return
    
    for figure_url in figures:
        try:
            # Validate URL
            if not figure_url:
                continue
                
            figure_filename = os.path.basename(figure_url)
            if not figure_filename:
                logging.warning(f"Invalid figure URL: {figure_url}")
                continue
            
            # Construct download URL properly
            figure_download_url = urljoin(base_url, f"download/{figure_filename}")
            
            # Download with timeout and error handling
            download_file(
                url=figure_download_url,
                output_dir=output_dir,
                timeout=30
            )
            logging.info(f"Successfully downloaded figure: {figure_filename}")
            
        except Exception as e:
            logging.error(f"Failed to download figure {figure_url}: {str(e)}")
            continue

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
        logging.debug(f"Response data: {response_data}")
        metadata_filename = response_data['metadata_file']
        metadata_download_url = f"http://localhost:5001/download/{metadata_filename}"
        metadata_output_path = os.path.join(output_dir, metadata_filename)
        download_file(metadata_download_url, metadata_output_path)

        figures = response_data.get('figures', [])
        for figure_url in figures:

            figure_filename = os.path.basename(figure_url)
            logging.debug(f"Downloading figure: {figure_filename}")
            figure_download_url = f"http://localhost:5001/download/{figure_filename}"
            logging.debug(f"Downloading figure: {figure_download_url}")

            # let's just handle it though download_file initially; in refactoring optimize
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

def process_batch_results(response_data):
    # Initialize aggregates
    total_pages = 0
    total_time = 0
    
    # Process documents
    files_info = []
    for doc in response_data:
        filename = os.path.splitext(os.path.basename(doc['filename']))[0]
        metadata_path = f"{filename}.json"
        
        files_info.append({
            'filename': filename,
            'metadata_file': metadata_path,
            'figures': doc['numFigures'],
            'pages': doc['numPages'],
            'time_ms': doc['timeInMillis']
        })
        
        total_pages += doc['numPages']
        total_time += doc['timeInMillis']
    
    # Calculate averages
    avg_time_per_page = total_time / total_pages if total_pages > 0 else 0

    
    result = {
        'num_documents': len(response_data),
        'documents': files_info,
        'processing_stats': {
            'total_pages': total_pages,
            'total_time_ms': total_time,
            'avg_ms_per_page': round(avg_time_per_page, 2)
        }
    }
    
    return result

def extract_batch(folder_path, output_dir, url="http://localhost:5001/extract_batch"):
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
           
            logging.debug(f"Initial output_dir: {output_dir}")

            if response.status_code == 200:
                response_data = response.json()
                #logging.debug(f"""Response: {response_data}""")
                results = process_batch_results(response_data)

                # Log results
                logging.info(f"Processed {results['num_documents']} documents")
                for doc in results['documents']:
                    logging.info(f"File: {doc['filename']}")
                    logging.info(f"Metadata file: {doc['metadata_file']}")
                    logging.info(f"Figures: {doc['figures']}")

                logging.info(f"Total documents processed: {results['num_documents']}, Total pages processed: {results['processing_stats']['total_pages']}")
                
                avg_time_per_page_sec = results['processing_stats']['avg_ms_per_page'] / 1000
                logging.info(f"Average processing time: {avg_time_per_page_sec:.2f} seconds/page")

                # Stat file have information about each document processed
                stat_file_path = os.path.join(output_dir, 'stat_file.json')
                if os.path.exists(stat_file_path):
                    logging.debug(f"Stat file saved to: {stat_file_path}")

                # Download metadata and figures
                #response_data = response.json()
                #logging.info(f"Response data: {response_data}")
                for doc in response_data:
                    filename = os.path.basename(doc['filename'])
                    metadata_filename = f"{os.path.splitext(filename)[0]}.json"
                    metadata_download_url = f"http://localhost:5001/download/{metadata_filename}"
                    metadata_output_path = os.path.join(output_dir, metadata_filename)
                    download_file(metadata_download_url, metadata_output_path) # requires full path
        
                    # Read the JSON file to get figure paths
                    with open(metadata_output_path, 'r') as f:
                        figure_data = json.load(f)
                        
                    # Download each figure
                    for figure in figure_data:
                        if 'renderURL' in figure:
                            figure_filename = os.path.basename(figure['renderURL'])
                            figure_download_url = f"http://localhost:5001/download/{figure_filename}"
                            figure_output_path = os.path.join(output_dir, figure_filename)
                            download_file(figure_download_url, figure_output_path)
                            
                    logging.info(f"Processed document {filename}: {doc['numFigures']} figures, {doc['numPages']} pages")
                
                # download stat_file.json
                stat_file = os.path.join(output_dir, 'stat_file.json')
                download_url = f"http://localhost:5001/download/stat_file.json"
                figure_output_path = os.path.join(output_dir, stat_file)
                download_file(download_url, stat_file)

            else:
                logging.error(f"Error: {response.status_code}")
                logging.error(response.text)

            
        logging.info(f"Batch extraction completed.")
        
    except requests.RequestException as e:
        logging.error(f"Error extracting batch: {str(e)}")
        if hasattr(e.response, 'content'):
            logging.error(f"Response content: {e.response.content}")
        raise
        
    except Exception as e:
        logging.error(f"Error during batch extraction: {str(e)}")
        raise
        
    finally:
        # Clean up temporary file
        if os.path.exists(temp_zip.name):
            os.unlink(temp_zip.name)


def setup_output_directory(output_dir):
    """Create and validate the output directory."""
    try:
        # Convert to absolute path
        output_dir = os.path.abspath(output_dir)
        
        # Verify we have write permissions
        if not os.access(output_dir, os.W_OK):
            raise PermissionError(f"No write permission for directory: {output_dir}")
            
        return output_dir
        
    except PermissionError as e:
        logging.error(f"Permission error: {str(e)}")
        raise
    except Exception as e:
        logging.error(f"Error setting up output directory: {str(e)}")
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract figures and tables from a PDF file or a directory of PDF files.')
    parser.add_argument('path', type=str, help='Path to the PDF file or directory containing PDF files.')
    parser.add_argument('--url', type=str, default='http://localhost:5001/extract', help='URL of the extraction service for single PDF files.')
    parser.add_argument('--batch-url', type=str, default='http://localhost:5001/extract_batch', help='URL of the extraction service for batch processing.')
    parser.add_argument('--output-dir', type=str, default='./output', help='Directory to save the output files.') #TODO: Change default output directory
    parser.add_argument('--is-directory', action='store_true', help='Specify if the path is a directory containing PDF files.')

    args = parser.parse_args()

    output_dir = setup_output_directory(args.output_dir)
    os.chmod(output_dir, 0o777)  # Give full permissions
    

    if args.is_directory:
        extract_batch(args.path, args.output_dir, args.batch_url)
    else:
        extract_file(args.path, args.output_dir, args.url)


