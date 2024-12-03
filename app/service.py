import subprocess
import os

def run_pdffigures2(file_path, output_dir):
    base_command = [
        "java", "-jar", "/pdffigures2/pdffigures2.jar",
        file_path,
        "-m", output_dir,
        "-d", output_dir,
        "--dpi", "300"
    ]
    result = subprocess.run(base_command, capture_output=True, text=True)
    return result

# run batches

# run url 

def count_figures_and_tables(figures):
    render_urls = {fig.get('renderURL') for fig in figures if fig.get('figType') == 'Table'}
    num_tables = len(render_urls)
    num_figures = sum(1 for fig in figures if fig.get('figType') == 'Figure')
    return num_tables, num_figures