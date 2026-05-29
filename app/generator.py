import os
import json
import re
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()


# ---------------------------------------------------------------------------
# Humanizer rules
#
# Distilled from the "humanizer" Claude skill (~/.claude/skills/humanizer,
# based on Wikipedia's "Signs of AI writing"). The cover letter is written
# by Groq's Llama model, which cannot load a Claude skill at runtime, so the
# skill's anti-AI-pattern rules are embedded directly in the prompt instead.
# These are applied to EVERY generated letter (single-pass humanization).
# ---------------------------------------------------------------------------

HUMANIZER_RULES_EN = """
HUMANIZER RULES — write like a real person, not an AI. These are mandatory:
- No em dashes (—) and no en dashes (–). Use a comma, a period, or a new sentence.
- No curly/smart quotes (" " ' '). Use straight quotes (" and ') only.
- Ban these AI-vocabulary words entirely: additionally, moreover, furthermore, crucial, pivotal, delve, leverage, robust, seamless, showcase, underscore, testament, landscape (figurative), tapestry, vibrant, foster, garner, intricate, realm, harness, spearhead, holistic, synergy, cutting-edge, groundbreaking, world-class, ever-evolving.
- Do not avoid simple verbs. Write "is / are / has / built / led", not "serves as / stands as / boasts / represents a / plays a key role in".
- No negative parallelism: never "not only X but also Y" or "it is not just X, it is Y".
- No rule-of-three padding: do not stack three adjectives or three nouns to sound complete.
- No superficial "-ing" tails on sentences (highlighting, ensuring, reflecting, showcasing, demonstrating my fit).
- No false ranges ("from X to Y") unless X and Y are a real scale.
- No filler: cut "in order to" (use "to"), "due to the fact that" (use "because"), "it is important to note that", "with a strong focus on".
- No hedging stacks ("could potentially possibly").
- No generic upbeat conclusion about the future or "what lies ahead".
- Vary sentence length and rhythm. Some short. Some longer. Do not make every sentence the same shape.
- Prefer concrete specifics: real project names, tools, and numbers from the CV over abstract claims.
"""

HUMANIZER_RULES_DE = """
HUMANIZER-REGELN — schreibe wie ein echter Mensch, nicht wie eine KI. Verbindlich:
- Keine Gedankenstriche (— oder –). Nutze Komma, Punkt oder einen neuen Satz.
- Keine typografischen Anführungszeichen (" " ‚ '). Nur gerade Anführungszeichen (" und ').
- Diese KI-Floskeln sind komplett verboten: darüber hinaus, zudem, ferner, des Weiteren, maßgeblich, wegweisend, nahtlos, ganzheitlich, vielfältig, robust, Synergie, im Bereich der, in der heutigen schnelllebigen Welt, Landschaft (im übertragenen Sinn).
- Keine aufgeblähten Konstruktionen statt einfacher Verben. Schreibe "ist / sind / hat / habe gebaut / habe geleitet", nicht "fungiert als / stellt dar / spielt eine zentrale Rolle".
- Keine "nicht nur ... sondern auch"-Konstruktionen.
- Keine Dreierlisten: nicht drei Adjektive oder drei Substantive aneinanderreihen, um vollständig zu klingen.
- Keine Partizipialfloskeln am Satzende (unterstreichend, gewährleistend, was meine Eignung zeigt).
- Kein Füllmaterial: streiche "aufgrund der Tatsache, dass" (nutze "weil"), "es ist wichtig zu erwähnen, dass", "mit einem starken Fokus auf".
- Kein gestapeltes Abschwächen ("könnte möglicherweise eventuell").
- Kein generisches optimistisches Schlusswort über die Zukunft.
- Variiere Satzlänge und Rhythmus. Mal kurz, mal länger. Nicht jeder Satz gleich gebaut.
- Konkret bleiben: echte Projektnamen, Tools und Zahlen aus dem Lebenslauf statt abstrakter Aussagen.
"""


def md_to_html_bold(text: str) -> str:
    """Convert **word** markdown to <strong>word</strong> HTML."""
    return re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)


def _normalize_body(raw: str) -> str:
    """Turn a raw letter body into clean paragraphs separated by blank lines.

    The model is inconsistent: it may use the escape sequence \\n\\n, real line
    breaks, or both. We unescape, split on blank lines, and collapse stray
    single line breaks inside a paragraph into spaces so pdf.py (which splits on
    "\\n\\n") always gets clean paragraphs.
    """
    raw = (raw.replace('\\n', '\n').replace('\\t', ' ')
              .replace('\\"', '"').replace("\\'", "'").replace('\\\\', '\\'))
    paras = [re.sub(r'\s*\n\s*', ' ', p).strip()
             for p in re.split(r'\n\s*\n', raw) if p.strip()]
    return '\n\n'.join(paras)


def parse_letter_response(text: str) -> dict:
    """Parse the model's JSON reliably, recovering from invalid JSON.

    The model often emits real line breaks inside the letter_body string, which
    makes the whole payload invalid JSON. Rather than dumping the raw JSON blob
    into the PDF, we fall back to field-by-field extraction so the company, role
    and letter still come through.
    """
    text = text.replace('```json', '').replace('```', '').strip()

    try:
        data = json.loads(text)
        return {
            'company_name': (data.get('company_name') or '').strip(),
            'role': (data.get('role') or '').strip(),
            'job_type': (data.get('job_type') or 'Vollzeit').strip(),
            'letter_body': _normalize_body(data.get('letter_body', '')),
        }
    except (json.JSONDecodeError, AttributeError, TypeError):
        pass

    def grab(field: str) -> str:
        m = re.search(r'"%s"\s*:\s*"(.*?)"' % field, text, re.S)
        return m.group(1).strip() if m else ''

    body_m = re.search(r'"letter_body"\s*:\s*"(.*)"\s*}?\s*$', text, re.S)
    body = body_m.group(1) if body_m else text
    return {
        'company_name': grab('company_name') or 'Unbekanntes Unternehmen',
        'role': grab('role') or 'Position',
        'job_type': grab('job_type') or 'Vollzeit',
        'letter_body': _normalize_body(body),
    }


