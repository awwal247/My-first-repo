-- ============================================================
-- Zenith OX — Full Supabase Schema
-- Includes: all existing tables + v2.7 new additions
-- Safe to re-run: all statements use IF NOT EXISTS
-- Run this in: Supabase Dashboard → SQL Editor → Run
-- ============================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;


-- ── Users ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email          TEXT UNIQUE NOT NULL,
    display_name   TEXT NOT NULL,
    password_hash  TEXT,
    google_id      TEXT UNIQUE,
    bio            TEXT NOT NULL DEFAULT '',
    avatar_color   TEXT NOT NULL DEFAULT '#7c5cff',
    created_at     TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE users ADD COLUMN IF NOT EXISTS bio          TEXT NOT NULL DEFAULT '';
ALTER TABLE users ADD COLUMN IF NOT EXISTS avatar_color TEXT NOT NULL DEFAULT '#7c5cff';

-- v2.7: premium flag (used for model access + token limit bypass)
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_premium BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE users ADD COLUMN IF NOT EXISTS is_admin   BOOLEAN NOT NULL DEFAULT false;


-- ── Conversations (per-message memory) ───────────────────────
CREATE TABLE IF NOT EXISTS conversations (
    id         BIGSERIAL PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode_key   TEXT NOT NULL,
    role       TEXT NOT NULL CHECK(role IN('user','assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conv_user_mode ON conversations(user_id, mode_key);


-- ── Chats ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chats (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL DEFAULT 'New chat',
    mode       TEXT NOT NULL DEFAULT 'researcher',
    messages   JSONB NOT NULL DEFAULT '[]',
    pinned     BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE chats ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS chats_user_id_updated_at ON chats(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS chats_user_id_pinned     ON chats(user_id, pinned DESC, updated_at DESC);


-- ── User workspace settings ───────────────────────────────────
CREATE TABLE IF NOT EXISTS user_settings (
    user_id               UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    default_mode          TEXT NOT NULL DEFAULT 'researcher',
    email_notifications   BOOLEAN NOT NULL DEFAULT true,
    desktop_notifications BOOLEAN NOT NULL DEFAULT true,
    auto_title_chats      BOOLEAN NOT NULL DEFAULT true,
    compact_mode          BOOLEAN NOT NULL DEFAULT false,
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- ── File vault ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS user_files (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    filename     TEXT NOT NULL,
    content_type TEXT NOT NULL DEFAULT 'application/octet-stream',
    size_bytes   BIGINT NOT NULL DEFAULT 0,
    description  TEXT NOT NULL DEFAULT '',
    file_data    BYTEA NOT NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS user_files_user_id_created_at ON user_files(user_id, created_at DESC);


-- ── Notifications ─────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS notifications (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title      TEXT NOT NULL,
    body       TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT 'info',
    is_read    BOOLEAN NOT NULL DEFAULT false,
    action_url TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS notifications_user_id_created_at ON notifications(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS notifications_user_id_is_read    ON notifications(user_id, is_read, created_at DESC);


-- ── v2.7 NEW: Token usage (daily limit tracking) ─────────────
CREATE TABLE IF NOT EXISTS token_usage (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tokens     INTEGER NOT NULL DEFAULT 0,
    date       DATE NOT NULL DEFAULT CURRENT_DATE,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, date)
);

CREATE INDEX IF NOT EXISTS idx_token_usage_user_date ON token_usage(user_id, date);


-- ── v2.7 NEW: Projects (sidebar project groups) ──────────────
CREATE TABLE IF NOT EXISTS projects (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name       TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS project_chats (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    chat_id    UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(project_id, chat_id)
);

-- Max 3 chats per project is enforced in Python, not the DB.
-- ============================================================


-- ============================================================
-- Shared developer / QA test account
-- ============================================================
-- This is NOT a real user. It is a fixed-credential account shared among
-- the development team so the app can always be logged into and tested,
-- independent of whatever real users exist.
--
-- Its UUID is fixed (not gen_random_uuid()) so it matches the SAME
-- account that the app falls back to locally (SQLite) on the rare
-- occasion Supabase itself is unreachable -- see
-- app/services/fallback_db.py for that fallback logic. Whether Supabase
-- is up or down, logging in with these credentials always works:
--
--   email:    dev@zenithox.local
--   password: PIPuTZdEZyGlxw
--
-- Share these credentials only with other developers on the team --
-- never give them to end users. Safe to re-run (ON CONFLICT DO NOTHING).
INSERT INTO users (id, email, display_name, password_hash, google_id, bio, avatar_color, is_premium, is_admin)
VALUES (
    'ecb548c8-436b-5ef0-9250-2aa36942bcb3',
    'dev@zenithox.local',
    'Zenith Dev',
    'scrypt:32768:8:1$Iial1TFIQFH2mME8$24b140acef4d4afa3d2201ac6dc6b2f97729779f04aae3cd305750f70e1757b2d2e9c920a90efd372ffe2babf0453033a86c4e93536147450c6f80680aa6c632',
    NULL,
    'Shared developer/QA account. Works even when Supabase is down.',
    '#c9a84c',
    true,
    false
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO user_settings (user_id)
VALUES ('ecb548c8-436b-5ef0-9250-2aa36942bcb3')
ON CONFLICT (user_id) DO NOTHING;
-- ============================================================
