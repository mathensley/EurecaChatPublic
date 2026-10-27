import logging

from langchain.tools import ToolRuntime, tool
from langchain_core.runnables import RunnableConfig

from application.config import URL_SIG
from ...helpers.context import Context
from ...helpers.func_utils import get_func_info
from ...helpers.request_utils import make_request

@tool
async def historico_estudante(runtime: ToolRuntime[Context], config: RunnableConfig) -> list:
    """
    Use esta função quando a pergunta do usuário (Aluno) for sobre as informações do histórico de matrículas ou disciplinas dele mesmo (em primeira pessoa).
    Retorna valores como: os períodos completados, os nomes das disciplinas cursadas, a nota/média final em cada disciplina, se foi aprovado ou não, turma, se a disciplina foi dispensada ou não e o período em que a disciplina foi cursada.
    Além de se o usuário possui alguma disciplina sendo cursada no momento.
    """

    # Variáveis da tool
    func_name, _ = get_func_info()

    matricula = runtime.context.user_indentifier
    token = runtime.context.token

    params = {"estudante": matricula}
    headers = { "accept": "application/json", "token-de-autenticacao": token }

    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Recuperando seu histórico"})
            break
    except:
        pass
    
    try:
        print(f"🔍 Chamando {func_name}")

        dados = await make_request(url=f"{URL_SIG}/estudantes/historico/estudante", params=params, headers=headers)

        to_remove = ["matricula_do_estudante", "dispensas"]
        result = [{k: v for k, v in dado.items() if k not in to_remove} for dado in dados["historico_de_matriculas"]]

        """
        Retorna essas informações:
        "periodos_completados": int,
        "historico_de_matriculas": [
            "matricula_do_estudante": string,
            "codigo_da_disciplina": int,
            "nome_da_disciplina": string,
            "periodo": string,
            "turma": int,
            "status": ENUM "EM_CURSO", "Aprovado", "Reprovado", "Trancado", "Reprovado por Falta", 
            "tipo": ENUM "NORMAL",
            "media_final": float
        ]
        """
        return [{"periodos_completados": dados["periodos_completados"]}] + result
    
    except Exception:
        raise