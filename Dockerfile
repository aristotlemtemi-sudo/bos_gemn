FROM python:3.12-slim

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        tesseract-ocr \
        libjpeg-dev \
        zlib1g-dev \
        libtiff-dev \
        libopenjp2-7-dev \
        libwebp-dev \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

COPY . .

EXPOSE 10000
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:$PORT"]
