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

    @staticmethod
    def download_extracted_data(response_data, output_dir, base_url="http://localhost:5001"):
        """
        Downloads metadata and figures from the extraction response data.

        :param response_data: The JSON response data from the server.
        :param output_dir: Directory to save the downloaded files.
        :param base_url: Base URL for downloading files.
        """
        try:
            metadata_filename = response_data['metadata_file']
            metadata_download_url = urljoin(base_url, f"download/{metadata_filename}")
            metadata_output_path = os.path.join(output_dir, metadata_filename)
            FileDownloader.download_file(metadata_download_url, metadata_output_path)

            figures = response_data.get('figures', [])
            for figure_url in figures:
                figure_filename = os.path.basename(figure_url)
                figure_download_url = urljoin(base_url, f"download/{figure_filename}")
                figure_output_path = os.path.join(output_dir, figure_filename)
                FileDownloader.download_file(figure_download_url, figure_output_path)

            tables = response_data.get('tables', [])
            for table_url in tables:
                table_filename = os.path.basename(table_url)
                table_download_url = urljoin(base_url, f"download/{table_filename}")
                table_output_path = os.path.join(output_dir, table_filename)
                FileDownloader.download_file(table_download_url, table_output_path)

        except Exception as e:
            logging.error(f"Error downloading extracted data: {str(e)}")
            raise

    @staticmethod
    def process_batch_results(response_data):
        """
        Processes batch extraction results.

        :param response_data: The JSON response data from the server.
        :return: Processed results.
        """
        total_pages = 0
        total_time = 0

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

        avg_time_per_page = total_time / total_pages if total_pages > 0 else 0

        logging.info(f"Processed {len(response_data)} documents")
        return {
            'num_documents': len(response_data),
            'documents': files_info,
            'processing_stats': {
                'total_pages': total_pages,
                'total_time_ms': total_time,
                'avg_ms_per_page': round(avg_time_per_page, 2)
            }
        }
    
    @staticmethod

    def process_command_result(result):
        structured_output = []
        for item in result:
            try:
                metadata_file = item['filename'] + '.json'
                with open(metadata_file, 'r') as f:
                    metadata = json.load(f)
                file_metadata = {
                    "filename": os.path.basename(item['filename']),
                    "num_figures": item['numFigures'],
                    "num_pages": item['numPages'],
                    "time_in_millis": item['timeInMillis'],
                    "metadata_file": item['filename'] + '.json',
                    "figures": [fig['renderURL'] for fig in metadata if fig.get('figType') == 'Figure'],
                    "tables": [fig['renderURL'] for fig in metadata if fig.get('figType') == 'Table']
                }
                structured_output.append(file_metadata)
            except json.JSONDecodeError:
                logging.error("Failed to decode metadata file as JSON")
                return {"error": "Failed to decode metadata file as JSON"}, 500

        response = {
            "documents": structured_output,
            "metadata_file": 'stat_file.json'
        }
        return response

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

                    logging.info(f"Downloading extracted data to {response_data}")
                    for doc in response_data:
                        logging.info(f"Downloading metadata for {doc['filename']}")
                        metadata_filename = doc['metadata_file']
                        metadata_download_url = urljoin(url, f"download/{metadata_filename}")
                        metadata_output_path = os.path.join(output_dir, metadata_filename)
                        FileDownloader.download_file(metadata_download_url, metadata_output_path)

                        figures = doc.get('figures', [])
                        logging.info(f"Downloading figures for {doc['filename']}")
                        for figure_url in figures:
                            figure_filename = os.path.basename(figure_url)
                            figure_download_url = urljoin(url, f"download/{figure_filename}")
                            figure_output_path = os.path.join(output_dir, figure_filename)
                            FileDownloader.download_file(figure_download_url, figure_output_path)

                        tables = doc.get('tables', [])
                        logging.info(f"Downloading tables for {doc['filename']}")
                        for table_url in tables:
                            table_filename = os.path.basename(table_url)
                            table_download_url = urljoin(url, f"download/{table_filename}")
                            table_output_path = os.path.join(output_dir, table_filename)
                            FileDownloader.download_file(table_download_url, table_output_path)

                        # Modify the paths
                        doc["figures"] = [os.path.join(output_dir, os.path.basename(fig)) for fig in figures]
                        doc["tables"] = [os.path.join(output_dir, os.path.basename(tab)) for tab in tables]

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
    parser = argparse.ArgumentParser(description="Process PDF files and extract data.")
    parser.add_argument('input_path', help="Path to the input file or directory")
    parser.add_argument('output_dir', help="Directory to save the output files")
    parser.add_argument('--url', help="URL for the extraction service", default=None)
    
    args = parser.parse_args()

    try:
        response = extract_figures(args.input_path, args.output_dir, args.url)
        print(response)
    except Exception as e:
        logging.error(f"Error during extraction: {str(e)}")

if __name__ == "__main__":
    main()