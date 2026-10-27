CREATE TABLE IF NOT EXISTS token_usage (
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