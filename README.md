# Figure Extractor API

Extract figures and tables from PDF documents using this Flask-based service. The Figure Extractor API provides a straightforward HTTP interface for PDFFigures 2.0, a robust figure extraction system developed by the Allen Institute for AI. 

This API wrapper makes it ideal for integration into various applications and workflows, particularly for Retrieval-Augmented Generation (RAG) applications.


### About PDFFigures 2.0
This API service is built on top of PDFFigures 2.0, a Scala-based project by the Allen Institute for AI. PDFFigures 2.0 is specifically designed to extract figures, captions, tables, and section titles from scholarly documents in computer science domain. The original work is described in their academic paper: "PDFFigures 2.0: Mining Figures from Research Papers" (Clark and Divvala, 2016). You can read the paper [here](https://ai2-website.s3.amazonaws.com/publications/pdf2.0.pdf) and visit the [PDFFigures 2.0 website](http://pdffigures2.allenai.org/).


```
┌─────────────────┐      ┌──────────────────┐      ┌────────────────┐
│   Your App      │ HTTP │ Figure Extractor │ JNI  │  PDFFigures    │
│  (Any Language) │──────►      API         │──────►     2.0        │
│                 │      │  Python(Flask)   │      │  (Scala/JVM)   │
└─────────────────┘      └──────────────────┘      └────────────────┘
```
## Features

- PDF figure and table extraction
- Support for local and remote PDF files
- Batch processing capabilities for directories
- Statistics of the extracted tables and figures
- Docker support for easy deployment
- Visualization options for PDF parsing

## Use Cases

1. *Machine Learning Dataset Creation*
Extract visual data from clinical trial reports and research papers to build training datasets for medical image analysis and AI models, enabling researchers to efficiently aggregate figures for training machine learning algorithms in healthcare diagnostics.

2. *Clinical Research Data Mining*
Automatically extract and catalog figures from medical research articles, capturing key visualizations like treatment effect graphs, patient outcome charts, and experimental result diagrams to support systematic reviews and meta-analysis.

3. *Academic Literature Review and Education*
Quickly compile comprehensive visual libraries from academic publications, allowing researchers and educators to create teaching resources, compare research methodologies, and track visual trends across scientific disciplines.

## Setup

### Step 1: Build and Run the Docker Container

1. Clone the repository:

    ```sh
    git clone https://github.com/Huang-lab/figure-extractor.git
    cd pdf-extraction
    ```

2. Build the Docker image:

    ```sh
    docker build -t pdf-extraction .
    ```

3. Run the Docker container:

    ```sh
    docker run -p 5001:5001 pdf-extraction
    ```

    ### API Documentation

    For detailed API documentation, visit [API Docs](https://app.swaggerhub.com/apis-docs/WZEHRAKORKUSUZ/figure-extractor_api/1.0.0) 

## Usage: [`how-to.ipynb`](how-to.ipynb)

### Extract Figures and Tables from a PDF

"""
Processes a document and performs various operations on each page.

Average processing time per page: ~1.06 - 1.55 seconds (based on a 29-page document with a total processing time of ~45 seconds)
"""

#### Using the Module in Python Code


For example code snippets, please refer to the [`how-to.ipynb`](how-to.ipynb) notebook.

#### Using the CLI

**Default behavior**

```sh
python figure_extractor.py 2404.18021v1.pdf
```
This saves the extracted figures to `./output`

**Specifying output directory:**

```sh
python figure_extractor.py path/to/pdf/file --output_dir ./figures
```

This saves the extracted figures to `./figures`, creating the directory if it does not exist.

**Processing a folder:**

```sh
python figure_extractor.py /path/to/pdf/folder --output-dir ./custom_output
```
**Specifying a custom URL if you run the docker service on another port:**

```sh
    python figure_extractor.py path/to/pdf/file --url http://localhost:5001/extract --output-dir ./output
```

```sh
    python figure_extractor.py /path/to/pdf/folder --url http://localhost:5001/extract_batch --output-dir ./output
```




## App Structure
```
project/
├── Dockerfile                # Defines the Docker image for the Flask web service
├── Dockerignore    
├── app/                      # Contains the Flask web service code
│   ├── __init__.py           # Initializes the Flask app
│   ├── routes.py             # Defines the API endpoints
│   ├── service.py            # Contains the logic for running `pdffigures2`
│   └── utils.py              # Utility functions for file handling
├── figure_extractor.py       # CLI & Module for extracting figures and tables from a PDF file
├── how-to.ipynb 
└── README.md                 
```

## License

This project is licensed under the Apache License 2.0.
