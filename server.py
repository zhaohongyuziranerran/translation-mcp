"""Translation MCP Server - Multi-language translation hub.

10 tools: translate_text, translate_batch, translate_file, detect_language,
list_languages, translate_html, translate_json, translate_markdown,
compare_translations, transliterate
"""

import json
import os
import re
from typing import Optional

from fastmcp import FastMCP

mcp = FastMCP(
    "translation-mcp",
    instructions="Multi-language translation MCP. Google Translate (free), DeepL, and local LLM via vLLM. Translate text, files, HTML, JSON, Markdown. Batch processing. E-commerce product description translation. Auto language detection."
)

# Language codes
LANGUAGES = {
    "zh-CN": "Chinese Simplified",
    "zh-TW": "Chinese Traditional",
    "en": "English", "ja": "Japanese", "ko": "Korean",
    "fr": "French", "de": "German", "es": "Spanish",
    "pt": "Portuguese", "it": "Italian", "ru": "Russian",
    "ar": "Arabic", "hi": "Hindi", "th": "Thai",
    "vi": "Vietnamese", "id": "Indonesian", "ms": "Malay",
    "tr": "Turkish", "nl": "Dutch", "pl": "Polish",
    "sv": "Swedish", "da": "Danish", "fi": "Finnish",
    "no": "Norwegian", "cs": "Czech", "hu": "Hungarian",
    "el": "Greek", "he": "Hebrew", "ro": "Romanian",
    "uk": "Ukrainian", "bg": "Bulgarian", "hr": "Croatian",
}


def _google_translate(text: str, target: str, source: str = "auto") -> str:
    """Translate using Google Translate (free, no API key needed)."""
    try:
        from deep_translator import GoogleTranslator
        translator = GoogleTranslator(source=source if source != "auto" else "auto", target=target)
        result = translator.translate(text)
        return result
    except ImportError:
        return _http_translate(text, target, source)


def _http_translate(text: str, target: str, source: str = "auto") -> str:
    """Fallback HTTP-based translation."""
    import httpx
    import urllib.parse
    base_url = "https://translate.googleapis.com/translate_a/single"
    params = {
        "client": "gtx",
        "sl": source if source != "auto" else "auto",
        "tl": target,
        "dt": "t",
        "q": text
    }
    try:
        resp = httpx.get(base_url, params=params, timeout=15)
        data = resp.json()
        result = "".join([s[0] for s in data[0] if s[0]])
        return result
    except Exception:
        return None


@mcp.tool()
def list_languages() -> str:
    """List all supported languages with codes."""
    return json.dumps({
        "total": len(LANGUAGES),
        "languages": LANGUAGES
    }, ensure_ascii=False)


@mcp.tool()
def detect_language(text: str) -> str:
    """Auto-detect the language of input text.
    
    Args:
        text: Text to detect language for
    """
    try:
        from deep_translator import GoogleTranslator
        from langdetect import detect
        lang_code = detect(text)
        lang_name = LANGUAGES.get(lang_code, lang_code)
        return json.dumps({
            "detected_lang": lang_code,
            "language": lang_name,
            "confidence": "high",
            "text_preview": text[:100]
        }, ensure_ascii=False)
    except ImportError:
        # Fallback: simple char-based detection
        cjk = len(re.findall(r'[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]', text))
        arabic = len(re.findall(r'[\u0600-\u06ff]', text))
        cyrillic = len(re.findall(r'[\u0400-\u04ff]', text))
        total = len(text) or 1

        if cjk / total > 0.3:
            detected = "zh-CN"
        elif arabic / total > 0.3:
            detected = "ar"
        elif cyrillic / total > 0.3:
            detected = "ru"
        else:
            detected = "en"

        return json.dumps({
            "detected_lang": detected,
            "language": LANGUAGES.get(detected, detected),
            "method": "heuristic",
            "cjk_ratio": round(cjk / total, 3),
            "text_preview": text[:100]
        }, ensure_ascii=False)


