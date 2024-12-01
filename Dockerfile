FROM python:3.11-slim

WORKDIR /app

# Install postgresql-client for the health check
RUN apt-get update && apt-get install -y postgresql-client

COPY requirements.txt .
RUN pip install -r requirements.txt

# Create migrations directory
RUN mkdir -p migrations

# Copy application files
COPY . .

# Make the entrypoint script executable and ensure proper line endings
RUN chmod +x entrypoint.sh && \
    sed -i 's/\r$//' entrypoint.sh

EXPOSE 5000

ENTRYPOINT ["/bin/sh", "entrypoint.sh"] 