async def get_user_or_create(conn, nome, cpf, matricula=None):
    """Cria ou atualiza um usuário usando o CPF como identidade estável."""
    return await conn.fetchrow(
        """
        INSERT INTO users (nome, cpf, matricula)
        VALUES ($1, $2, $3)
        ON CONFLICT (cpf) WHERE cpf IS NOT NULL
        DO UPDATE SET
            nome = COALESCE(EXCLUDED.nome, users.nome),
            matricula = COALESCE(EXCLUDED.matricula, users.matricula)
        RETURNING *
        """,
        nome,
        cpf,
        matricula,
    )


async def get_user_by_cpf(conn, cpf):
    return await conn.fetchrow(
        "SELECT * FROM users WHERE cpf = $1",
        cpf,
    )
