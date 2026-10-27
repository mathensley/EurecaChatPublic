import subprocess, sys
from .log_mudancas import registrar_mudancas
from pathlib import Path
import logging


current_dir = Path(__file__).resolve().parent
CAMINHO_HISTORICO = current_dir / "historico" / "historico_mudancas.json"
CAMINHO_HISTORICO.parent.mkdir(parents=True, exist_ok=True)

# Pemrite ou não a criação dos Logs sobre as mudanças ocorridas.
REGISTRAR_MUDANCAS = False
# Permição sobre a atualização do novo banco de dados consolidade e a renomeação do antigo para old.
SUBSTITUIR_BANCOS = False
# Permite a consolidação do nvo banco de dados a partir dos demais bancos.
CONSOLIDAR_BANCO = True
# Permite a execução do agente de busca por anomalias
EXECUTAR_AGENTE_ANOMALIAS = True

# 
SCRIPTS = [
    # "download_estudantes",
    # "download_matriculas",
    # "download_estagios",
    # "download_professores",
    # "download_disciplinas",
]


def consolidar_banco_dados_final():

    MODULOS = [
        "src.tools.eureca.scripts_consolidacao_bd.1_criar_estrutura_ufcg",
        "src.tools.eureca.scripts_consolidacao_bd.2_consolidar_bancos",
        "src.tools.eureca.scripts_consolidacao_bd.ajuste_1_estagio",
        "src.tools.eureca.scripts_consolidacao_bd.ajuste_2_estudante",
        "src.tools.eureca.scripts_consolidacao_bd.ajuste_3_inscricao",
        "src.tools.eureca.scripts_consolidacao_bd.ajuste_4_professor",
        #"src.tools.eureca.scripts_consolidacao_bd.3_criar_chaves_estrangeiras",
    ]

    for modulo in MODULOS:
        print(f"\n{'=' * 60}", flush=True)
        print(f">>> INICIANDO: {modulo}", flush=True)
        print(f"{'=' * 60}", flush=True)

        resultado = subprocess.run([sys.executable, "-m", modulo], check=False,)
        print(f"\n>>> FINALIZADO: {modulo}", flush=True)
        print(f">>> Código de saída: {resultado.returncode}", flush=True)

        if resultado.returncode != 0:
            print(f"\n!!! O módulo {modulo} falhou. Execução interrompida.", flush=True,)
            sys.exit(resultado.returncode)

    print("\nTodos os ajustes foram executados com sucesso.", flush=True)


def main():

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    logger = logging.getLogger(__name__)
    logger.info("Iniciando script ufcg.sqlite...")


    if SCRIPTS or CONSOLIDAR_BANCO:
        for script in SCRIPTS:
            logger.info(f"\n========== {script}.py ==========")
            resultado = subprocess.run([sys.executable, "-m", f"src.tools.eureca.scripts_consolidacao_bd.{script}"])
            if resultado.returncode != 0:
                logger.info(f"ERRO ao executar {script}.py")
                return
        logger.info("\n========== TODOS OS DOWNLOADS CONCLUÍDOS ==========")


        if CONSOLIDAR_BANCO:
            logger.info(f"\n\n========== CONSOLIDANDO DADOS ==========")
            consolidar_banco_dados_final()
            logger.info(f"\n\n========== BANCO CONSOLIDADO ==========")


        if SUBSTITUIR_BANCOS:
            subprocess.run(["rm", "-f", "ufcg_old.sqlite"], check=True)
            subprocess.run(["mv", "ufcg.sqlite", "ufcg_old.sqlite"], check=True)
            subprocess.run(["cp", f"{current_dir}/banco_de_dados_consolidado/ufcg.sqlite", "ufcg.sqlite"], check=True)


        if REGISTRAR_MUDANCAS:
            logger.info("\n========== REGISTRANDO MUDANÇAS ==========")
            registrar_mudancas(
                scripts_executados=SCRIPTS,
                caminho_db_antigo="ufcg_old.sqlite",
                caminho_db_novo="ufcg.sqlite",
                caminho_historico=CAMINHO_HISTORICO,
            )
            
        if EXECUTAR_AGENTE_ANOMALIAS:
            subprocess.run([sys.executable, "-m", "src.agents.anomaly_agent"])


if __name__ == "__main__":
    main()
