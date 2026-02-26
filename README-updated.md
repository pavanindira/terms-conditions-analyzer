# ⚖️ Terms & Conditions Analyzer

A fully **rule-based** T&C analyzer with no AI, no external APIs, no data
leaving your machine. Built with **Flask + Jinja2** and containerized with
**Docker**.

---

## Quick Start — Docker (recommended)

```bash
# 1. Clone / download the project
cd tc_app

# 2. Copy and configure environment
cp .env.example .env
# Edit .env and set a strong SECRET_KEY

# 3. Build and run
docker compose up --build

# App is live at http://localhost:5050
```

To run in the background:
```bash
docker compose up --build -d
```

To stop:
```bash
docker compose down
```

---

## Docker Commands Reference

| Command | What it does |
|---|---|
| `docker compose up --build` | Build image and start container (foreground) |
| `docker compose up --build -d` | Build and start in background |
| `docker compose down` | Stop and remove container |
| `docker compose logs -f` | Follow live logs |
| `docker compose ps` | Check container status |
| `docker compose restart web` | Restart the web service |
| `docker build -t tc-analyzer .` | Build image manually |
| `docker run -p 5050:5050 tc-analyzer` | Run image directly |

---

## Manual Setup (without Docker)

```bash
# Python 3.9+ required

# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install system dependencies (for OCR)
# macOS
brew install tesseract poppler

# Ubuntu / Debian
sudo apt install tesseract-ocr tesseract-ocr-eng poppler-utils

# Windows — download installers:
# Tesseract: https://github.com/UB-Mannheim/tesseract/wiki
# Poppler:   https://github.com/oschwartz10612/poppler-windows

# 4. Run
python app.py
# → http://localhost:5050
```

---

## Project Structure

```
tc_app/
├── Dockerfile              ← Multi-stage Docker build
├── docker-compose.yml      ← Docker Compose orchestration
├── .dockerignore           ← Files excluded from Docker image
├── .env.example            ← Environment variable template
├── app.py                  ← Flask routes
├── analyzer.py             ← Rule-based analysis engine (no AI)
├── requirements.txt        ← Python dependencies (includes gunicorn)
├── templates/
│   ├── base.html
│   ├── index.html
│   ├── result.html
│   └── about.html
└── static/
    ├── css/style.css
    └── js/main.js
```

---

## How the Analyzer Works (No AI)

| Step | Method |
|---|---|
| Document type detection | Weighted keyword matching across **20 categories** |
| Risk scoring | 30+ weighted regex patterns → 0–100 score |
| Key point extraction | **20 dedicated detectors** (billing, privacy, arbitration, IP, SLA, health data, non-compete, etc.) |
| Red flag detection | **22 specific patterns** for aggressive or unusual clauses |
| Before-signing checklist | Contextual — only items relevant to this specific document |

---

## Supported Document Types (20)

Insurance · Loan/Credit · Mortgage · Investment/Securities · Lease/Rental ·
Employment · SaaS/Software · Mobile App · Cloud Services · Open Source ·
E-Commerce · Subscription · Streaming/Media · Travel/Hospitality ·
Telecommunications · Healthcare/Medical · Financial Advisory ·
Privacy Policy · Social Media · Website Terms of Use

---

## File Upload Support

| Format | Method |
|---|---|
| `.txt` | Direct text read |
| `.pdf` | Text extraction via PyPDF2; OCR fallback for scanned PDFs |
| `.png`, `.jpg`, `.jpeg`, `.webp`, `.tiff`, `.bmp` | OCR via Tesseract |

---

## Production Notes

- The Docker image runs as a **non-root user** for security
- Uses **Gunicorn** (2 workers) instead of Flask's dev server
- Resource limits: 512MB RAM max, 128MB reserved
- An optional **Nginx** reverse proxy block is included (commented) in `docker-compose.yml`
- Generate a strong `SECRET_KEY`:
  ```bash
  python -c "import secrets; print(secrets.token_hex(32))"
  ```

---

## Disclaimer

This tool provides a general overview only. It is **not legal advice**.
For important agreements, always consult a qualified legal professional.
