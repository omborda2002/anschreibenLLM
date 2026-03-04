from pathlib import Path
from datetime import datetime
from weasyprint import HTML
import re

BASE_DIR = Path(__file__).resolve().parent.parent
TEMPLATE_PATH = BASE_DIR / "template" / "anschreiben.html"


def shorten_url(url: str) -> str:
    """Strip https://, http://, www. for display."""
    url = url.strip()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = url.rstrip('/')
    return url


def ensure_https(url: str) -> str:
    """Ensure URL has https:// prefix for href."""
    url = url.strip()
    if url and not url.startswith('http'):
        return 'https://' + url
    return url


def render_pdf(
    personal_info: dict,
    company_name: str,
    role: str,
    job_type: str,
    greeting: str,
    letter_body: str,
    closing_phrase: str,
    language: str,
) -> bytes:

    now = datetime.now()
    if language == "DE":
        months_de = ["Januar", "Februar", "März", "April", "Mai", "Juni",
                     "Juli", "August", "September", "Oktober", "November", "Dezember"]
        date_str = f"{now.day}. {months_de[now.month - 1]} {now.year}"
    else:
        date_str = now.strftime("%B %d, %Y")

    portfolio = personal_info.get("portfolio", "")
    github = personal_info.get("github", "")
    linkedin = personal_info.get("linkedin", "")

    # Convert paragraph breaks to HTML — preserve <strong> tags
    paragraphs = letter_body.strip().split("\n\n")
    body_html = "".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())

    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        template_str = f.read()

    replacements = {
        "{{full_name}}": personal_info["full_name"],
        "{{street}}": personal_info["street"],
        "{{city}}": personal_info["city"],
        "{{phone}}": personal_info["phone"],
        "{{email}}": personal_info["email"],
        # Display versions (short)
        "{{portfolio}}": shorten_url(portfolio),
        "{{github}}": shorten_url(github),
        "{{linkedin}}": shorten_url(linkedin),
        # Full href versions
        "{{portfolio_full}}": ensure_https(portfolio),
        "{{github_full}}": ensure_https(github),
        "{{linkedin_full}}": ensure_https(linkedin),
        "{{company_name}}": company_name,
        "{{date}}": date_str,
        "{{role}}": role,
        "{{job_type}}": job_type,
        "{{greeting}}": greeting,
        "{{letter_body}}": body_html,
        "{{closing_phrase}}": closing_phrase,
    }

    html_content = template_str
    for placeholder, value in replacements.items():
        html_content = html_content.replace(placeholder, value)

    return HTML(string=html_content, base_url=str(BASE_DIR)).write_pdf()