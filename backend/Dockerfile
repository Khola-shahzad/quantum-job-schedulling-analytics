# ============================
# Quantum Scheduler Backend
# ============================

# Base image with Python + Java support (Debian Bullseye)
FROM python:3.10-bullseye

# Set working directory
WORKDIR /app

# Install system dependencies (includes Java 17 for PySpark)
RUN apt-get update && apt-get install -y \
    openjdk-17-jre-headless \
    && rm -rf /var/lib/apt/lists/*

# Environment variable for Java
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64
ENV PATH=$JAVA_HOME/bin:$PATH

# Copy dependency list
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose Flask port
EXPOSE 5000

# Start Flask app
CMD ["python", "app.py"]
