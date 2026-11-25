FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install curl for container health check and build tools for C-extensions
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --no-cache-dir --default-timeout=1000 -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt

# Copy backend source code
COPY . /app/

# Collect static files for WhiteNoise
RUN python manage.py collectstatic --noinput

EXPOSE 8000

# Default production command using Gunicorn with 3 workers
CMD ["gunicorn", "bizpermit_core.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3", "--timeout", "120"]
