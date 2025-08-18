FROM python:3.11-slim

# Install dependencies
RUN apt-get update && apt-get install -y --no-install-recommends curl

# Download and install uv binary
RUN curl -L https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz \
  | tar xz -C /usr/local/bin

# Make sure it's executable
RUN chmod +x /usr/local/bin/uv
RUN mkdir -p /tmp/uv-extract && \
  curl -L https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz \
  | tar xz -C /tmp/uv-extract && \
  mv /tmp/uv-extract/uv /usr/local/bin/uv && \
  chmod +x /usr/local/bin/uv && \
  rm -rf /tmp/uv-extract
COPY requirements.txt .

# Use uv for package install
RUN uv pip install --system -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