@mcp.tool()
def translate_text(
    text: str,
    target_lang: str,
    source_lang: str = "auto",
    engine: str = "google"
) -> str:
    """Translate text to target language.
    
    Args:
        text: Text to translate (max 5000 chars)
        target_lang: Target language code (en/ja/ko/fr/de/es/pt/ar/ru/th/vi...)
        source_lang: Source language (auto for auto-detect)
        engine: Translation engine (google/deepl/llm)
    """
    if not text.strip():
        return json.dumps({"error": "Empty text"})

    target_lang = target_lang.strip()
    text = text[:5000]

    result = None
    error = None

    # Google Translate (primary, free)
    if engine == "google":
        try:
            result = _google_translate(text, target_lang, source_lang)
            if not result:
                result = _http_translate(text, target_lang, source_lang)
        except Exception as e:
            error = str(e)
            result = _http_translate(text, target_lang, source_lang)

    # DeepL (requires API key)
    elif engine == "deepl":
        api_key = os.environ.get("DEEPL_API_KEY")
        if not api_key:
            return json.dumps({"error": "DEEPL_API_KEY not configured"})
        try:
            import httpx
            resp = httpx.post(
                "https://api-free.deepl.com/v2/translate",
                data={"text": text, "target_lang": target_lang.upper(), "source_lang": source_lang.upper() if source_lang != "auto" else ""},
                headers={"Authorization": f"DeepL-Auth-Key {api_key}"},
                timeout=15
            )
            data = resp.json()
            result = data["translations"][0]["text"]
        except Exception as e:
            error = str(e)

    # LLM via vLLM
    elif engine == "llm":
        llm_url = os.environ.get("LLM_API_URL", "http://localhost:8000/v1")
        try:
            import httpx
            prompt = f"Translate the following text from {source_lang} to {target_lang}. Only output the translation, nothing else:\n\n{text}"
            resp = httpx.post(
                f"{llm_url}/chat/completions",
                json={
                    "model": "qwen2.5-7b",
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 2000,
                    "temperature": 0.1
                },
                timeout=30
            )
            data = resp.json()
            result = data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            error = str(e)

    if result:
        return json.dumps({
            "success": True,
            "original": text[:200],
            "translated": result,
            "source_lang": source_lang,
            "target_lang": target_lang,
            "engine": engine,
            "char_count": len(result)
        }, ensure_ascii=False)
    else:
        return json.dumps({"success": False, "error": error or "Translation failed"}, ensure_ascii=False)


@mcp.tool()
def translate_batch(
    texts: str,
    target_lang: str,
    source_lang: str = "auto",
    engine: str = "google"
) -> str:
    """Batch translate multiple texts at once.
    
    Args:
        texts: JSON array of texts to translate, or newline-separated
        target_lang: Target language code
        source_lang: Source language code
        engine: Translation engine
    """
    # Parse input
    if texts.strip().startswith("["):
        items = json.loads(texts)
    else:
        items = [t.strip() for t in texts.split("\n") if t.strip()]

    if not items:
        return json.dumps({"error": "No texts provided"})

    translated = []
    for i, text in enumerate(items[:50], 1):
        result = translate_text(text, target_lang, source_lang, engine)
        r = json.loads(result)
        translated.append({
            "index": i,
            "original": text[:100],
            "translated": r.get("translated", r.get("error", ""))[:200],
            "success": r.get("success", False)
        })

    return json.dumps({
        "total_input": len(items),
        "translated": len(translated),
        "successful": sum(1 for t in translated if t["success"]),
        "target_lang": target_lang,
        "results": translated
    }, ensure_ascii=False)


