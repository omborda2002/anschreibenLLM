import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def load_personal_info() -> dict:
    path = BASE_DIR / "config" / "personal-info.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# Map the UI/CV-variant key to its plain-text CV file.
CV_FILES = {
    "aiml": "cv_aiml.txt",
    "ds": "cv_datascience.txt",
}


def load_cv(variant: str = "aiml") -> str:
    """Load the plain-text CV for the given variant.

    variant: "aiml" (AI/ML Engineer roles) or "ds" (Data Science roles).
    Falls back to the AI/ML CV for any unknown key.
    """
    filename = CV_FILES.get(variant, CV_FILES["aiml"])
    path = BASE_DIR / "config" / filename
    with open(path, "r", encoding="utf-8") as f:
        return f.read()