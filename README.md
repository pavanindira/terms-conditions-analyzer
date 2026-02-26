# ⚖️ Terms & Conditions Analyzer — Flask + Jinja2

A fully **rule-based** T&C analyzer with no AI, no external APIs, and no
data leaving your machine. Built with Flask, Jinja2 templates, and vanilla
CSS / JS.

---

## Project Structure

```
tc_app/
├── app.py                  ← Flask routes
├── analyzer.py             ← Rule-based analysis engine (no AI)
├── requirements.txt
├── templates/
│   ├── base.html           ← Shared layout (navbar, flash messages, footer)
│   ├── index.html          ← Home / input page
│   ├── result.html         ← Analysis results page
│   └── about.html          ← How it works
└── static/
    ├── css/style.css       ← All styles (dark gold theme)
    └── js/main.js          ← Tabs, counters, file drop, animations
```

---

## Setup & Run

```bash
# 1. Create virtual environment
python -m venv venv
source venv/bin/activate        # macOS / Linux
venv\Scripts\activate           # Windows

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
python app.py
```

Open **http://localhost:5050** in your browser.

---

## How the Analyzer Works (No AI)

| Step | Method |
|------|--------|
| Document type detection | Weighted keyword matching (regex) across 10 document categories |
| Risk scoring | 20+ weighted regex patterns for aggressive clauses, summed to 0-100 |
| Key point extraction | 11 dedicated detector functions, one per category |
| Red flag detection | 14 specific patterns for concerning clauses |
| Before-signing checklist | Contextual — only items relevant to detected clauses appear |

---

## Supported Document Types

- Insurance Policies
- SaaS / Software License Agreements
- Mobile App Terms of Service
- E-Commerce / Shopping Terms
- Employment Contracts
- Privacy Policies
- Financial Services Agreements
- Streaming / Media Subscriptions
- Social Media Platform Terms
- Website Terms of Use

---

## Disclaimer

This tool provides a general overview only. It is **not legal advice**.
For important agreements, always consult a qualified legal professional.