@mcp.tool()
def translate_file(
    file_path: str,
    target_lang: str,
    output_path: Optional[str] = None,
    source_lang: str = "auto",
    engine: str = "google",
    preserve_format: bool = True
) -> str:
    """Translate a text file (txt/md/json/csv) to target language.
    
    Args:
        file_path: Path to source file
        target_lang: Target language code
        output_path: Output path (default: adds _translated suffix)
        source_lang: Source language code
        engine: Translation engine
        preserve_format: Preserve line breaks and structure
    """
    if not os.path.exists(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        ext = os.path.splitext(file_path)[1].lower()

        if ext in (".json",):
            data = json.loads(content)
            translated = _translate_json_recursive(data, target_lang, source_lang, engine)
            output = json.dumps(translated, ensure_ascii=False, indent=2)
        elif ext in (".csv",):
            import csv, io
            reader = csv.reader(io.StringIO(content))
            rows = list(reader)
            translated_rows = []
            for i, row in enumerate(rows[:100]):
                if i == 0 and preserve_format:
                    translated_rows.append(row)
                else:
                    translated_rows.append([_google_translate(cell, target_lang, source_lang) or cell for cell in row])
            output_buf = io.StringIO()
            writer = csv.writer(output_buf)
            writer.writerows(translated_rows)
            output = output_buf.getvalue()
        elif preserve_format:
            # Translate line by line preserving structure
            lines = content.split("\n")
            translated_lines = []
            for line in lines:
                if line.strip() and not line.strip().startswith("#") and not line.strip().startswith("```"):
                    translated = _google_translate(line, target_lang, source_lang)
                    translated_lines.append(translated if translated else line)
                else:
                    translated_lines.append(line)
            output = "\n".join(translated_lines)
        else:
            result = translate_text(content, target_lang, source_lang, engine)
            r = json.loads(result)
            output = r.get("translated", content)

        if not output_path:
            base, ext_orig = os.path.splitext(file_path)
            output_path = f"{base}_translated_{target_lang}{ext_orig}"

        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(output)

        return json.dumps({
            "success": True,
            "input_file": file_path,
            "output_file": output_path,
            "output_size": os.path.getsize(output_path),
            "target_lang": target_lang,
            "engine": engine
        }, ensure_ascii=False)

    except Exception as e:
        return json.dumps({"error": str(e)}, ensure_ascii=False)


def _translate_json_recursive(obj, target, source, engine):
    if isinstance(obj, str):
        return _google_translate(obj, target, source) or obj
    elif isinstance(obj, list):
        return [_translate_json_recursive(item, target, source, engine) for item in obj]
    elif isinstance(obj, dict):
        return {k: _translate_json_recursive(v, target, source, engine) for k, v in obj.items()}
    return obj


@mcp.tool()
def translate_html(
    html_text: str,
    target_lang: str,
    source_lang: str = "auto",
    output_path: Optional[str] = None
) -> str:
    """Translate HTML content, preserving tags.
    
    Args:
        html_text: HTML string to translate
        target_lang: Target language code
        source_lang: Source language code
        output_path: Output file path
    """
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        return json.dumps({"error": "beautifulsoup4 not installed. pip install beautifulsoup4"})

    soup = BeautifulSoup(html_text, "html.parser")

    # Translate text nodes only (not script/style)
    for tag in soup.find_all(string=True):
        if tag.parent.name not in ("script", "style"):
            text = tag.strip()
            if text:
                translated = _google_translate(text, target_lang, source_lang)
                if translated:
                    tag.replace_with(translated)

    result = str(soup)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)

    return json.dumps({
        "success": True,
        "html_length": len(result),
        "saved_to": output_path
    }, ensure_ascii=False)


