# Observabilidade de serviços com Grafana Alloy

O Alloy coleta métricas operacionais do backend, PostgreSQL e Phoenix pela rede
interna do Docker e as envia ao Prometheus gerenciado pelo Grafana Cloud. Ele
também lê os logs JSON do backend em um volume dedicado e os envia ao Loki.
Não são usados modo privilegiado, socket Docker nem mounts do host.

Nesta etapa, logs dos outros containers e métricas da VM/runtime dos containers
não são coletados.
O dashboard antigo `eurecachat-infraestrutura.json` foi preservado como
histórico, mas seus painéis de Loki, host e cAdvisor não recebem novos dados
com esta configuração.

## Fluxo

```text
Backend :9464 ────┐
PostgreSQL :5432 ─┼─> Alloy ─> Grafana Cloud Prometheus
Phoenix :9090 ────┘
Backend JSONL ────────> Alloy ─> Grafana Cloud Loki
```

As portas `9464` do backend e `9090` do Phoenix não são publicadas no host: elas
ficam disponíveis somente na rede do Compose. Os traces de LLM continuam
armazenados e visualizados no próprio Phoenix; os endpoints Prometheus contêm
apenas métricas operacionais.

## Credenciais da VM

Preencha somente no `.env` da VM:

```env
OBSERVABILITY_ENVIRONMENT=production
OBSERVABILITY_INSTANCE=nome-da-vm

GRAFANA_CLOUD_METRICS_URL=https://.../api/prom/push
GRAFANA_CLOUD_METRICS_USERNAME=...
GRAFANA_CLOUD_LOKI_URL=https://.../loki/api/v1/push
GRAFANA_CLOUD_LOKI_USERNAME=...
GRAFANA_CLOUD_API_KEY=glc_...

# Gere uma senha exclusiva; não reutilize POSTGRES_PASSWORD.
POSTGRES_MONITOR_PASSWORD=uma-senha-forte-e-exclusiva
```

Crie uma access policy/token com os escopos `metrics:write` e `logs:write`. O
token é exibido uma única vez pelo Grafana Cloud; não o adicione ao Git nem o
envie em mensagens.

## Subida e verificação

Na VM Linux, com o `.env` preenchido:

```bash
docker compose --profile observability up -d --build
docker compose --profile observability ps -a
docker compose --profile observability logs --tail=100 alloy
```

O resultado esperado é:

- `postgres_monitor_setup` finalizado com código `0`;
- `alloy`, `backend`, `phoenix` e `postgres` em execução;
- nenhuma porta do Alloy, `9464` do backend ou `9090` do Phoenix publicada no host;
- ausência de erros de configuração nos logs do Alloy.

No Grafana Cloud, em **Explore > Metrics**, consulte:

```promql
up{project="eurecachat", job=~"integrations/(backend|postgres|phoenix)"}
```

Devem aparecer os três jobs com valor `1`.

No Grafana Cloud, em **Explore**, selecione a fonte Loki e consulte:

```logql
{project="eurecachat", environment="production", service="backend"}
```

O backend mantém no máximo o arquivo ativo e dois backups de 10 MiB. Os mesmos
logs continuam disponíveis no stdout por meio de `docker compose logs backend`.

Para conferir diretamente as métricas do backend:

```bash
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:9464/metrics', timeout=10).read().decode())"
```

Para conferir diretamente as métricas do Phoenix pela rede interna, use um
container que já possua Python:

```bash
docker compose exec backend python -c "import urllib.request; print(urllib.request.urlopen('http://phoenix:9090/metrics', timeout=10).read().decode())"
```

## Monitor PostgreSQL

O profile executa uma tarefa idempotente chamada `postgres_monitor_setup`. Ela
cria ou atualiza o usuário técnico fixo `eureca_monitor`, concede somente o
papel nativo `pg_monitor` e remove permissões de escrita no banco da aplicação.
O exporter PostgreSQL embutido no Alloy usa exclusivamente essa credencial.

O coletor `stat_statements` permanece desativado, portanto textos de consultas
SQL não são enviados ao Grafana.

Para confirmar que a conta não escreve nas tabelas da aplicação:

```bash
docker compose --profile observability run --rm --no-deps postgres_monitor_setup sh -lc 'PGPASSWORD="$POSTGRES_MONITOR_PASSWORD" psql -h postgres -U eureca_monitor -d "$POSTGRES_MONITOR_DATABASE" -v ON_ERROR_STOP=1 -c "UPDATE public.users SET nome = nome WHERE false"'
```

O comando deve falhar com `cannot execute UPDATE in a read-only transaction`
ou `permission denied`.

## Dashboards

- `dashboards/eurecachat-servicos.json`: dashboard atual, baseado somente nas
  métricas permitidas do backend, PostgreSQL e Phoenix.
- `dashboards/eurecachat-agente.json`: visão do relatório do agente no Grafana,
  com turnos, ferramentas, latência, erros e tokens.
- `dashboards/eurecachat-infraestrutura.json`: dashboard anterior, preservado
  sem modificações.

Para importar o novo dashboard, abra **Dashboards > New > Import**, envie
`eurecachat-servicos.json` e associe as fontes
`grafanacloud-<stack>-prom` para métricas e `grafanacloud-<stack>-logs` para
logs quando solicitado.

Para a visão do agente, importe também `eurecachat-agente.json` e associe as
mesmas fontes Prometheus e Loki. As métricas de ferramentas e tokens passam a
ser emitidas pelo backend quando `ENABLE_GRAFANA_OBSERVABILITY=true`; traces,
prompts e mensagens continuam disponíveis no Phoenix.

O dashboard atual apresenta, nesta ordem:

- backend: disponibilidade, CPU, memória, HTTP, Socket.IO e processamento de chats;
- PostgreSQL: conexões, transações, deadlocks, cache e tamanho dos bancos;
- Phoenix: CPU, memória, fila e rejeições de spans, erros e tempo de inserção.
- logs: eventos JSON integrais emitidos pelo backend.

## Limitação intencional

Sem cAdvisor, socket Docker ou acesso ao host, não existem métricas reais de
CPU, memória, rede, filesystem, OOM ou reinicialização por container. CPU e
memória do backend e Phoenix representam somente seus respectivos processos.
Essa limitação evita conceder ao Alloy permissões equivalentes às de
administração da VM.
