FROM python:3.11-slim

# You can build with: docker build --build-arg UV_VERSION=0.1.22 -t your-image .
ARG UV_VERSION=0.1.22

WORKDIR /app

# Install curl just to fetch uv, then remove it and clean apt metadata to keep the image small
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && curl -L "https://github.com/astral-sh/uv/releases/download/v${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" -o uv.tar.gz \
    && tar xzf uv.tar.gz -C /usr/local/bin \
    && rm uv.tar.gz \
    && apt-get purge -y curl \
    && apt-get autoremove -y \
    && rm -rf /var/lib/apt/lists/* \
    && chmod +x /usr/local/bin/uv

# Copy only requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies system-wide using uv
RUN uv pip install --system -r requirements.txt

# Now copy the rest of the app
COPY . .

# (Optional) Create and switch to a non-root user:
# RUN useradd -m appuser && chown -R appuser /app
# USER appuser

EXPOSE 8080

# Use uvicorn to serve the FastAPI app (adjust module if needed)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
