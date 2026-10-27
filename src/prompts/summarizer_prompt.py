DEFAULT_SUMMARIZER_PROMPT = """
Resuma o histórico de conversa a seguir, mantendo as informações importantes:

<INICIO_DO_HISTORICO>
{messages}
</FIM_DO_HISTORICO>

## IMPORTANTE:
- O resumo deve manter a essência das perguntas e respostas e não deve ser longo.
- Seja direto e evite repetições.
- Se atente a informações importantes, essas informações não devem ficar de fora.
- Responda apenas com o resumo, sem informações adicionais.
"""