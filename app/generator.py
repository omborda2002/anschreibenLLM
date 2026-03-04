import os
import json
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()


def md_to_html_bold(text: str) -> str:
    """Convert **word** markdown to <strong>word</strong> HTML."""
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)


def generate_all(
    personal_info: dict,
    cv_text: str,
    job_posting: str,
    language: str,
    tone: str,
) -> dict:

    llm = ChatGroq(
        model="llama-3.3-70b-versatile",
        api_key=os.getenv("GROQ_API_KEY"),
        temperature=0.8,
    )

    if language == "DE":
        greeting = "Sehr geehrte Damen und Herren,"
        closing = "Mit freundlichen Grüßen,"
        tone_instruction = "förmlich und direkt" if tone == "formal" else "professionell und persönlich"
        lang_instruction = "Schreibe auf Deutsch. Klar, präzise, wie ein echter erfahrener Bewerber."
        banned_phrases = """
VERBOTENE PHRASEN — diese dürfen NICHT vorkommen, nicht einmal sinngemäß:
- "ich bin überzeugt"
- "ich bin begeistert"  
- "ich bin beeindruckt"
- "ich bin sicher"
- "eine gute Passung"
- "wertvolles Teammitglied"
- "außergewöhnlich"
- "ich freue mich darauf"
- "meine Fähigkeiten und Erfahrungen"
- Irgendwas mit "Passion" oder "Leidenschaft"
"""
    else:
        greeting = "Dear Hiring Team,"
        closing = "Yours sincerely,"
        tone_instruction = "formal and direct" if tone == "formal" else "professional and personal"
        lang_instruction = "Write in English. Clear, direct, like a real experienced applicant."
        banned_phrases = """
BANNED PHRASES — must not appear, not even paraphrased:
- "I am excited"
- "I am passionate"
- "I am confident"
- "I am impressed"
- "great fit"
- "valuable team member"
- "extraordinary"
- "I look forward to"
- "my skills and experience"
- Anything with "passion"
"""

    prompt = ChatPromptTemplate.from_template("""
{lang_instruction}

TASK 1 — Extract from job posting:
- company_name
- role (exact job title)
- job_type: one of "Werkstudent", "Teilzeit", "Vollzeit", "Praktikum"

TASK 2 — Write 3 cover letter body paragraphs.
No greeting. No closing. Just the 3 paragraphs.

Tone: {tone_instruction}

{banned_phrases}

WRITING RULES:
- Use <strong>term</strong> (HTML, NOT markdown **) to bold exactly 2 specific technical terms from the CV that match the job
- Mention company name maximum ONCE
- Never start 2 consecutive sentences with "Ich" or "I"
- No em dashes (—)
- No bullet points
- No padding sentences — every sentence must add value
- Be specific: name actual projects, tools, numbers from the CV
- Paragraph 1: what you bring technically (specific, concrete)
- Paragraph 2: relevant project or experience that proves it
- Paragraph 3: brief, forward-looking — one sentence on fit, one on next step

CV:
{cv_text}

Name: {full_name}
University: {university}
Degree: {degree}

Job posting:
{job_posting}

Return ONLY valid JSON, no markdown, no code fences:
{{
  "company_name": "...",
  "role": "...",
  "job_type": "...",
  "letter_body": "paragraph1\\n\\nparagraph2\\n\\nparagraph3"
}}
""")

    chain = prompt | llm
    response = chain.invoke({
        "lang_instruction": lang_instruction,
        "tone_instruction": tone_instruction,
        "banned_phrases": banned_phrases,
        "cv_text": cv_text,
        "full_name": personal_info["full_name"],
        "university": personal_info["university"],
        "degree": personal_info["degree"],
        "job_posting": job_posting,
    })

    text = response.content.strip()
    text = text.replace("```json", "").replace("```", "").strip()

    try:
        data = json.loads(text)
        data["letter_body"] = md_to_html_bold(data.get("letter_body", ""))
    except json.JSONDecodeError:
        data = {
            "company_name": "Unbekanntes Unternehmen",
            "role": "Position",
            "job_type": "Vollzeit",
            "letter_body": md_to_html_bold(text),
        }

    data["greeting"] = greeting
    data["closing_phrase"] = closing
    return data