# ─────────────────────────────────────────────────────────────────────────────
# Stage 1 — Builder
# Install Python dependencies into a clean layer so the final image stays lean
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /install

# Copy only requirements first (better layer caching — only rebuilds on changes)
COPY requirements.txt .

RUN pip install --upgrade pip \
 && pip install --prefix=/install/pkgs --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2 — Runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# ── System dependencies ───────────────────────────────────────────────────────
# tesseract-ocr       — OCR engine for image text extraction
# tesseract-ocr-eng   — English language data for Tesseract
# poppler-utils       — PDF → image conversion (used by pdf2image)
# libgl1              — OpenCV / Pillow dependency
# curl                — useful for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
        tesseract-ocr \
        tesseract-ocr-eng \
        poppler-utils \
        libgl1 \
        curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ── Copy installed Python packages from builder ───────────────────────────────
COPY --from=builder /install/pkgs /usr/local

# ── App setup ─────────────────────────────────────────────────────────────────
WORKDIR /app

# Create a non-root user for security
RUN groupadd -r appuser && useradd -r -g appuser appuser

# Copy application code
COPY . .

# Set correct ownership
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

# ── Environment ───────────────────────────────────────────────────────────────
ENV FLASK_APP=app.py \
    FLASK_ENV=production \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Tell Tesseract where its data lives (set by apt install)
    TESSDATA_PREFIX=/usr/share/tesseract-ocr/5/tessdata

EXPOSE 5050

# ── Healthcheck ───────────────────────────────────────────────────────────────
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5050/ || exit 1

# ── Start ─────────────────────────────────────────────────────────────────────
# Use gunicorn for production; falls back gracefully with flask run for dev
CMD ["python", "-m", "gunicorn", \
     "--bind", "0.0.0.0:5050", \
     "--workers", "1", \
     "--timeout", "120", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app:app"]
