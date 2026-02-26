from flask import (
    Flask, render_template, request, redirect, url_for,
    flash, jsonify, send_file, session
)
from analyzer import analyze, AnalysisResult
from llm import enhance_with_llm, ollama_status, LLMInsight
import io, os, uuid

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, "templates"),
    static_folder=os.path.join(BASE_DIR, "static"),
)
app.secret_key = os.environ.get("SECRET_KEY", "tc-analyzer-dev-key")

# ── In-memory result cache ───────────────────────────────────────────────────
_cache: dict = {}
_MAX_CACHE = 50

def _cache_put(result: AnalysisResult, insight: LLMInsight) -> str:
    key = str(uuid.uuid4())
    if len(_cache) >= _MAX_CACHE:
        del _cache[next(iter(_cache))]
    _cache[key] = {"result": result.to_dict(), "insight": _insight_to_dict(insight)}
    return key

def _cache_get(key: str):
    entry = _cache.get(key)
    if not entry:
        return None, None
    result  = AnalysisResult.from_dict(entry["result"])
    insight = _insight_from_dict(entry["insight"])
    return result, insight

def _insight_to_dict(i: LLMInsight) -> dict:
    return {
        "plain_summary":    i.plain_summary,
        "overall_verdict":  i.overall_verdict,
        "negotiation_tips": i.negotiation_tips,
        "plain_red_flags":  i.plain_red_flags,
        "user_questions":   i.user_questions,
        "model_used":       i.model_used,
        "enhanced":         i.enhanced,
    }

def _insight_from_dict(d: dict) -> LLMInsight:
    return LLMInsight(**d)

# ── File type helpers ────────────────────────────────────────────────────────
ALLOWED_TEXT  = {".txt"}
ALLOWED_PDF   = {".pdf"}
ALLOWED_IMAGE = {".png", ".jpg", ".jpeg", ".webp", ".tiff", ".bmp", ".gif"}
ALL_ALLOWED   = ALLOWED_TEXT | ALLOWED_PDF | ALLOWED_IMAGE

def _ext(fn: str) -> str:
    return os.path.splitext(fn.lower())[1]

# ── Text extractors ──────────────────────────────────────────────────────────

def _from_txt(raw: bytes) -> str:
    return raw.decode("utf-8", errors="ignore")

def _from_pdf(raw: bytes) -> str:
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(raw))
        text = "\n".join(p.extract_text() or "" for p in reader.pages)
        return text if len(text.strip()) >= 100 else _pdf_ocr_fallback(raw)
    except ImportError:
        flash("PyPDF2 not installed.", "warning"); return ""
    except Exception as e:
        flash(f"PDF error: {e}", "danger"); return ""

def _pdf_ocr_fallback(raw: bytes) -> str:
    try:
        from pdf2image import convert_from_bytes
        import pytesseract
        return "\n".join(pytesseract.image_to_string(p) for p in convert_from_bytes(raw, dpi=200))
    except Exception as e:
        flash(f"PDF OCR failed: {e}", "warning"); return ""

def _from_image(raw: bytes) -> str:
    try:
        import pytesseract
        from PIL import Image
        img = Image.open(io.BytesIO(raw))
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        text = pytesseract.image_to_string(img)
        if not text.strip():
            flash("No text extracted from image — check that it is clear and legible.", "warning")
        return text
    except Exception as e:
        flash(f"Image OCR failed: {e}", "danger"); return ""

def _extract_text(filename: str, raw: bytes) -> str:
    ext = _ext(filename)
    if ext in ALLOWED_TEXT:  return _from_txt(raw)
    if ext in ALLOWED_PDF:   return _from_pdf(raw)
    if ext in ALLOWED_IMAGE: return _from_image(raw)
    flash(f"Unsupported file type: {ext}", "danger"); return ""

# ── Web routes ───────────────────────────────────────────────────────────────

@app.route("/", methods=["GET"])
def index():
    llm_info = ollama_status()
    return render_template("index.html", llm=llm_info)


