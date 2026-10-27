import logging

from langchain.tools import ToolRuntime, tool
from langchain_core.runnables import RunnableConfig

from application.config import URL_SIG
from ...helpers.context import Context
from ...helpers.func_utils import get_func_info
from ...helpers.request_utils import make_request

@tool
async def estudante_info(runtime: ToolRuntime[Context], config: RunnableConfig) -> dict:
    """
    Use esta função quando a pergunta do usuário (Aluno) for sobre as informações acadêmicas dele mesmo (em primeira pessoa).
    Retorna valores como: métricas (CRA, MC, ...), dados pessoais (CPF, telefone, endereço, unidade federativa, estado civil, ...), créditos do curso, períodos completados, período atual, etc.
    Não é preciso fornecer nenhum dado para recuperar essas informações.
    """

    # Variáveis da tool
    func_name, _ = get_func_info()

    matricula = runtime.context.user_indentifier
    token = runtime.context.token

    params = {"estudante": matricula}
    headers = {"accept": "application/json", "token-de-autenticacao": token}

    try:
        callbacks = config["configurable"].get("callbacks_sio")
        for cb in callbacks:
            if hasattr(cb, 'emit'):
                await cb.emit("status", {"resposta": "Buscando por seus dados"})
            break
    except:
        pass
    
    try:
        print(f"🔍 Chamando {func_name}")

        dados = await make_request(url=f"{URL_SIG}/estudantes/estudante", params=params, headers=headers)

        curriculo = dados.get("codigo_do_curriculo")
        
        if not curriculo:
            curriculos = await make_request(url=f"{URL_SIG}/curriculos/codigos-curriculo", params={"curso": dados.get("codigo_do_curso")})
            curriculo = max(curriculos, key=lambda x: int(x))
            
        curr_params = {"curso": dados.get("codigo_do_curso"), "curriculo": curriculo}
        dados_curriculo = await make_request(url=f"{URL_SIG}/curriculos/curriculo", params=curr_params)
        dados_disciplinas = await make_request(url=f"{URL_SIG}/estudantes/historico/estudante", params=params, headers=headers)

        disciplinas_do_curso = dados_curriculo.get("disciplinas_do_curriculo", [])
        # Mapeia código da disciplina -> horas totais
        mapa_disciplinas = {str(d["codigo_da_disciplina"]): d.get("horas_totais", 0) for d in disciplinas_do_curso}

        historico = dados_disciplinas.get("historico_de_matriculas", [])

        creditos_obrigatorias = 0
        creditos_optativas = 0
        creditos_complementares = 0

        for disc in historico:
            codigo = str(disc.get("codigo_da_disciplina"))
            nome = str(disc.get("nome_da_disciplina") or "")
            tipo = str(disc.get("tipo") or "")
            status = str(disc.get("status") or "")

            if status not in ["Aprovado", "Transferido"]:
                continue

            horas = mapa_disciplinas.get(codigo) or 0
            creditos = horas / 15  # conversão de horas para créditos

            if "Obrigatória" in tipo:
                if "COMPLEMENTARES" in nome.upper():
                    creditos_complementares += creditos
                else:
                    creditos_obrigatorias += creditos
            elif "Optativa" in tipo:
                creditos_optativas += creditos
        
        min_obrig = dados_curriculo.get("minimo_creditos_disciplinas_obrigatorias", 0)
        min_optat = dados_curriculo.get("minimo_creditos_disciplinas_optativas", 0)
        min_compl = dados_curriculo.get("minimo_creditos_atividades_complementares", 0)

        dados.update({
            "creditos_obrigatorias": creditos_obrigatorias,
            "creditos_optativas": creditos_optativas,
            "creditos_complementares": creditos_complementares,
            "faltam_creditos_obrigatorias": max(0, min_obrig - creditos_obrigatorias),
            "faltam_creditos_optativas": max(0, min_optat - creditos_optativas),
            "faltam_creditos_complementares": max(0, min_compl - creditos_complementares),
            "minimo_creditos_disciplinas_obrigatorias": min_obrig,
            "minimo_creditos_disciplinas_optativas": min_optat,
            "minimo_creditos_atividades_complementares": min_compl
        })

        return dados
    
    except Exception:
        raise