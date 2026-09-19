FROM python:3.11-slim

WORKDIR /app

# Copy core framework
COPY core /app/core

# Copy tool specific code
COPY tools/dnslog /app/tool

# Install dependencies
RUN pip install --no-cache-dir -r tool/requirements.txt

# Set python path to include /app so imports work
ENV PYTHONPATH=/app

CMD ["python", "tool/main.py"]
