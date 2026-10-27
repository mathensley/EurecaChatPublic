
import sqlite3

# Uso: python db_check.py <caminho_do_banco.sqlite> <tabela>

def contar_registros(caminho_banco: str, tabela: str) -> int:
    """
    Conecta ao banco SQLite informado e retorna o total de registros
    da tabela `matriculas_ufcg`.

    Args:
        caminho_banco: Caminho absoluto ou relativo para o arquivo .sqlite.

    Returns:
        Número de linhas na tabela `matriculas_ufcg`.
    """
    conn = sqlite3.connect(caminho_banco)
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM " + tabela + " WHERE ano_de_conclusao_ensino_medio < 1970 OR ano_de_conclusao_ensino_medio > 2026;")
        total = cursor.fetchone()[0]
        return total
    finally:
        conn.close()


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Comando incorreto!")
        sys.exit(1)

    caminho = sys.argv[1]
    tabela = sys.argv[2]
    total = contar_registros(caminho, tabela)
    print(f"Total de registros em '{tabela}': {total:,}")
