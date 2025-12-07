# Use a slim version of OpenJDK 25 as the base image
FROM eclipse-temurin:11-jdk-jammy

# Install dependencies for pdffigures2, git, and Python-related tools
RUN apt-get update && apt-get install -y \
    libleptonica-dev \
    tesseract-ocr \
    curl \
    gnupg \
    git \
    python3-pip && \
    # Add sbt repository and install sbt
    echo "deb https://repo.scala-sbt.org/scalasbt/debian all main" | tee /etc/apt/sources.list.d/sbt.list && \
    curl -sL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x99E82A75642AC823" | apt-key add && \
    apt-get update && \
    apt-get install -y sbt && \
    # Clean up to reduce image size
    rm -rf /var/lib/apt/lists/*

# Clone the pdffigures2 repository from GitHub
RUN git clone https://github.com/allenai/pdffigures2.git /pdffigures2

# Set the working directory to the cloned repository
WORKDIR /pdffigures2

# Build pdffigures2 with sbt assembly
RUN sbt assembly

# Create a directory for the Flask application code
WORKDIR /app

# Copy the Flask application files into the container
COPY . /app/

# Install Flask & other required Python packages
COPY requirements.txt /app/requirements.txt
RUN pip3 install --no-cache-dir -r /app/requirements.txt && \
    pip3 install --no-cache-dir gunicorn

# Set environment variables for Java (reduced heap to be container-friendly)
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"
# Use a conservative default heap; can be overridden with -e JAVA_OPTS
ENV JAVA_OPTS="-Xmx2g"

# Set environment variable for the output directory (allow overrides from Docker or ENV)
ENV OUTPUT_DIR=/app/output

# Expose port 5001 for the Flask app (where it will run)
EXPOSE 5001

# Default number of gunicorn workers (single worker to serialize heavy jobs)
ENV GUNICORN_WORKERS=1
ENV GUNICORN_TIMEOUT=600

# Command to run the Flask server via gunicorn
# "run:app" assumes run.py exposes a top-level Flask `app` object.
CMD ["gunicorn", "-w", "1", "--timeout", "600", "-b", "0.0.0.0:5001", "run:app"]