@app.route("/analyze", methods=["POST"])
def analyze_doc():
    text = ""

    upload = request.files.get("file")
    if upload and upload.filename:
        ext = _ext(upload.filename)
        if ext not in ALL_ALLOWED:
            flash(f"Unsupported file type '{ext}'.", "danger")
            return redirect(url_for("index"))
        text = _extract_text(upload.filename, upload.read())
        source_label = upload.filename
    else:
        text = request.form.get("text", "").strip()
        source_label = "Pasted text"

    if not text or not text.strip():
        flash("No text found. Please paste text or upload a readable file.", "danger")
        return redirect(url_for("index"))
    if len(text.strip()) < 50:
        flash("Document is too short to analyze.", "warning")
        return redirect(url_for("index"))

    try:
        result = analyze(text)
    except Exception as e:
        flash(f"Analysis error: {e}", "danger")
        return redirect(url_for("index"))

    # ── LLM enhancement (non-blocking — falls back gracefully) ──────────────
    use_llm = request.form.get("use_llm", "on") != "off"
    insight = LLMInsight()
    if use_llm:
        try:
            insight = enhance_with_llm(
                text=text,
                doc_type=result.document_type,
                risk_level=result.risk_level,
                risk_score=result.risk_score,
            )
        except Exception as e:
            app.logger.warning("LLM enhancement failed: %s", e)

    cache_key = _cache_put(result, insight)
    session["result_key"] = cache_key

    return render_template(
        "result.html",
        r=result,
        llm=insight,
        source=source_label,
        cache_key=cache_key,
    )


# ── Export routes ────────────────────────────────────────────────────────────

def _get_cached() -> tuple:
    key = request.args.get("key") or session.get("result_key")
    return _cache_get(key) if key else (None, None)


@app.route("/export/pdf")
def export_pdf():
    result, insight = _get_cached()
    if not result:
        flash("No analysis found — please analyze a document first.", "warning")
        return redirect(url_for("index"))
    from exporters import export_pdf as gen
    return send_file(io.BytesIO(gen(result, insight)),
        mimetype="application/pdf", as_attachment=True,
        download_name="tc_analysis_report.pdf")

@app.route("/export/summary")
def export_summary():
    result, insight = _get_cached()
    if not result:
        flash("No analysis found.", "warning"); return redirect(url_for("index"))
    from exporters import export_summary_pdf as gen
    return send_file(io.BytesIO(gen(result, insight)),
        mimetype="application/pdf", as_attachment=True,
        download_name="tc_summary.pdf")

@app.route("/export/word")
def export_word():
    result, insight = _get_cached()
    if not result:
        flash("No analysis found.", "warning"); return redirect(url_for("index"))
    from exporters import export_word as gen
    return send_file(io.BytesIO(gen(result, insight)),
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        as_attachment=True, download_name="tc_analysis_report.docx")

@app.route("/export/csv")
def export_csv():
    result, insight = _get_cached()
    if not result:
        flash("No analysis found.", "warning"); return redirect(url_for("index"))
    from exporters import export_csv as gen
    return send_file(io.BytesIO(gen(result, insight)),
        mimetype="text/csv", as_attachment=True,
        download_name="tc_analysis.csv")


# ── REST API ─────────────────────────────────────────────────────────────────

@app.route("/api/health", methods=["GET"])
def api_health():
    llm = ollama_status()
    return jsonify({"status": "ok", "version": "3.0", "llm": llm})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Analyze a T&C document and return structured JSON.

    Accepts:
      • application/json    → { "text": "...", "use_llm": true }
      • multipart/form-data → file field or text field
    """
    text, use_llm = "", True
    ct = request.content_type or ""

    if "application/json" in ct:
        body = request.get_json(silent=True) or {}
        text = body.get("text", "").strip()
        use_llm = body.get("use_llm", True)
        if not text:
            return jsonify({"error": "JSON body must contain a 'text' field."}), 400
    elif "multipart/form-data" in ct or "application/x-www-form-urlencoded" in ct:
        upload = request.files.get("file")
        if upload and upload.filename:
            ext = _ext(upload.filename)
            if ext not in ALL_ALLOWED:
                return jsonify({"error": f"Unsupported file type: {ext}"}), 415
            text = _extract_text(upload.filename, upload.read())
        else:
            text = request.form.get("text", "").strip()
        use_llm = request.form.get("use_llm", "true").lower() != "false"
    else:
        text = request.get_data(as_text=True).strip()

    if not text:
        return jsonify({"error": "No text provided."}), 400
    if len(text) < 50:
        return jsonify({"error": "Text too short (minimum 50 characters)."}), 400

    try:
        result = analyze(text)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    response_data = result.to_dict()

    if use_llm:
        try:
            insight = enhance_with_llm(
                text=text,
                doc_type=result.document_type,
                risk_level=result.risk_level,
                risk_score=result.risk_score,
            )
            response_data["llm_insight"] = _insight_to_dict(insight)
        except Exception as e:
            response_data["llm_insight"] = {"enhanced": False, "error": str(e)}

    return jsonify(response_data), 200


@app.route("/api/llm/status", methods=["GET"])
def api_llm_status():
    return jsonify(ollama_status())


@app.route("/api/docs")
def api_docs():
    llm = ollama_status()
    return render_template("api.html", llm=llm)


@app.route("/about")
def about():
    return render_template("about.html")


if __name__ == "__main__":
    app.run(debug=True, port=5050)
