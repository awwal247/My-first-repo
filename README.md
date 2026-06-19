# Zenith OX — Flask + Glassmorphism UI

Full-stack Python Flask app converted from the React/Node Zenith OX UI,
using the `date` project's backend (OpenRouter, Groq fallback, Exa AI,
Tavily fallback, Supabase, Llama Vision).

## Tech Stack
- **Backend**: Python Flask
- **AI Primary**: OpenRouter (`meta-llama/llama-3.3-70b-instruct:free` and more)
- **AI Fallback**: Groq (`llama-3.3-70b-versatile`)
- **Vision**: Groq Llama 4 Scout (`meta-llama/llama-4-scout-17b-16e-instruct`)
- **Search Primary**: Exa AI (deep research with cited sources)
- **Search Fallback**: Tavily
- **Database**: Supabase (PostgreSQL via psycopg2)
- **Streaming**: SSE live AI text tracker (no typewriter animation)
- **UI**: Glassmorphism dark theme, HTML/CSS/minimal JS
- **Auth**: Email/password + optional Google OAuth

## Pages
| Route | Description |
|---|---|
| `/` | Landing page (public) |
| `/login` | Login |
| `/register` | Register |
| `/home` or `/menu` | Dashboard (mode picker + recent chats) |
| `/modes` | Full modes grid |
| `/chat` | Chat interface (streaming) |
| `/research` | Deep Research info page |
| `/vision` | Vision AI info page |
| `/presentations` | Slides generator info page |
| `/history` | Chat history |
| `/memory` | Vector memory viewer |
| `/files` | Files info |
| `/settings` | Settings |
| `/profile` | Profile |
| `/notifications` | Notifications |
| `/admin` | Admin overview |
| `/help` | Help & FAQ |

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in your API keys
```

### 3. Create Supabase tables
Run `schema.sql` in the Supabase SQL editor.

### 4. Run
```bash
python app.py
```

## Environment Variables
See `.env.example` for all required keys:
- `OPENROUTER_API_KEY` — primary AI
- `GROQ_API_KEY` — fallback AI + vision
- `EXA_API_KEY` — primary web search
- `TAVILY_API_KEY` — fallback web search
- `DATABASE_URL` — Supabase PostgreSQL connection string
- `FLASK_SECRET_KEY` — Flask session secret
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` — optional OAuth
