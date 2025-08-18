# Use the official lightweight Python 3.11 image as the base
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Install system dependencies:
# - gcc     → needed for building some Python packages with C extensions
# - ffmpeg  → for handling audio/video processing (if your app needs it)
# Clean up apt cache to reduce image size
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install uv and all Python dependencies in one layer
RUN pip install uv \
    && uv pip install --system -r requirements.txt

# Copy the rest of the application code
COPY . .

# Default port for local development; Cloud Run overrides this automatically
ENV PORT=8080

# Expose port (optional; good practice)
EXPOSE 8080

# Start the FastAPI app with Uvicorn
# Shell form allows $PORT to expand correctly at runtime
CMD uvicorn app.main:app --host 0.0.0.0 --port $PORT --workers 4
