# Use a slim version of OpenJDK 11 as the base image
FROM openjdk:11-jdk-slim

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
RUN pip3 install --no-cache-dir -r /app/requirements.txt

# Set environment variables for Java
ENV JAVA_HOME=/usr/lib/jvm/java-11-openjdk-amd64
ENV PATH="${JAVA_HOME}/bin:${PATH}"

# Set environment variable for the output directory (allow overrides from Docker or ENV)
ENV OUTPUT_DIR=/app/output

# Expose port 5001 for the Flask app (where it will run)
EXPOSE 5001

# Command to run the Flask server
CMD ["python3", "run.py"]