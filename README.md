# Translation MCP Server

Multi-language translation MCP Server supporting Google Translate, DeepL, and LLM-based translation.

## Features (10 Tools)

| Tool | Description |
|------|-------------|
| `translate_text` | Translate text between languages |
| `translate_batch` | Batch translate multiple texts |
| `translate_file` | Translate entire file content |
| `detect_language` | Auto-detect text language |
| `list_languages` | List supported languages |
| `translate_html` | Translate HTML preserving tags |
| `translate_json` | Translate JSON values preserving keys |
| `translate_markdown` | Translate Markdown preserving formatting |
| `compare_translations` | Compare translations from multiple engines |
| `transliterate` | Transliterate text between scripts |

## Deployment

**Server**: https://www.mzse.com/translation-mcp/
**Port**: 9020
**Transport**: Streamable HTTP

### MCP Client Configuration

```json
{
  "mcpServers": {
    "translation": {
      "url": "https://www.mzse.com/translation-mcp/"
    }
  }
}
```

### REST API Example

```bash
curl -X POST https://www.mzse.com/translation-mcp/ \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"translate_text","arguments":{"text":"Hello","target_lang":"zh"}},"id":1}'
```

## Installation

```bash
pip install -r requirements.txt
python server.py
```

## Environment Variables

- `PORT` - Server port (default: 9020)