def sanitize_humanized(text: str) -> str:
    """Deterministic safety net for the humanizer rules.

    The prompt asks the model to avoid em dashes and curly quotes, but that is
    not 100% reliable, so we strip them here too. Em/en dashes become commas;
    smart quotes become straight quotes. Spacing around commas is normalised
    so the replacements never leave " ," or doubled commas behind.
    """
    text = text.replace("—", ",").replace("–", ",")
    text = (text.replace("“", '"').replace("”", '"')
                .replace("‘", "'").replace("’", "'"))
    text = re.sub(r"\s+,", ",", text)          # no space before a comma
    text = re.sub(r",(?=\S)", ", ", text)      # ensure one space after a comma
    text = re.sub(r"(?:,\s*){2,}", ", ", text)  # collapse repeated commas
    text = re.sub(r"[ \t]{2,}", " ", text)      # collapse runs of spaces
    return text


# Words the prompt bans but the model still leaks. Deleted words are dropped
# outright; swapped words get a plainer synonym. Applied deterministically so
# these AI tells never reach the PDF.
_VOCAB_DELETE = ["seamlessly", "effortlessly", "holistically"]
_VOCAB_SWAP = {
    "seamless": "smooth", "cutting-edge": "advanced", "cutting edge": "advanced",
    "robust": "reliable", "vibrant": "active", "groundbreaking": "novel",
    "leverage": "use", "leveraging": "using", "leverages": "uses", "leveraged": "used",
    "utilize": "use", "utilizing": "using", "utilizes": "uses", "utilized": "used",
    "showcase": "show", "showcases": "shows", "showcasing": "showing", "showcased": "showed",
    "delve into": "go into",
}


def scrub_ai_vocab(text: str) -> str:
    """Remove/replace high-frequency AI-vocabulary words the model leaks."""
    for w in _VOCAB_DELETE:
        text = re.sub(r"\b" + re.escape(w) + r"\b", "", text, flags=re.I)
    for a, b in _VOCAB_SWAP.items():
        text = re.sub(r"\b" + re.escape(a) + r"\b", b, text, flags=re.I)
    text = re.sub(r"\s+([.,;:])", r"\1", text)   # no space before punctuation
    text = re.sub(r"[ \t]{2,}", " ", text)
    # Recapitalise the first letter of each sentence (a swap may have lowered it)
    text = re.sub(r"(^|[.!?]\s+|\n)([a-z])",
                  lambda m: m.group(1) + m.group(2).upper(), text)
    return text


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
        temperature=0.6,
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
- "ich glaube"
- "ein starker Kandidat" / "ein idealer Kandidat"
- "um nur einige zu nennen"
- Irgendwas mit "Passion" oder "Leidenschaft"
"""
        humanizer_rules = HUMANIZER_RULES_DE
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
- "I believe"
- "strong candidate" / "ideal candidate" / "perfect candidate"
- "to name a few"
- "make me a strong fit" / "make me an ideal fit"
- Anything with "passion"
"""
        humanizer_rules = HUMANIZER_RULES_EN

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

{humanizer_rules}

WRITING RULES:
- Use <strong>term</strong> (HTML, NOT markdown **) to bold exactly 2 specific technical terms from the CV that match the job
- Mention company name maximum ONCE
- Never start 2 consecutive sentences with "Ich" or "I"
- No bullet points
- LENGTH: each paragraph is 2 to 3 sentences. The whole letter stays under 200 words.
- No padding sentences. Cut any sentence that only restates that something "worked", "produced results", "was successful", or "was completed on time". Cut "I was able to...", "this demonstrates my ability to...", "this showcases my expertise in...".
- Do not reuse the same noun phrase twice (e.g. do not say "production-ready systems" or "large amounts of data" more than once).
- Be specific: name actual projects, tools, numbers from the CV
- Anchor the letter to THIS posting: pick the 2-3 concrete requirements or technologies named in the job posting and answer them with real evidence from the CV. If the posting names a stack (e.g. TypeScript, a framework, a cloud, a model provider), reference the matching CV experience explicitly.
- Paragraph 1: open with your single strongest, most specific match to this exact role — a real project, production system, or measurable result. Do NOT open with a generic summary like "I bring a strong foundation in...".
- Paragraph 2: a concrete project or work result that proves you can do the core task in the posting (name the project, the tools, and a number or outcome).
- Paragraph 3: brief, forward-looking — one sentence connecting your background to what the team is building, one sentence on the next step. No generic "I believe I am a strong candidate" wording.

CV:
{cv_text}

Name: {full_name}
University: {university}
Degree: {degree}

Job posting:
{job_posting}

Return ONLY valid JSON, no markdown, no code fences.
CRITICAL: "letter_body" must be a SINGLE-LINE JSON string. Separate the three
paragraphs ONLY with the two-character escape \\n\\n. Do NOT put real line
breaks anywhere inside the JSON.
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
        "humanizer_rules": humanizer_rules,
        "cv_text": cv_text,
        "full_name": personal_info["full_name"],
        "university": personal_info["university"],
        "degree": personal_info["degree"],
        "job_posting": job_posting,
    })

    data = parse_letter_response(response.content.strip())
    data["letter_body"] = md_to_html_bold(scrub_ai_vocab(sanitize_humanized(data["letter_body"])))
    data["greeting"] = greeting
    data["closing_phrase"] = closing
    return data