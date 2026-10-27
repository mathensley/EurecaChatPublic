-- Força a primeira versão com TTL a consultar novamente o SIG.
-- Entradas anteriores podiam permanecer válidas até o encerramento das notas.
UPDATE academic_period_cache
SET refresh_after = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP
WHERE cache_key = 'current';
