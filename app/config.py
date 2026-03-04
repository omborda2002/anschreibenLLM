import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

def load_personal_info() -> dict:
    path = BASE_DIR / "config" / "personal-info.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_cv() -> str:
    path = BASE_DIR / "config" / "cv.txt"
    with open(path, "r", encoding="utf-8") as f:
        return f.read()