import argparse
import os
import requests
import tempfile
import zipfile
import json
from urllib.parse import urljoin
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

DEFAULT_OUTPUT_DIR = os.path.join(os.getcwd(), 'output')

class FileDownloader:
    @staticmethod
    def download_file(download_url, output_path, timeout=30):
        """
        Downloads a file from the given URL to the specified path.
        
        :param download_url: The URL of the file to download.
        :param output_path: The file system path to save the downloaded file.
        :param timeout: The request timeout duration.
        """
        try:
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            logging.debug(f"Starting download from {download_url}")
            response = requests.get(download_url, stream=True, timeout=timeout)
            response.raise_for_status()
            with open(output_path, 'wb') as file:
                for chunk in response.iter_content(chunk_size=8192):
                    file.write(chunk)
            logging.debug(f"Downloaded file to {output_path}")
        except requests.RequestException as e:
            logging.error(f"Failed to download {download_url}: {str(e)}")
            raise

    @staticmethod
    def download_extracted_data(response_data, output_dir, base_url="http://localhost:5001"):
        """
        Downloads metadata and figures from the extraction response data.

        :param response_data: The JSON response data from the server.
        :param output_dir: Directory to save the downloaded files.
        :param base_url: Base URL for downloading files.
        """
        try:
            metadata_filename = response_data['metadata_filename']
            metadata_download_url = urljoin(base_url, f"download/{metadata_filename}")
            metadata_output_path = os.path.join(output_dir, metadata_filename)
            FileDownloader.download_file(metadata_download_url, metadata_output_path)

            figures = response_data.get('figures', [])
            for figure_filename in figures:
                figure_download_url = urljoin(base_url, f"download/{figure_filename}")
                figure_output_path = os.path.join(output_dir, figure_filename)
                FileDownloader.download_file(figure_download_url, figure_output_path)

            tables = response_data.get('tables', [])
            for table_filename in tables:
                table_download_url = urljoin(base_url, f"download/{table_filename}")
                table_output_path = os.path.join(output_dir, table_filename)
                FileDownloader.download_file(table_download_url, table_output_path)

        except Exception as e:
            logging.error(f"Error downloading extracted data: {str(e)}")
            raise

class PDFExtractor:
    @staticmethod
    def extract_pdf(file_path, output_dir, url="http://localhost:5001/extract", base_url="http://localhost:5001"):
        """
        Extracts figures and tables from a PDF file by sending it to the server and downloads the extracted data.

        :param file_path: Path to the PDF file to be extracted.
        :param url: URL of the extraction service.
        :param output_dir: Directory to save the downloaded files.
        :param base_url: Base URL for downloading files.
        :return: Response from the server.
        """
        try:
            logging.debug(f"Uploading {file_path} to {url} for extraction")
            logging.info(f"Extracting figures and tables from {file_path}")
            with open(file_path, 'rb') as file:
                files = {'file': file}
                response = requests.post(url, files=files)
            response.raise_for_status()
            logging.info(f"Extraction successful for {file_path}")
            response_data = response.json()
            PDFExtractor.download_extracted_data(response_data, output_dir, base_url)
            return response_data
        except requests.RequestException as e:
            logging.error(f"Error extracting PDF: {str(e)}")
            raise

class DirectoryProcessor:
    @staticmethod
    def zip_directory(folder_path):
        """
        Creates a ZIP file from the specified directory - only including pdf files.

        :param folder_path: Path to the directory to zip.
        :return: Path to the temporary ZIP file.
        """
        logging.debug(f"Zipping directory: {folder_path}")
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, _, files in os.walk(folder_path):
                for file in files:
                    if file.lower().endswith('.pdf'):
                        zipf.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), folder_path))
        logging.debug(f"Created ZIP file at {temp_zip.name}")
        return temp_zip.name

    @staticmethod
    def setup_output_directory(output_dir):
        """
        Ensures the output directory exists and is writable.

        :param output_dir: Path to the output directory.
        :return: Absolute path to the output directory.
        """
        try:
            output_dir = os.path.abspath(output_dir)
            os.makedirs(output_dir, exist_ok=True)
            if not os.access(output_dir, os.W_OK):
                raise PermissionError(f"No write permission for directory: {output_dir}")
            logging.info(f"Output directory is set to {output_dir}")
            return output_dir
        except Exception as e:
            logging.error(f"Error setting up output directory: {str(e)}")
            raise

