from werkzeug.utils import secure_filename
import os
import json

def save_uploaded_file(file):
    filename = secure_filename(file.filename)
    file_path = os.path.join('/app/uploads/', filename)
    file.save(file_path)
    return file_path

def read_output_file(output_file):
    if not os.path.exists(output_file):
        return None
    with open(output_file, 'r') as f:
        output_data = f.read()
    return json.loads(output_data)