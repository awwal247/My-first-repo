# ZENITH OX v4.0

A Secure Intelligent AI Assistant with Chat History & Vector Memory.

## What's New in v4.0

| Feature | Description |
|---------|-------------|
| **HuggingFace First, Groq Fallback** | `ask_ai()` routes to HF Inference API first, falls back to Groq on failure |
| **Multi-Image Upload** | Upload multiple images in one message, each analyzed by Groq Vision |
| **Pollinations.ai PPTX Images** | AI-generated slide images automatically embedded in presentations |
| **Voice Input** | Web Speech API microphone button for voice-to-text |
| **Dark Mode** | Full dark theme with CSS variables and localStorage persistence |
| **Chat Export** | Export chats as Markdown, Text, or JSON |
| **Regenerate** | Retry the last AI response with higher temperature |
| **Edit Messages** | Inline edit any bot message |
| **Pin Chats** | Pin important chats to keep them at the top |
| **Search Chats** | Full-text search across all chat titles and messages |
| **Rename Chats** | Inline rename any chat session |
| **Restore on Load** | Automatically restores your most recent chat on page load |
| **No Jupyter Notebooks** | All AI modes use API-based models — no manual training needed |

## File Changes

### Modified Files (v3.0 -> v4.0)
- `app/config/ai_modes.py` - Added `hf_model` keys + `image_prompt` for PPTX
- `app/config/settings.py` - Added `HF_TOKEN`, `HF_API_URL`, `POLLINATIONS_BASE`
- `app/services/ai_client.py` - New `ask_hf()` + `ask_ai()` HF-first routing
- `app/services/db.py` - Added `pinned` column, search, pin, rename, restore
- `app/routes/chat.py` - Multi-file upload, Pollinations PPTX images, `/regenerate`, `/export-chat`
- `app/routes/chats.py` - New `/pin`, `/rename`, `/restore`, `/search` endpoints
- `app/__init__.py` - Registered `chats_bp` blueprint
- `templates/index.html` - Mic btn, dark mode toggle, export btn, search bar, multi-file input
- `static/js/script.js` - Voice, dark mode, export, regenerate, edit, multi-image, charts
- `static/js/chat_history_redesign.js` - Search, pin, restore-on-load, inline rename
- `static/css/style.css` - All new component styles (dark mode, voice, export, etc.)
- `schema.sql` - Added `pinned` column to `chats` table
- `requirements.txt` - Added `huggingface_hub>=0.24.0`
- `.env.example` - Added `HF_TOKEN`

### Unchanged Files
- `app.py`, `api/index.py`, `vercel.json`
- `app/routes/auth.py`, `landing.py`, `main.py`
- `app/services/memory.py`, `search.py`, `storage.py`
- `app/utils/auth.py`, `files.py`
- `templates/landing.html`, `login.html`, `menu.html`, `register.html`

## Setup Instructions

### 1. Database Migration
```sql
-- Run this in your Supabase SQL Editor
ALTER TABLE chats ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS chats_user_id_pinned ON chats(user_id, pinned DESC, updated_at DESC);
```

### 2. Environment Variables
Add these to your `.env` or Vercel environment variables:
```bash
# Existing
GROQ_API_KEY=your_groq_key
DATABASE_URL=your_supabase_url
TAVILY_API_KEY=your_tavily_key

# New for v4.0
HF_TOKEN=hf_your_huggingface_token    # Get from huggingface.co/settings/tokens
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Deploy
Push to GitHub and deploy on Vercel as usual.

## API Endpoints

### Chat
| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/chat` | Send message (supports multi-file upload) |
| POST | `/regenerate` | Regenerate last response |
| POST | `/clear` | Clear conversation memory |
| POST | `/upload-code` | Upload ZIP/RAR code project |
| POST | `/export-chat` | Export chat (md, txt, json) |
| GET | `/history` | Get conversation history |
| GET | `/memory-sidebar` | Get memory for all modes |

### Chat Sessions
| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/chats` | List all chats |
| POST | `/api/chats/create` | Create new chat |
| GET | `/api/chats/<id>` | Get single chat |
| PUT | `/api/chats/<id>` | Update chat |
| DELETE | `/api/chats/<id>` | Delete chat |
| POST | `/api/chats/<id>/pin` | Toggle pin |
| POST | `/api/chats/<id>/rename` | Rename chat |
| POST | `/api/chats/<id>/restore` | Restore chat |
| GET | `/api/chats/search?q=...` | Search chats |
