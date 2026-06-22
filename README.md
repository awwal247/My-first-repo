# Zenith OX v2.5 — Standard AI Workspace

Zenith OX v2.5 is a Flask + SQL + OpenRouter workspace with a more standard chat UI, visible thinking trace, better attachment workflows, exact download naming, and workspace model switching.

## v2.5 update highlights

- Rounded prompt composer with inline **plus** button inside the chat input
- **Thinking trace** shown in chat before the final answer lands
- Bottom attachment sheet with **Camera**, **Photo**, **Files**, **Google Drive**, **GitHub**, and **Code ZIP** actions
- Public-link import support for **Google Drive** and **GitHub**
- Workspace model selection for:
  - Meta Llama Versatile 3.1
  - OpenAI GPT OSS 120B
  - Google Gemini Flash 3.1 preset
  - Google Gemini Pro
- Improved return-file naming so generated files are delivered with user-expected names whenever possible
- Refreshed landing page and workspace presentation

## Stack

- **Backend:** Python, Flask, PostgreSQL / Supabase-style SQL
- **AI routing:** OpenRouter primary, Groq fallback / vision
- **Frontend:** Jinja templates, vanilla JavaScript, custom CSS
- **File handling:** PDFs, Office docs, spreadsheets, images, archives, code files

## Workspace model presets

The workspace model picker changes the active chat model without changing the higher-level AI mode.

| UI label | Routed model |
|---|---|
| Meta Llama Versatile 3.1 | `meta-llama/llama-3.1-70b-instruct` |
| OpenAI GPT OSS 120B | `openai/gpt-oss-120b:free` |
| Google Gemini Flash 3.1 | `google/gemini-2.5-flash` |
| Google Gemini Pro | `google/gemini-2.5-pro` |

> Note: the Gemini Flash and Pro presets are mapped to current stable OpenRouter Gemini endpoints in code.

## Attachment sheet behavior

The plus button inside the composer opens a bottom sheet with:

- **Camera** → opens a camera capture file picker on supported devices
- **Photo** → opens local image selection
- **Files** → opens general file selection
- **Google Drive** → imports a public/shared Google Drive file link
- **GitHub** → imports a public GitHub repo, blob, raw, archive, or release asset link
- **Code ZIP** → developer-only project upload action

Imported files are added to the same pending attachment queue used by normal local uploads.

## Exact file naming

For developer outputs, v2.5 improves artifact delivery:

- single generated files are returned directly when possible
- multi-file outputs are zipped with a more meaningful archive name
- if the user explicitly asks for a filename or archive name, the app tries to preserve it exactly

## Environment variables

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...
GROQ_API_KEY=gsk_...
DATABASE_URL=postgresql://...

# Optional
EXA_API_KEY=...
TAVILY_API_KEY=...
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...
FLASK_SECRET_KEY=...
FLASK_DEBUG=false
```

## Install

```bash
pip install -r requirements.txt
```

## Run locally

```bash
python app.py
```

Then open:

```text
http://127.0.0.1:5000/
```

## Main routes

### App
- `GET /` — landing page
- `GET /menu` — dashboard / workspace overview
- `GET /chat` — chat workspace
- `GET /files` — files vault
- `GET /history-center` — chat history center
- `GET /settings` — workspace settings

### Chat
- `POST /chat` — standard message + file upload
- `POST /chat/stream` — SSE text streaming
- `POST /regenerate` — regenerate last answer
- `POST /clear` — clear mode memory
- `POST /upload-code` — analyze / modify a ZIP or RAR code project
- `POST /import-external` — import a public Google Drive or GitHub file into the attachment queue
- `GET /download-generated/<filename>` — download generated file or archive

## Notes for deployment

- The workspace expects OpenRouter as the primary inference provider.
- Groq is still used as a fallback and for image understanding.
- Public Google Drive and GitHub imports do not require OAuth because they are link-based imports.
- If you want private Google Drive selection, you can extend the current link-based flow with OAuth and the Google Picker API.

## v2.5 release goal

This update focuses on making Zenith OX feel closer to a real, polished AI workspace instead of a basic demo interface while keeping the backend Flask architecture simple and maintainable.
