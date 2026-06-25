import unicodedata
import re

def normalize(text: str) -> str:
    if not text:
        return ''
    text = unicodedata.normalize('NFKC', text)
    text = text.casefold()
    text = re.sub(r'\s+', ' ', text).strip()
    return text