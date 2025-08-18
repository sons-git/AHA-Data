# Use the official lightweight Python 3.11 image as the base
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies:
# - gcc     → needed for building some Python packages with C extensions
# - ffmpeg  → for handling audio/video processing (if required by your app)
# Then clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy only requirements first (for better Docker layer caching)
COPY requirements.txt .

# Install uv (fast Python package manager)
RUN pip install uv

# Use uv to install dependencies into the system Python environment
# --system ensures packages go to the global site-packages, not a virtualenv
RUN uv pip install --system -r requirements.txt

# Copy the rest of the application code
COPY . .

# Expose port 8080 for the FastAPI/Uvicorn app
EXPOSE 8080

# Start the FastAPI app with Uvicorn
# --host 0.0.0.0 → listen on all network interfaces
# --port 8080    → container port
# --workers 4    → number of worker processes for handling requests
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
