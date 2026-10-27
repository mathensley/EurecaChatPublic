"""
Script de validação de dados com Great Expectations.

Estrutura:
    src/data_validation/
    run_validation.py               este script (runner genérico)
    expectations_estudantes_ufcg.py suite para estudantes_ufcg.sqlite
    └expectations_matriculas_ufcg.py suite para matriculas_ufcg.sqlite

Uso:
    # Apenas validar (saída no terminal):
    python src/data_validation/run_validation.py

    # Validar E gerar relatório HTML:
    python src/data_validation/run_validation.py --report

O script é somente leitura: não altera nenhum dado dos bancos SQLite.
O relatório HTML é gerado em: src/data_validation/gx_project/gx/uncommitted/data_docs/
"""

import os
import sys
import webbrowser
import great_expectations as gx
from great_expectations.checkpoint import UpdateDataDocsAction
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from expectations_estudantes_ufcg import build_suite as build_suite_estudantes
from expectations_matriculas_ufcg import build_suite as build_suite_matriculas

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Diretório onde o GX vai persistir suites, resultados e Data Docs
GX_PROJECT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "gx_project")

DATABASES = [
    {
        "db_file":    "estudantes_ufcg.sqlite",
        "table":      "estudantes_ufcg",
        "build_suite": build_suite_estudantes,
    },
    # {
    #     "db_file":    "matriculas_ufcg.sqlite",
    #     "table":      "matriculas_ufcg",
    #     "build_suite": build_suite_matriculas,
    # },
]


def print_results(results, table_name: str) -> None:
    """Imprime um relatório legível dos resultados de validação."""
   
    print(f"Resultados: {table_name}")
    print(f"Sucesso geral: {'PASSOU' if results.success else 'FALHOU'}")
    print()

    passed = 0
    failed = 0

    for result in results.results:
        exp_type = result.expectation_config.type
        column   = result.expectation_config.kwargs.get("column", "—")
        success  = result.success

        if success:
            passed += 1
            status = "V"
        else:
            failed += 1
            status = "X"

        print(f"{status} [{column}] {exp_type}")

        # Detalhes de falha
        if not success:
            exc = result.exception_info if hasattr(result, "exception_info") else {}
            if exc and exc.get("raised_exception"):
                print(f"Erro: {exc.get('exception_message', '')}")
            else:
                res = result.result or {}
                unexpected_count = res.get("unexpected_count")
                unexpected_pct   = res.get("unexpected_percent")
                if unexpected_count is not None:
                    print(f"Valores inesperados: {unexpected_count:,} ({unexpected_pct:.2f}%)")

    print(f"\nTotal: {passed + failed} expectations | {passed} passaram | {failed} falharam\n")
  

#Geração de relatório HTML
def generate_report(context, open_browser: bool = True) -> str:
    """
    Gera o relatório HTML usando a função build_data_docs() do Great Expectations.

    O GX lê todos os ValidationResults já salvos no contexto e produz um site
    Args:
        context: Contexto GX com modo 'file'.
        open_browser: Se True, abre o relatório automaticamente no navegador.
    Returns:
        Caminho absoluto para o index.html gerado.
    """
    print("\nGerando relatório HTML (Data Docs)...")


    sites_info = context.build_data_docs()
    report_url = None
    for site_name, site_data in sites_info.items():
        local_path = site_data
        if local_path:
            report_url = local_path
            print(f"Relatório [{site_name}]: {local_path}")
            break

    if report_url and open_browser:
        webbrowser.open(report_url)
        print("Relatório aberto no navegador.")
    elif not report_url:
        print("Aviso: nao foi possivel determinar o caminho do relatorio.")

    return report_url or ""


def validate_database(context, config: dict) -> bool:
    """
    Conecta ao banco, aplica a suite de expectations e retorna True se passou.

    Args:
        context: Contexto GX com modo 'file'.
        config: Dicionário com 'db_file', 'table' e 'build_suite'.

    Returns:
        True se todas as expectations passaram, False caso contrário.
    """
    db_file     = config["db_file"]
    table       = config["table"]
    build_suite = config["build_suite"]

    print(f"\nIniciando validação: {db_file} → {table}")

    db_path = os.path.join(BASE_DIR, "sqlite", db_file)
    if not os.path.exists(db_path):
        print(f"  [ERRO] Banco nao encontrado: {db_path}")
        return False

    sqlite_url = f"sqlite:///{db_path}"

    # Data Source — add_or_update evita erro "already exists" em re-execuções
    data_source = context.data_sources.add_or_update_sqlite(
        name=f"source_{table}",
        connection_string=sqlite_url,
    )

    # Asset e Batch
    asset = data_source.add_table_asset(name=f"asset_{table}", table_name=table)
    batch_definition = asset.add_batch_definition_whole_table(f"batch_{table}")

    # Suite de expectations (construída pelo módulo específico da tabela)
    suite = build_suite()
    context.suites.add_or_update(suite)

    # Validation Definition
    validation_def = gx.ValidationDefinition(
        name=f"validation_{table}",
        data=batch_definition,
        suite=suite,
    )
    context.validation_definitions.add_or_update(validation_def)

    # ── Checkpoint com UpdateDataDocsAction ───────────────────────────────────
    # O Checkpoint executa a validação e dispara ações pós-resultado.
    # UpdateDataDocsAction: persiste os ValidationResults no contexto de arquivo,
    # garantindo que generate_report() / build_data_docs() os inclua no HTML.
    checkpoint = gx.Checkpoint(
        name=f"checkpoint_{table}",
        validation_definitions=[validation_def],
        actions=[
            UpdateDataDocsAction(name="update_data_docs"),
        ],
        result_format="COMPLETE",
        
    )
    context.checkpoints.add_or_update(checkpoint)
    checkpoint_result = checkpoint.run()

    for _key, results in checkpoint_result.run_results.items():
        print_results(results, table)

    return checkpoint_result.success


def main():
    gerar_relatorio = "--report" in sys.argv

    print("\n" + "═" * 60)
    print(" Great Expectations — Validacao de Dados UFCG")
    if gerar_relatorio:
        print("Relatorio HTML")
    print("═" * 60)

    # Contexto com modo 'file': persiste suites, resultados e Data Docs em disco.
    # Necessário para que build_data_docs() consiga construir o relatório HTML.
    os.makedirs(GX_PROJECT_DIR, exist_ok=True)
    context = gx.get_context(mode="file", project_root_dir=GX_PROJECT_DIR)

    overall_success = True
    for db_config in DATABASES:
        success = validate_database(context, db_config)
        if not success:
            overall_success = False

    print("═" * 60)
    if overall_success:
        print("Todas as validacoes passaram.")
    else:
        print("Uma ou mais validacoes falharam. Revise o relatorio acima.")
    print("═" * 60 + "\n")

    if gerar_relatorio:
        generate_report(context, open_browser=True)

    sys.exit(0 if overall_success else 1)


if __name__ == "__main__":
    main()
