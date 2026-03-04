# Feder — Anschreiben Generator

Paste a job posting, get a DIN-style cover letter PDF in seconds.
Powered by FastAPI, LangChain, and Groq.

## Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Add your Groq API key to `.env`:
```
GROQ_API_KEY=your_key_here
```

Fill in your details in `config/personal-info.json` and paste your CV into `config/cv.txt`.

## Run

```bash
uvicorn main:app --reload
```

Open `http://localhost:8000`, paste a job posting, click Generate.

## Structure

```
├── app/
│   ├── config.py       loads personal info + CV
│   ├── generator.py    LangChain + Groq — extracts job info + writes letter
│   └── pdf.py          renders HTML template to PDF via WeasyPrint
├── config/
│   ├── personal-info.json
│   └── cv.txt
├── form/index.html     browser UI
├── template/anschreiben.html   DIN 5008 PDF template
├── main.py             FastAPI server
└── requirements.txt
```