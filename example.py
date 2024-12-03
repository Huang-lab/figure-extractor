from figure_extractor import extract_figures

def main():
    # Path to the PDF file to be extracted
    file_path = '2404.18021v1.pdf'
    
    # Directory to save the downloaded files
    output_dir = './output'
    
    # URL of the extraction service
    url = 'http://localhost:5001/extract'
    
    # Extract figures and tables from the PDF file
    extract_figures(file_path, output_dir, url)

if __name__ == '__main__':
    main()