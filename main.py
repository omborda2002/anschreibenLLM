import re
import os
import secrets
import hashlib
from fastapi import FastAPI, Form, Request
from fastapi.responses import Response, HTMLResponse, RedirectResponse
from pathlib import Path
from starlette.middleware.sessions import SessionMiddleware
from app.config import load_personal_info, load_cv
from app.generator import generate_all
from app.pdf import render_pdf
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
BASE_DIR = Path(__file__).resolve().parent

SECRET_KEY = os.getenv("SECRET_KEY", "feder-fallback-secret-key-change-me")
APP_PASSWORD = os.getenv("APP_PASSWORD", "Om@12345")

app.add_middleware(
    SessionMiddleware,
    secret_key=SECRET_KEY,
    max_age=7 * 24 * 3600,  # 7 days
    https_only=True,
    same_site="lax",
)


def is_authenticated(request: Request) -> bool:
    return request.session.get("authenticated") is True


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    if is_authenticated(request):
        return RedirectResponse("/", status_code=302)
    with open(BASE_DIR / "form" / "login.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/login")
async def login(request: Request, password: str = Form(...)):
    if secrets.compare_digest(
        hashlib.sha256(password.encode()).hexdigest(),
        hashlib.sha256(APP_PASSWORD.encode()).hexdigest(),
    ):
        request.session["authenticated"] = True
        return RedirectResponse("/", status_code=302)

    with open(BASE_DIR / "form" / "login.html", "r", encoding="utf-8") as f:
        content = f.read()
    content = content.replace('id="error-msg"', 'id="error-msg" style="display:block"')
    return HTMLResponse(content, status_code=401)


@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)


@app.get("/", response_class=HTMLResponse)
async def serve_form(request: Request):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)
    with open(BASE_DIR / "form" / "index.html", "r", encoding="utf-8") as f:
        return f.read()


@app.post("/generate")
async def generate(
    request: Request,
    job_posting: str = Form(...),
    language: str = Form("DE"),
    tone: str = Form("formal"),
):
    if not is_authenticated(request):
        return RedirectResponse("/login", status_code=302)

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