@mcp.tool()
def translate_json(
    json_data: str,
    target_lang: str,
    source_lang: str = "auto",
    keys_to_translate: Optional[str] = None
) -> str:
    """Translate values in JSON data.
    
    Args:
        json_data: JSON string
        target_lang: Target language code
        source_lang: Source language code
        keys_to_translate: Comma-separated keys to translate (None=all)
    """
    data = json.loads(json_data)
    keys_set = set(k.strip() for k in keys_to_translate.split(",")) if keys_to_translate else None

    def _translate(obj):
        if isinstance(obj, dict):
            return {k: (_translate(v) if not keys_set or k in keys_set else v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [_translate(item) for item in obj]
        elif isinstance(obj, str) and (not keys_set or True):
            return _google_translate(obj, target_lang, source_lang) or obj
        return obj

    result = _translate(data)
    return json.dumps({
        "success": True,
        "translated": result,
        "target_lang": target_lang
    }, ensure_ascii=False)


@mcp.tool()
def translate_markdown(
    markdown_text: str,
    target_lang: str,
    source_lang: str = "auto",
    output_path: Optional[str] = None
) -> str:
    """Translate Markdown content, preserving formatting and code blocks.
    
    Args:
        markdown_text: Markdown text to translate
        target_lang: Target language code
        source_lang: Source language code
        output_path: Output file path
    """
    lines = markdown_text.split("\n")
    result_lines = []
    in_code_block = False

    for line in lines:
        stripped = line.strip()

        # Skip code blocks
        if stripped.startswith("```"):
            in_code_block = not in_code_block
            result_lines.append(line)
            continue

        if in_code_block:
            result_lines.append(line)
            continue

        # Translate markdown contents (preserve headers/list markers)
        if stripped.startswith("#"):
            # Header: translate the text part
            match = re.match(r'^(#+)\s*(.+)$', line)
            if match:
                hashes, title = match.groups()
                translated = _google_translate(title, target_lang, source_lang)
                result_lines.append(f"{hashes} {translated or title}")
            else:
                result_lines.append(line)
        elif stripped.startswith(("- ", "* ", "1. ")):
            # List item
            match = re.match(r'^(\s*(?:-|\*|\d+\.)\s+)(.+)$', line)
            if match:
                prefix, content = match.groups()
                translated = _google_translate(content, target_lang, source_lang)
                result_lines.append(f"{prefix}{translated or content}")
            else:
                result_lines.append(line)
        elif stripped:
            translated = _google_translate(line, target_lang, source_lang)
            result_lines.append(translated or line)
        else:
            result_lines.append(line)

    result = "\n".join(result_lines)

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(result)

    return json.dumps({
        "success": True,
        "length": len(result),
        "saved_to": output_path,
        "target_lang": target_lang
    }, ensure_ascii=False)


@mcp.tool()
def compare_translations(
    text: str,
    target_lang: str,
    source_lang: str = "auto"
) -> str:
    """Compare translations from multiple engines (Google + LLM).
    
    Args:
        text: Text to translate
        target_lang: Target language code
        source_lang: Source language code
    """
    engines = {}

    # Google
    try:
        engines["google"] = _google_translate(text, target_lang, source_lang)
    except Exception as e:
        engines["google"] = f"error: {e}"

    # LLM if available
    llm_url = os.environ.get("LLM_API_URL")
    if llm_url:
        try:
            import httpx
            prompt = f"Translate to {target_lang}: {text}"
            resp = httpx.post(
                f"{llm_url}/chat/completions",
                json={"model": "qwen2.5-7b", "messages": [{"role": "user", "content": prompt}], "max_tokens": 500, "temperature": 0.1},
                timeout=20
            )
            engines["llm_qwen"] = resp.json()["choices"][0]["message"]["content"].strip()
        except Exception as e:
            engines["llm_qwen"] = f"error: {e}"

    return json.dumps({
        "original": text[:200],
        "target_lang": target_lang,
        "translations": engines
    }, ensure_ascii=False)


@mcp.tool()
def transliterate(text: str, script: str = "latin") -> str:
    """Transliterate text to a different script (e.g., Chinese pinyin, Russian Latin).
    
    Args:
        text: Text to transliterate
        script: Target script (latin/cyrillic/hangul)
    """
    try:
        import unicodedata
        from pypinyin import pinyin, Style

        if script == "latin":
            # Chinese to Pinyin
            result = " ".join([p[0] for p in pinyin(text, style=Style.TONE)])
            return json.dumps({
                "success": True,
                "original": text,
                "transliterated": result,
                "script": "pinyin"
            }, ensure_ascii=False)
    except ImportError:
        pass

    # Fallback: basic transliteration
    result = text
    return json.dumps({
        "success": True,
        "original": text,
        "transliterated": result,
        "script": script,
        "note": "Install pypinyin for Chinese pinyin support"
    }, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=int(os.environ.get("PORT", "9020")))