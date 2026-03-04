import re
from fastapi import FastAPI, Form
from fastapi.responses import Response, HTMLResponse
from pathlib import Path
from app.config import load_personal_info, load_cv
from app.generator import generate_all
from app.pdf import render_pdf

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent


@app.get("/", response_class=HTMLResponse)
async def serve_form():
    with open(BASE_DIR / "form" / "index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/generate")
async def generate(
    job_posting: str = Form(...),
    language: str = Form("DE"),
    tone: str = Form("formal"),
):
    personal_info = load_personal_info()
    cv_text = load_cv()

    result = generate_all(
        personal_info=personal_info,
        cv_text=cv_text,
        job_posting=job_posting,
        language=language,
        tone=tone,
    )

    pdf_bytes = render_pdf(
        personal_info=personal_info,
        company_name=result.get("company_name", ""),
        role=result.get("role", ""),
        job_type=result.get("job_type", "Vollzeit"),
        greeting=result.get("greeting", ""),
        letter_body=result.get("letter_body", ""),
        closing_phrase=result.get("closing_phrase", ""),
        language=language,
    )

    def slugify(text):
        text = text.replace(" ", "_")
        text = re.sub(r'[^\x00-\x7F]', '', text)
        text = re.sub(r'[^a-zA-Z0-9_\-]', '', text)
        return text or "unknown"

    filename = f"Anschreiben_{slugify(result.get('company_name','Company'))}_{slugify(result.get('role','Role'))}.pdf"

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )