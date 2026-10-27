/*CRIAÇÃO DAS TABELAS*/

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    nome TEXT,
    matricula TEXT,
    cpf TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS users_cpf_unique_idx
    ON users (cpf) WHERE cpf IS NOT NULL;

CREATE TABLE IF NOT EXISTS chat_tabs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id),
    title TEXT,
    context TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_tab_id UUID REFERENCES chat_tabs(id),
    role TEXT,
    content TEXT,
    filename TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);


CREATE TABLE token_usage (
    identifier     TEXT         NOT NULL,
    id_type        TEXT         NOT NULL,
    input_tokens   INTEGER      NOT NULL DEFAULT 0,
    output_tokens  INTEGER      NOT NULL DEFAULT 0,
    total_tokens   INTEGER      NOT NULL DEFAULT 0,
    date           DATE         NOT NULL DEFAULT (NOW() AT TIME ZONE 'America/Recife')::DATE,
    last_updated   TIMESTAMPTZ  NOT NULL DEFAULT CURRENT_TIMESTAMP,

    PRIMARY KEY (identifier, date)
);

CREATE INDEX IF NOT EXISTS idx_token_usage_identifier_day
    ON token_usage (identifier);

CREATE TABLE IF NOT EXISTS academic_period_cache (
    cache_key TEXT PRIMARY KEY,
    periodo TEXT,
    valid_from DATE,
    valid_until DATE,
    refresh_after TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT academic_period_cache_singleton CHECK (cache_key = 'current')
);
