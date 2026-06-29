# Start from an official Python image — slim means smaller file size
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system libraries that PyMuPDF needs to read PDFs
RUN apt-get update && apt-get install -y \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first — Docker caches this layer
# So if you only change code (not requirements), pip install is skipped on rebuild
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all your project files into the container
COPY . .

# Create the data directories inside the container
RUN mkdir -p uploads reports state

# Tell Docker this app listens on port 8000
EXPOSE 8000

# The command that runs when the container starts
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]