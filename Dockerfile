FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl

# Set uv version and checksum
ENV UV_VERSION=0.1.22
ENV UV_SHA256=5c3c2b2c48e0e7f9b6f2a4c6c2e0cfb5b1fbd8f5e8fa2e5d0f5a9b6e7a7e4b5e

# Download, verify, and install uv binary
RUN curl -L "https://github.com/astral-sh/uv/releases/download/v${UV_VERSION}/uv-x86_64-unknown-linux-gnu.tar.gz" -o uv.tar.gz \
    && echo "${UV_SHA256}  uv.tar.gz" | sha256sum -c - \
    && tar xz -C /usr/local/bin -f uv.tar.gz \
    && chmod +x /usr/local/bin/uv \
    && rm uv.tar.gz

# Make sure it's executable
RUN chmod +x /usr/local/bin/uv

COPY requirements.txt .

# Use uv for package install
RUN uv pip install --system -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "4"]
