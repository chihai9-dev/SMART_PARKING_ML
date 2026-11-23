FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/workspace \
    FLASK_DEBUG=0

# OpenCV, ONNX Runtime and pytesseract need native system libraries.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    libgomp1 \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
COPY requirements.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir -r requirements.txt

# Copy the repository so the app can import src.* and load models/data if present.
COPY . ./

ENV SMARTPARKING_API_URL=http://backend:8080
EXPOSE 5000

# Flask CLI binds to 0.0.0.0 inside the container. This avoids app.run's
# default localhost-only bind and does not enable the development debugger.
CMD ["python", "-m", "flask", "--app", "app.app", "run", "--host=0.0.0.0", "--port=5000"]
