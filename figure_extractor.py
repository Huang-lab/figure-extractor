import requests
import os
import logging

def extract_pdf(file_path, url='http://localhost:5001/extract'):
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
        logging.error(f"Error extracting PDF: {str(e)}")
        raise

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
        logging.error(f"Error downloading file: {str(e)}")
        raise

def extract_figures(file_path, output_dir='.', url='http://localhost:5001/extract'):
    """
    Extract figures and tables from a PDF file and download the results.

    :param file_path: Path to the PDF file to be extracted.
    :param output_dir: Directory to save the downloaded files.
    :param url: URL of the extraction service.
    """
    logging.basicConfig(level=logging.INFO)

    try:
        response = extract_pdf(file_path, url)
        print(response.text)

        if response.status_code == 200:
            response_data = response.json()

            # Download the JSON metadata file
            metadata_filename = response_data['metadata_file']
            metadata_download_url = f"http://localhost:5001/download/{metadata_filename}"
            metadata_output_path = os.path.join(output_dir, metadata_filename)
            download_file(metadata_download_url, metadata_output_path)

            # Download the figures
            figures = response_data.get('figures', [])
            for figure_url in figures:
                figure_filename = os.path.basename(figure_url)
                figure_download_url = f"http://localhost:5001/download/{figure_filename}"
                figure_output_path = os.path.join(output_dir, figure_filename)
                download_file(figure_download_url, figure_output_path)
    except Exception as e:
        logging.error(f"An error occurred: {str(e)}")