class BatchExtractor:
    @staticmethod
    def extract_batch(folder_path, output_dir, url="http://localhost:5001/extract_batch"):
        """
        Extracts figures and metadata from a batch of PDF files in a directory.

        :param folder_path: Path to the folder containing PDF files.
        :param output_dir: Directory to save the results.
        :param url: URL of the batch extraction service.
        :return: Processed results.
        """
        try:
            logging.info(f"Processing batch extraction for {folder_path}")
            output_dir = DirectoryProcessor.setup_output_directory(output_dir)
            logging.debug(f"Output directory: {output_dir}")
            zip_file_path = DirectoryProcessor.zip_directory(folder_path)
            logging.debug(f"Created ZIP file: {zip_file_path}")

            with open(zip_file_path, 'rb') as zip_file:
                files = {
                    'folder': ('batch.zip', zip_file, 'application/zip')
                }
                logging.debug(f"Sending request to {url}")
                logging.debug(f"Files: {files}")
                response = requests.post(url, files=files)
                response.raise_for_status()
                logging.error(f"Received response: {response.status_code} - {response.text}")

                if not isinstance(response, dict) or "error" not in response:
                    response_data = response.json()
                    logging.info(f"Received response data: {json.dumps(response_data, indent=2)}")
                    logging.info(f"Downloading extracted data to {response_data}")

                    for doc in response_data:
                        logging.info(f"Downloading metadata for {doc['document']}")
                        # download metadata, figures and tables for each document
                        FileDownloader.download_extracted_data(doc, output_dir, base_url="http://localhost:5001")

                        # update figures and tables paths with output directory
                        figures = doc.get('figures', [])
                        tables = doc.get('tables', [])
                        doc["figures"] = [os.path.join(output_dir, fig) for fig in figures]
                        doc["tables"] = [os.path.join(output_dir, tab) for tab in tables]

                    # Extract figure-level information
                        figures_with_metadata = []
                        figure_metadata_path = os.path.join(output_dir, f"{doc["document"]}.json")
                        with open(figure_metadata_path, 'r') as metadata_file:
                            figure_metadata = json.load(metadata_file)

                        for fig in figures:
                            figure_info = get_figure_metadata(figure_metadata, fig)
                            figures_with_metadata.append({
                                'figure': fig,
                                'metadata': figure_info
                            })
                        
                        doc['figures_with_metadata'] = figures_with_metadata

                # Save the response data as a JSON file
                json_output_path = os.path.join(output_dir, 'stat_file.json')
                with open(json_output_path, 'w') as json_file:
                    json.dump(response_data, json_file, indent=2)
                logging.info(f"Saved response data to {json_output_path}")                  

                return response_data

        except Exception as e:
            logging.error(f"Error during batch extraction: {str(e)}")
            raise

        finally:
            if os.path.exists(zip_file_path):
                os.unlink(zip_file_path)
                logging.debug(f"Deleted temporary ZIP file {zip_file_path}")
                
def get_figure_metadata(figure_metadata, fig):
    render_url = next((item['renderURL'] for item in figure_metadata if 'renderURL' in item and item['renderURL'].endswith(f"/{fig}")), None)
    if render_url:
        logging.debug(f"Found renderURL for {fig}: {render_url}")
        figure_info = next((item for item in figure_metadata if item['renderURL'] == render_url), {})
        return figure_info
    else:
        logging.debug(f"No renderURL found for {fig}")
        return {}
    
def extract_figures(input_path, output_dir, url=None):
    """
    Processes the given path either as a directory or a file and runs the appropriate extraction function.

    :param input_path: Path to the input file or directory.
    :param output_dir: Directory to save the output files.
    :param url: URL for the extraction service (optional).
    """
    if os.path.isfile(input_path):
        if url is None:
            url = "http://localhost:5001/extract"
        response = PDFExtractor.extract_pdf(input_path, output_dir, url)
        logging.info(f"Extraction response: {json.dumps(response, indent=2)}")
        return response
    elif os.path.isdir(input_path):
        if url is None:
            url = "http://localhost:5001/extract_batch"
        response = BatchExtractor.extract_batch(input_path, output_dir, url)
        logging.info(f"Batch extraction response: {json.dumps(response, indent=2)}")
        return response
    else:
        logging.error("Invalid input path. It should be either a file or a directory.")
        return None

def main():
    parser = argparse.ArgumentParser(description="Process PDF files and extract figures, tables and images.")
    parser.add_argument('input_path', help="Path to the input PDF file or directory containing PDF files.")
    parser.add_argument('--output_dir', nargs='?', default='output', help="Directory to save extracted figures. Defaults to './output' if not specified.")
    parser.add_argument('--url', help="URL for the extraction service. For file extraction: 'http://localhost:5001/extract', for batch extraction: 'http://localhost:5001/extract_batch'. Only needed if you change the port while running Docker.")
    
    args = parser.parse_args()

    try:
        output_dir = args.output_dir if args.output_dir else DEFAULT_OUTPUT_DIR
        output_dir = DirectoryProcessor.setup_output_directory(output_dir)
        response = extract_figures(args.input_path, output_dir, args.url)
        print(json.dumps(response, indent=2))
    except Exception as e:
        logging.error(f"Error during extraction: {str(e)}")

if __name__ == "__main__":
    main()