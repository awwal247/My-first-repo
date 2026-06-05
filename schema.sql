-- Zenith OX v4.0 schema
-- Run this in Supabase SQL Editor

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT UNIQUE NOT NULL,
    display_name TEXT NOT NULL,
    password_hash TEXT,
    google_id TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Conversations table (per-message memory for vector search)
CREATE TABLE IF NOT EXISTS conversations (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode_key TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN('user','assistant')),
    content TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_conv_user_mode ON conversations(user_id, mode_key);

-- Chats table (session-based chat history)
-- v4.0: Added pinned column for pinning important chats
CREATE TABLE IF NOT EXISTS chats (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title TEXT NOT NULL DEFAULT 'New chat',
    mode TEXT NOT NULL DEFAULT 'researcher',
    messages JSONB NOT NULL DEFAULT '[]',
    pinned BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS chats_user_id_updated_at ON chats(user_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS chats_user_id_pinned ON chats(user_id, pinned DESC, updated_at DESC);

-- For upgrading existing databases to v4.0, run:
-- ALTER TABLE chats ADD COLUMN IF NOT EXISTS pinned BOOLEAN NOT NULL DEFAULT false;
