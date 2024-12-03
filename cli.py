import argparse
from figure_extractor import extract_figures
import os

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Extract figures and tables from a PDF file.')
    parser.add_argument('file_path', type=str, help='Path to the PDF file to be extracted.')
    parser.add_argument('--url', type=str, default='http://localhost:5001/extract', help='URL of the extraction service.')
    parser.add_argument('--output-dir', type=str, default='.', help='Directory to save the downloaded files.')

    args = parser.parse_args()

    # Create output directory if it does not exist
    if not os.path.exists(args.output_dir):
        os.makedirs(args.output_dir)
        print(f"Output directory '{args.output_dir}' created.")

    extract_figures(args.file_path, args.output_dir, args.url)