CREATE TABLE IF NOT EXISTS academic_period_cache (
    cache_key TEXT PRIMARY KEY,
    periodo TEXT,
    valid_from DATE,
    valid_until DATE,
    refresh_after TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT academic_period_cache_singleton CHECK (cache_key = 'current')
);
