import logging

from langchain.tools import ToolRuntime, tool

from application.config import URL_SIG
from ...helpers.context import Context
from ...helpers.func_utils import get_func_info
from ...helpers.request_utils import make_request
from ...helpers.tool_handlers.agent_utils import get_nome_campus, _periodo_key, _formatar_turma

@tool
async def professor_info(runtime: ToolRuntime[Context]) -> dict:
    """
    Use esta função quando a pergunta do usuário (Professor) for sobre as informações dele mesmo (em primeira pessoa).
    Retorna valores como: nome, cpf, matrícula do docente, departamento (ou unidade acadêmica), campus, email, SIAPE, titulação e disciplinas e turmas que leciona e já lecionou.
    Não é preciso fornecer nenhum dado para recuperar essas informações.
    """

    # Variáveis da tool
    func_name, _ = get_func_info()
    
    siape = runtime.context.user_indentifier
    token = runtime.context.token

    params = {"professor": siape}
    headers = {"accept": "application/json", "token-de-autenticacao": token}

    # try:
    #     callbacks = config["configurable"].get("callbacks_sio")
    #     for cb in callbacks:
    #         if hasattr(cb, 'emit'):
    #             await cb.emit("status", {"resposta": "Buscando seus dados de professor"})
    #         break
    # except:
    #     pass
    

    try:
        print(f"🔍 Chamando {func_name}")

        dados = await make_request(url=f"{URL_SIG}/professores/professor", params=params, headers=headers)
        if not dados:
            raise ValueError("Não foi possível obter os dados do professor.")

        dados_professor = dados.copy()

        nome_campus = get_nome_campus(dados_professor.get("campus"))
        if nome_campus:
            dados_professor["campus"] = nome_campus

        codigo_do_setor = dados_professor.get("codigo_do_setor")
        if codigo_do_setor:
            setor = await make_request(url=f"{URL_SIG}/setores", params={"setor": codigo_do_setor}, headers=headers)

            if isinstance(setor, list):
                setor = setor[0] if setor else None

            if isinstance(setor, dict):
                departamento = setor.get("descricao")
                if departamento:
                    dados_professor["departamento"] = departamento

        turmas = await make_request(url=f"{URL_SIG}/classes-por-professor", params=params, headers=headers)
        turmas = turmas or []

        periodo_atual = max(turmas, key=_periodo_key)["periodo"] if turmas else None
        disciplinas_atuais = [_formatar_turma(turma) for turma in turmas if turma.get("periodo") == periodo_atual]
        disciplinas_anteriores = [_formatar_turma(turma) for turma in turmas if turma.get("periodo") != periodo_atual]
        
        return {"dados_professor": dados_professor, "disciplinas_atuais": disciplinas_atuais, "disciplinas_lecionadas_anteriormente": disciplinas_anteriores}
    except Exception as e:
        logging.exception(f"Erro interno inesperado na tool {func_name}: {e}")
        raise Exception(e)
