ALTER TABLE users ADD COLUMN IF NOT EXISTS cpf TEXT;

-- Antes desta migration, a coluna matricula armazenava o CPF retornado pelo
-- serviço de autenticação. Preserva esse valor na coluna correta.
UPDATE users
SET cpf = matricula
WHERE cpf IS NULL AND matricula IS NOT NULL;

-- Consolida eventuais duplicatas antigas antes de criar a unicidade do CPF.
WITH canonical AS (
    SELECT cpf, (ARRAY_AGG(id ORDER BY created_at NULLS LAST, id))[1] AS keep_id
    FROM users
    WHERE cpf IS NOT NULL
    GROUP BY cpf
    HAVING COUNT(*) > 1
)
UPDATE chat_tabs AS ct
SET user_id = canonical.keep_id
FROM users AS duplicate_user
JOIN canonical ON canonical.cpf = duplicate_user.cpf
WHERE ct.user_id = duplicate_user.id
  AND duplicate_user.id <> canonical.keep_id;

WITH canonical AS (
    SELECT cpf, (ARRAY_AGG(id ORDER BY created_at NULLS LAST, id))[1] AS keep_id
    FROM users
    WHERE cpf IS NOT NULL
    GROUP BY cpf
    HAVING COUNT(*) > 1
)
DELETE FROM users AS duplicate_user
USING canonical
WHERE duplicate_user.cpf = canonical.cpf
  AND duplicate_user.id <> canonical.keep_id;

-- O valor legado era CPF, não matrícula. O identificador acadêmico verdadeiro
-- será preenchido no próximo login do usuário.
UPDATE users
SET matricula = NULL
WHERE cpf IS NOT NULL AND matricula = cpf;

CREATE UNIQUE INDEX IF NOT EXISTS users_cpf_unique_idx
    ON users (cpf) WHERE cpf IS NOT NULL;
