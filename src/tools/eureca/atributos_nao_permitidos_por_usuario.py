LISTA_DE_ATRIBUTOS_NAO_PERMITIDOS_POR_USUARIO = {
    "anon": {
        "estudante": ["matricula_do_estudante", "nome_do_estudante"],
        "inscricao": ["matricula_do_estudante", "nome_do_estudante"],
        "estagio":   ["bolsa_mensal", "auxilio_transporte_diario"],
        "professor": ["siape"]
    },
    "Aluno": {
        "estudante": ["matricula_do_estudante", "nome_do_estudante"],
        "inscricao": ["matricula_do_estudante", "nome_do_estudante"],
        "estagio":   ["bolsa_mensal", "auxilio_transporte_diario"],
        "professor": ["siape"]
    },
    "Professor": {
        "estudante": ["matricula_do_estudante_anon"],
        "inscricao": ["matricula_do_estudante_anon"],
        "estagio":   ["bolsa_mensal", "auxilio_transporte_diario"],
        "professor": ["siape"]
    },
}


class ColunasNaoPermitidasError(Exception):
    def __init__(self, colunas: list[str]):
        self.colunas = colunas
        super().__init__(", ".join(colunas))


class SqlInvalidoError(Exception):
    """SQL que não é uma consulta única e válida: vai para nova tentativa, não é negação de perfil."""
