# Use a slim Python 3.12 image to match project requirements
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy only requirements first for better caching
COPY requirements.txt .

# Install dependencies with hash verification
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

# Copy the rest of the application
COPY . .

# Create generic mock S3 storage root.
# Bucket folders and object prefixes are created on demand.
RUN mkdir -p s3_buckets && chmod -R 777 s3_buckets

# Expose the default port
EXPOSE 8001

# Run the application with uvicorn and enable reload for iterative development
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]
