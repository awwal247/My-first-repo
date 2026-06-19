# ZENITH OX v4.0 — OpenRouter Edition

A Secure Intelligent AI Assistant with Chat History & Vector Memory.
Powered by **OpenRouter** (primary) with **Groq** fallback for vision.

## What's New in v4.0 OpenRouter Edition

| Feature | Description |
|---------|-------------|
| **OpenRouter First, Groq Fallback** | `ask_ai()` routes to OpenRouter first, falls back to Groq on failure |
| **Multi-Image Upload** | Upload multiple images in one message, each analyzed by Groq Vision |
| **Pollinations.ai PPTX Images** | AI-generated images automatically embedded in presentations |
| **Voice Input** | Web Speech API microphone button for voice-to-text |
| **Dark Mode** | Full dark theme with CSS variables and localStorage persistence |
| **Chat Export** | Export chats as Markdown, Text, or JSON |
| **Regenerate** | Retry the last AI response with higher temperature |
| **Edit Messages** | Inline edit any bot message |
| **Pin Chats** | Pin important chats to keep them at the top |
| **Search Chats** | Full-text search across all chat titles and messages |
| **Rename Chats** | Inline rename any chat session |
| **Restore on Load** | Automatically restores your most recent chat on page load |
| **No Jupyter Notebooks** | All AI modes use API models — no manual training needed |

## Architecture

```
User Message
    → ask_ai()
        → ask_openrouter()  [PRIMARY: OpenRouter API]
        → ask_groq()        [FALLBACK: Groq API]
        → ask_groq_vision() [VISION: Groq multimodal for images]
```

## OpenRouter Setup

1. Get your API key at [openrouter.ai/keys](https://openrouter.ai/keys)
2. Set `OPENROUTER_API_KEY` in your environment variables
3. Groq key is still required for image/vision analysis

## Environment Variables

```bash
# Required
OPENROUTER_API_KEY=sk-or-v1-...
GROQ_API_KEY=gsk_...
DATABASE_URL=postgresql://...

# Optional
TAVILY_API_KEY=tvly-...        # For web search in Researcher mode
GOOGLE_CLIENT_ID=...           # For Google OAuth
GOOGLE_CLIENT_SECRET=...       # For Google OAuth
```

## Install Dependencies

```bash
pip install -r requirements.txt
```

No `huggingface_hub` needed — OpenRouter handles all model routing.

## Deploy

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
