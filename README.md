# Agents4Good: Eureca Chat

> Este projeto tem como objetivo criar um sistema de agentes inteligentes capazes de responder perguntas relacionadas à Universidade Federal de Campina Grande (UFCG), usando dados reais obtidos pela [API oficial Eureca](https://eureca.sti.ufcg.edu.br/), para fornecer respostas precisas e contextualizadas. O sistema funciona como um chatbot.

Esta é a **V2 do EurecaChat**, atualizada para as novas versões do LangChain e
LangGraph e com uma nova interface desenvolvida em React/Next.js.

---
## 🏛️ Arquitetura

O fluxo principal da V2 é implementado como um grafo de estados do LangGraph.
Cada mensagem passa primeiro por uma validação de segurança. Quando permitida,
ela segue para um único agente especializado, construído com `create_agent` do
LangChain, que seleciona e executa as ferramentas necessárias para responder à
pergunta. Mensagens bloqueadas recebem uma resposta segura e encerram o fluxo
sem executar o agente.

| **Componente** | **Responsabilidade** |
|----------------|----------------------|
| `CheckUserMessage` | Atua como guardrail de entrada. Classifica a mensagem, remove conteúdo interno de validação e decide entre encerrar o fluxo com uma resposta segura ou encaminhá-lo ao agente. |
| `AgentNode` | Executa o agente especializado do EurecaChat, responsável por interpretar a solicitação, chamar ferramentas e produzir a resposta final. |
| Ferramentas | Consultam informações acadêmicas sobre cursos, currículos, disciplinas, turmas, horários, calendários, setores, estudantes, professores e o portal da UFCG. |
| Middlewares | Adicionam contexto, filtram ferramentas conforme o perfil do usuário, tratam erros, registram a execução e resumem conversas longas. |
| Memória e persistência | O `AsyncPostgresSaver` mantém os checkpoints do LangGraph por `thread_id`. Para usuários autenticados, o `thread_id` corresponde ao chat salvo; sessões anônimas têm seus checkpoints removidos ao desconectar. |
| API e tempo real | O Quart disponibiliza autenticação e histórico por HTTP, enquanto o Socket.IO transmite status, tokens e a resposta final. |
| Frontend | A aplicação React/Next.js é exportada como site estático, servida pelo Quart e integrada às APIs e ao Socket.IO. |

---
## 🚀 Instalação e deploy

Para instalar basta executar o código abaixo:

```
docker compose up -d --build
```

O build é único: o Docker compila o frontend Next/React como site estático e o
Quart serve tudo na porta `8000`. Não é necessário publicar uma segunda porta
para o frontend. Em desenvolvimento, use `npm run dev` em `frontend/` e defina
`NEXT_PUBLIC_API_URL=http://localhost:8000` e
`NEXT_PUBLIC_SOCKET_URL=http://localhost:8000`.

Variáveis novas importantes:

- `APP_ORIGIN`: origem exata permitida no CORS/Socket.IO (localmente,
  `http://localhost:8000`; no deploy, use a URL pública sem barra final). O
  valor `*` funciona apenas sem credenciais CORS e não deve ser usado quando o
  frontend estiver em outro domínio.
- `COOKIE_SECURE=true`: para quando o deploy público usa HTTPS.

Diagnóstico via endpoint:

- `GET /api/health/live`: confirma que o processo HTTP responde.
- `GET /api/health/ready`: confirma Postgres, checkpointer/agente e informa a
  versão/commit implantado.
- Phoenix na porta `6006`; OBS: a interface só será externa se a plataforma de deploy publicar essa porta ou configurar uma rota dedicada.

---
## 👩🏻‍💻 Uso

1. Utilizando o Quart

Para executar o chatbot com uma mini aplicação Quart que serve um front-end, basta executar o código abaixo:

```
hypercorn application.app:sio_app
```

---
## 🤝 Contribuição
Contribuições são bem-vindas! 
Siga os passos abaixo para colaborar: 
- Faça um fork do repositório;
- Modifique o que desejar e crie um pull request;
- Detalhe o pull request. Descreva suas alterações.
---

## 📜 Licença
Este projeto é licenciado sob a MIT - License
- Eureca - UFCG
