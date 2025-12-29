# Modern Figure Extractor

A high-performance, modernized wrapper for [PDFFigures 2.0](http://pdffigures2.allenai.org/), designed for seamless integration into modern AI workflows and RAG (Retrieval-Augmented Generation) pipelines.

This project takes the robust extraction capabilities of the Allen Institute for AI's PDFFigures 2.0 and wraps them in a sophisticated, modular Python architecture with production-ready features.

## 🚀 Modernization Highlights

While the core extraction engine remains the powerful PDFFigures 2.0, this project introduces significant modernizations:

- **Modular Architecture**: Clean separation between core extraction logic, web service, and CLI tools.
- **Dual-Mode Execution**: Run extractions locally (direct JVM call) or remotely via a high-performance Flask API.
- **Automated Environment Setup**: A smart setup script that handles Java 11 detection, Scala/sbt building, and Python dependency management.
- **Production-Ready API**: Includes rate limiting, request tracking (UUIDs), standardized error handling, and automated background cleanup.
- **Interactive Documentation**: Built-in Swagger/OpenAPI documentation for easy API exploration.
- **Standardized Metadata**: Enhanced JSON parsing that provides consistent, easy-to-consume figure and table metadata.

## 🛠 Features

- **High-Accuracy Extraction**: Captures figures, tables, captions, and their precise coordinates.
- **Batch Processing**: Efficiently process entire directories of PDFs in one command.
- **Flexible Deployment**: Run as a lightweight CLI tool, a local web server, or a containerized Docker service.
- **Automated Cleanup**: Background worker ensures temporary files and old results don't exhaust disk space.
- **Security Focused**: Input validation, secure filename handling, and directory traversal protection.

## 📋 Setup

### Option 1: Local Setup (Recommended for Development)

1.  **Prerequisites**: Ensure you have **Java 11** installed.
2.  **Run Setup**:
    ```sh
    python3 setup_local.py
    ```
    *This script will automatically clone pdffigures2, build the JAR using sbt, and install all Python requirements.*

3.  **Verify**:
    ```sh
    python3 figure_extractor.py path/to/sample.pdf --local
    ```

### Option 2: Docker Setup (Recommended for Production)

1.  **Build**:
    ```sh
    docker build -t figure-extractor .
    ```
2.  **Run**:
    ```sh
    docker run -p 5001:5001 figure-extractor
    ```

## 📖 Usage

### CLI Tool
The `figure_extractor.py` script is your primary interface.

**Local Mode (Direct Extraction):**
```sh
python3 figure_extractor.py path/to/document.pdf --local --output-dir ./results
```

**Remote Mode (Via API):**
```sh
python3 figure_extractor.py path/to/document.pdf --output-dir ./results
```

### API Endpoints
- `POST /extract`: Extract from a single PDF file.
- `POST /extract_batch`: Extract from a ZIP archive of PDFs.
- `GET /download/<filename>`: Retrieve extracted images or JSON metadata.
- `GET /api/docs`: Interactive Swagger UI documentation.

## 🏗 Project Structure

```text
├── app/                # Flask Web Service
│   ├── routes.py       # API Endpoints & Rate Limiting
│   ├── service.py      # Service Layer
│   ├── utils.py        # Standardized Responses & Validation
│   └── cleanup.py      # Background Cleanup Worker
├── core/               # Core Logic (Framework Agnostic)
│   ├── config.py       # Centralized Configuration
│   ├── extractor.py    # pdffigures2 Subprocess Wrapper
│   └── metadata.py     # Metadata Parsing & Normalization
├── figure_extractor.py # Unified CLI Tool
├── setup_local.py      # Intelligent Setup Script
├── run.py              # Local API Entry Point
└── Dockerfile          # Production Container Config
```

## 📜 Attribution & License

This project is built upon **PDFFigures 2.0**, developed by the Allen Institute for AI. 
- **Paper**: [PDFFigures 2.0: Mining Figures from Research Papers](https://ai2-website.s3.amazonaws.com/publications/pdf2.0.pdf) (Clark and Divvala, 2016).
- **Original Source**: [allenai/pdffigures2](https://github.com/allenai/pdffigures2)

Licensed under the **Apache License 2.0**.

