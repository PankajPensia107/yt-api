# Python base image
FROM python:3.10-slim

# System dependencies install karna (Tesseract, Poppler, OpenCV support)
# System dependencies install karna (Robust Version)
# System dependencies install karna (Updated for Debian Trixie/Latest)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-hin \
    tesseract-ocr-pan \
    libtesseract-dev \
    poppler-utils \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Work directory set karna
WORKDIR /app

# Requirements copy aur install karna
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Baaki saara code copy karna
COPY . .

# Upload directory banana
RUN mkdir -p uploads

# Port expose karna
EXPOSE 8000

# App run karne ki command
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
