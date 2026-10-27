import React, { useEffect, useMemo, useState } from "react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Cell,
} from "recharts";

/* ============================================================================
 * PhoenixDashboard
 * ----------------------------------------------------------------------------
 * Dashboard de observabilidade para agentes de IA instrumentados com o
 * Arize Phoenix. Mostra:
 *   - tempo de execução por ferramenta (com botão para alternar para a taxa
 *     de uso, isto é, a participação de cada ferramenta no total de chamadas)
 *   - tokens consumidos por ferramenta
 *   - número de execuções de cada ferramenta por turno
 *     (turno = prompt do usuário + resposta final do agente)
 *   - usuários ativos por dia (usuários distintos com ao menos um turno no dia)
 *   - padrão de uso por dia + hora (tokens / tempo / turnos), para achar picos
 *   - ranking de ferramentas por número de erros no período/horário filtrados, com
 *     detalhe de cada erro (chat, quando, duração, mensagem completa)
 * Com filtros por data e por faixa de horário, além de seleção de ferramentas.
 *
 * Dependência extra: recharts
 *   npm install recharts
 *
 * O componente já vem com um gerador de dados fictícios (mock) para
 * funcionar sozinho. Para plugar nos dados reais do Phoenix, passe a prop
 * `turns` no formato `Turn[]` definido abaixo — normalmente escrevendo um
 * adaptador que transforma as respostas da API de traces do Phoenix (spans
 * com atributos como openinference.span.kind, llm.token_count.*,
 * status_code, session.id etc.) nesse mesmo formato: os spans de uma trace
 * viram um `Turn` (o `session.id` do Phoenix pode virar o `chatId`, e um
 * atributo como `user.id`, quando presente na trace, vira o `userId`), e os
 * spans do tipo TOOL viram `ToolExecution[]`.
 * ==========================================================================*/

/* ---------------------------------- Tipos --------------------------------- */

export interface ToolExecution {
  id: string;
  toolName: string;
  turnId: string;
  startTime: string; // ISO 8601
  endTime: string; // ISO 8601
  durationMs: number;
  tokensInput: number;
  tokensOutput: number;
  status: "success" | "error";
  errorType?: string;
  errorMessage?: string;
}

export interface LLMUsage {
  id: string;
  turnId: string;
  modelName?: string;
  startTime: string;
  endTime: string;
  durationMs: number;
  tokensInput: number;
  tokensOutput: number;
  tokensCacheRead?: number;
  status: "success" | "error";
  errorType?: string;
  errorMessage?: string;
}

export interface Turn {
  id: string;
  /** Identifica a conversa/sessão à qual o turno pertence (ex: session.id do Phoenix). */
  chatId: string;
  /**
   * Identifica o usuário dono da conversa (ex: atributo user.id anexado à
   * trace no Phoenix). Opcional: se ausente, o dashboard usa o `chatId` como
   * aproximação de "usuário" — o que ainda funciona bem para contar
   * usuários ativos, mas superestima o total quando o mesmo usuário abre
   * várias conversas no período.
   */
  userId?: string;
  timestamp: string; // ISO 8601 — início do turno
  userPrompt?: string;
  agentResponse?: string;
  executions: ToolExecution[];
  llmUsages?: LLMUsage[];
}

export interface PhoenixDashboardProps {
  /** Turnos já carregados do Phoenix. Se omitido, usa dados fictícios (mock). */
  turns?: Turn[];
}

/* ------------------------------ Dados fictícios ---------------------------- */

const MOCK_TOOLS = [
  "buscar_na_web",
  "consultar_banco_dados",
  "gerar_documento",
  "transcrever_audio",
  "enviar_email",
  "chamar_llm",
] as const;

const ERROR_TYPES = [
  "TimeoutError",
  "ValidationError",
  "RateLimitError",
  "ConnectionError",
  "ToolNotFoundError",
];

const DAYS_OF_MOCK_DATA = 30;
const NUM_MOCK_USERS = 16;
const MOCK_USER_IDS = Array.from(
  { length: NUM_MOCK_USERS },
  (_, i) => `user-${String(i + 1).padStart(2, "0")}`
);

function pick<T>(arr: readonly T[]): T {
  return arr[Math.floor(Math.random() * arr.length)];
}

/** Simula um padrão de uso com picos de manhã e, principalmente, à tarde. */
function hourWeight(hour: number): number {
  if (hour >= 9 && hour <= 11) return 1.6; // pico da manhã
  if (hour >= 14 && hour <= 17) return 2.2; // pico da tarde (o mais alto)
  if (hour >= 19 && hour <= 21) return 0.9; // uso leve à noite
  if (hour <= 6) return 0.12; // madrugada, quase nada
  return 0.5; // demais horários
}

function buildErrorMessage(toolName: string): string {
  const templates = [
    `Falha ao executar "${toolName}": o serviço respondeu com HTTP 504 após 30s de espera. A requisição foi reenviada automaticamente 2 vezes antes de desistir. Verifique se o serviço externo está disponível e se o timeout configurado é suficiente para o volume atual de dados.`,
    `Erro de validação em "${toolName}": o parâmetro "input_id" veio vazio no payload recebido do orquestrador. Isso normalmente acontece quando o passo anterior do pipeline não populou corretamente o contexto compartilhado entre as ferramentas.`,
    `"${toolName}" atingiu o limite de requisições do provedor (429 Too Many Requests). O agente tentou novamente após um backoff exponencial, mas o limite ainda estava ativo. Considere distribuir as chamadas ao longo do tempo ou pedir um limite maior.`,
    `Conexão recusada ao chamar "${toolName}": o host de destino não respondeu na porta configurada. Pode ser uma instabilidade temporária de rede ou o serviço estar fora do ar no momento da chamada.`,
    `"${toolName}" não está registrada no runtime do agente para este ambiente. Verifique se o manifesto de ferramentas foi atualizado após o último deploy.`,
  ];
  return pick(templates);
}

function generateMockTurns(): Turn[] {
  const turns: Turn[] = [];
  const now = new Date();
  const daysWithTurns = new Set<string>();

  let turnCounter = 0;
  let chatCounter = 0;
  let turnsInCurrentChat = 0;
  let currentChatId = `chat-${String(++chatCounter).padStart(3, "0")}`;
  let currentUserId = pick(MOCK_USER_IDS);
  let turnsUntilNewChat = 2 + Math.floor(Math.random() * 5);

  function pushTurn(turnStart: Date) {
    if (turnsInCurrentChat >= turnsUntilNewChat) {
      currentChatId = `chat-${String(++chatCounter).padStart(3, "0")}`;
      currentUserId = pick(MOCK_USER_IDS);
      turnsInCurrentChat = 0;
      turnsUntilNewChat = 2 + Math.floor(Math.random() * 5);
    }
    turnsInCurrentChat++;

    const loadFactor = hourWeight(turnStart.getHours()); // picos tendem a ter chamadas um pouco mais pesadas
    const execCount = 1 + Math.floor(Math.random() * 4);
    const executions: ToolExecution[] = [];
    let cursor = turnStart.getTime();

    for (let j = 0; j < execCount; j++) {
      const toolName = pick(MOCK_TOOLS);
      const durationMs = Math.round((120 + Math.random() * 2200) * (0.7 + loadFactor * 0.3));
      const start = new Date(cursor);
      const end = new Date(cursor + durationMs);
      cursor = end.getTime() + Math.floor(Math.random() * 400);
      const isError = Math.random() < 0.09;

      executions.push({
        id: `exec-${turnCounter}-${j}`,
        toolName,
        turnId: `turn-${turnCounter}`,
        startTime: start.toISOString(),
        endTime: end.toISOString(),
        durationMs,
        tokensInput: Math.round((60 + Math.random() * 420) * (0.7 + loadFactor * 0.3)),
        tokensOutput: Math.round((20 + Math.random() * 260) * (0.7 + loadFactor * 0.3)),
        status: isError ? "error" : "success",
        errorType: isError ? pick(ERROR_TYPES) : undefined,
        errorMessage: isError ? buildErrorMessage(toolName) : undefined,
      });
    }

    turns.push({
      id: `turn-${turnCounter}`,
      chatId: currentChatId,
      userId: currentUserId,
      timestamp: turnStart.toISOString(),
      userPrompt: `Pergunta de exemplo #${turnCounter + 1} feita pelo usuário.`,
      agentResponse: `Resposta final gerada pelo agente para o turno #${turnCounter + 1}.`,
      executions,
    });
    daysWithTurns.add(formatDateInput(turnStart));
    turnCounter++;
  }

  for (let dayOffset = DAYS_OF_MOCK_DATA - 1; dayOffset >= 0; dayOffset--) {
    for (let hour = 0; hour < 24; hour++) {
      const expected = hourWeight(hour) * (0.6 + Math.random() * 0.8);
      const numTurnsThisHour = Math.round(expected);

      for (let k = 0; k < numTurnsThisHour; k++) {
        const turnStart = new Date(now);
        turnStart.setDate(turnStart.getDate() - dayOffset);
        turnStart.setHours(hour, Math.floor(Math.random() * 60), Math.floor(Math.random() * 60), 0);
        if (turnStart.getTime() > now.getTime()) continue; // não gerar turnos no futuro
        pushTurn(turnStart);
      }
    }
  }

  // Garante que nenhum dia do período fique sem nenhum turno só por azar do
  // sorteio acima (horas de menor movimento podem arredondar pra zero) — sem
  // isso, o heatmap e o gráfico de usuários ativos podiam "pular" dias e dar
  // a falsa impressão de que o histórico é mais curto do que DAYS_OF_MOCK_DATA.
  for (let dayOffset = DAYS_OF_MOCK_DATA - 1; dayOffset >= 0; dayOffset--) {
    const day = new Date(now);
    day.setDate(day.getDate() - dayOffset);
    const dayKey = formatDateInput(day);
    if (daysWithTurns.has(dayKey)) continue;
    day.setHours(15, Math.floor(Math.random() * 60), 0, 0); // horário de pico da tarde
    if (day.getTime() > now.getTime()) day.setTime(now.getTime() - 60000);
    pushTurn(day);
  }

  return turns.sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime());
}

/* --------------------------------- Paleta ---------------------------------- */

const PALETTE = [
  "#E8A33D", // âmbar
  "#4FB3A9", // teal
  "#6C8EEF", // azul
  "#C97BD6", // lilás
  "#7FCB6B", // verde
  "#E5788A", // rosa
  "#54B8E0", // ciano
  "#D6A75B", // areia
];

function colorForTool(toolName: string, allTools: string[]): string {
  const idx = allTools.indexOf(toolName);
  return PALETTE[idx % PALETTE.length];
}

/* --------------------------------- Custo ------------------------------------ */

/**
 * Preço estimado por 1.000 tokens, usado só para calcular o "custo" no
 * gráfico de tempo/custo/uso por ferramenta. Esses valores são um
 * placeholder — ajuste para bater com o preço real do(s) modelo(s) usados
 * pelo agente (ou passe um valor diferente por ferramenta, se cada uma
 * chamar um modelo diferente).
 */
const PRICE_PER_1K_INPUT_TOKENS_USD = 0.003;
const PRICE_PER_1K_OUTPUT_TOKENS_USD = 0.015;

function estimateCostUsd(tokensInput: number, tokensOutput: number): number {
  return (
    (tokensInput / 1000) * PRICE_PER_1K_INPUT_TOKENS_USD +
    (tokensOutput / 1000) * PRICE_PER_1K_OUTPUT_TOKENS_USD
  );
}

function formatCostUsd(usd: number): string {
  return usd < 0.01 ? `$${usd.toFixed(4)}` : `$${usd.toFixed(2)}`;
}

const COLOR_ERROR = "#E5484D";

type HeatmapMetric = "tokens" | "duration" | "turns";

const METRIC_RGB: Record<HeatmapMetric, string> = {
  tokens: "232,163,61",
  duration: "79,179,169",
  turns: "108,142,239",
};

const METRIC_LABEL: Record<HeatmapMetric, string> = {
  tokens: "Tokens",
  duration: "Tempo",
  turns: "Turnos",
};

/* --------------------------------- Estilos ---------------------------------- */

const styles = `
  .phx-root {
    --phx-bg: #12161d;
    --phx-panel: #1b212b;
    --phx-panel-border: #2a3140;
    --phx-text: #e6e9ef;
    --phx-muted: #8b94a7;
    font-family: -apple-system, "Inter", "Segoe UI", system-ui, sans-serif;
    background: var(--phx-bg);
    color: var(--phx-text);
    padding: 28px;
    border-radius: 14px;
    max-width: 1240px;
    margin: 0 auto;
  }
  .phx-header { display:flex; flex-direction:column; gap:4px; margin-bottom:22px; }
  .phx-title { font-size: 22px; font-weight: 600; letter-spacing: -0.01em; }
  .phx-subtitle { font-size: 13.5px; color: var(--phx-muted); }

  .phx-filters {
    display:flex; flex-wrap:wrap; align-items:flex-end; gap:16px;
    background: var(--phx-panel);
    border: 1px solid var(--phx-panel-border);
    padding: 16px 18px;
    border-radius: 10px;
    margin-bottom: 22px;
  }
  .phx-field { display:flex; flex-direction:column; gap:6px; }
  .phx-field label { font-size: 12px; color: var(--phx-muted); }
  .phx-field input[type="date"], .phx-field select {
    background: #12161d; border: 1px solid var(--phx-panel-border);
    color: var(--phx-text); border-radius: 6px; padding: 7px 9px; font-size: 13px;
  }
  .phx-hour-range { display:flex; align-items:center; gap:6px; }
  .phx-hour-range span { font-size: 12px; color: var(--phx-muted); }
  .phx-tool-toggles { display:flex; flex-wrap:wrap; gap:6px; max-width: 480px; }
  .phx-tool-chip {
    border: 1px solid var(--phx-panel-border); border-radius: 999px;
    padding: 5px 11px; font-size: 12.5px; cursor: pointer; user-select:none;
    background: transparent; color: var(--phx-muted); transition: all .12s ease;
  }
  .phx-tool-chip.active { color: #12161d; border-color: transparent; }
  .phx-reset-btn {
    border: 1px solid var(--phx-panel-border); background: transparent;
    color: var(--phx-muted); border-radius: 6px; padding: 7px 12px;
    font-size: 12.5px; cursor: pointer;
  }
  .phx-reset-btn:hover { color: var(--phx-text); border-color: #3a4356; }

  .phx-stats { display:grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 12px; margin-bottom: 22px; }
  .phx-stat {
    background: var(--phx-panel); border: 1px solid var(--phx-panel-border);
    border-radius: 10px; padding: 14px 16px;
  }
  .phx-stat-label { font-size: 12px; color: var(--phx-muted); margin-bottom: 6px; }
  .phx-stat-value { font-size: 22px; font-weight: 600; font-variant-numeric: tabular-nums; }
  .phx-stat-value.error { color: ${COLOR_ERROR}; }

  .phx-grid { display:grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
  .phx-panel {
    background: var(--phx-panel); border: 1px solid var(--phx-panel-border);
    border-radius: 10px; padding: 16px 18px 8px; margin-bottom: 16px;
  }
  .phx-panel-title { font-size: 14px; font-weight: 600; margin-bottom: 2px; }
  .phx-panel-desc { font-size: 12px; color: var(--phx-muted); margin-bottom: 10px; }

  .phx-metric-toggle { display:flex; gap:6px; margin-bottom: 12px; }

  .phx-empty { color: var(--phx-muted); font-size: 13px; padding: 18px 4px; }

  .phx-errors-layout { display:grid; grid-template-columns: 1fr 230px; gap: 16px; }
  .phx-error-list { display:flex; flex-direction:column; gap:10px; max-height: 440px; overflow-y:auto; padding-right:4px; }
  .phx-error-card { background:#12161d; border:1px solid var(--phx-panel-border); border-radius:8px; padding:10px 12px; }
  .phx-error-card-head { display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; font-size:13px; }
  .phx-error-meta { margin-bottom:6px; }
  .phx-error-message { font-size:13px; line-height:1.5; color: var(--phx-text); }
  .phx-link-btn { background:none; border:none; color:#6C8EEF; font-size:12px; padding:4px 0 0; cursor:pointer; }
  .phx-mono { font-family: "SFMono-Regular", Consolas, "Liberation Mono", monospace; font-size: 12px; color: var(--phx-muted); }
  .phx-error-badge {
    display:inline-block; background: rgba(229,72,77,0.14); color: ${COLOR_ERROR};
    border-radius: 5px; padding: 2px 7px; font-size: 11.5px; font-weight: 500;
  }
  .phx-error-rank { display:flex; flex-direction:column; gap:4px; }
  .phx-error-rank-title { font-size: 12px; color: var(--phx-muted); margin-bottom: 4px; }
  .phx-rank-item {
    display:flex; justify-content:space-between; gap:8px; background:transparent;
    border:1px solid var(--phx-panel-border); border-radius:7px; padding:7px 10px;
    font-size:12.5px; color:var(--phx-text); cursor:pointer; text-align:left;
  }
  .phx-rank-item.active { border-color:#e8a33d; background: rgba(232,163,61,0.12); }

  @media (max-width: 860px) {
    .phx-stats { grid-template-columns: repeat(2, 1fr); }
    .phx-grid { grid-template-columns: 1fr; }
    .phx-errors-layout { grid-template-columns: 1fr; }
  }
`;

/* --------------------------------- Helpers ---------------------------------- */

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatDateInput(d: Date): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "America/Fortaleza",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(d);
  const get = (type: string) => parts.find((part) => part.type === type)?.value || "00";
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function hourInObservabilityTimezone(d: Date): number {
  const hour = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Fortaleza",
    hour: "2-digit",
    hourCycle: "h23",
  }).formatToParts(d).find((part) => part.type === "hour")?.value;
  return Number(hour || 0);
}

/** Usa userId quando disponível; caso contrário, cai para chatId como aproximação de "usuário". */
function getUserId(turn: Turn): string {
  return turn.userId ?? turn.chatId;
}

function formatShortDate(dayKey: string): string {
  const [, m, d] = dayKey.split("-");
  return `${d}/${m}`;
}

function hourInRange(hour: number, from: number, to: number): boolean {
  if (from <= to) return hour >= from && hour <= to;
  return hour >= from || hour <= to; // faixa que cruza a meia-noite, ex: 22h às 4h
}

function formatMetricValue(value: number, metric: HeatmapMetric): string {
  if (metric === "tokens") return value.toLocaleString("pt-BR");
  if (metric === "duration") return formatDuration(value);
  return String(value);
}

function heatCellColor(value: number, max: number, metric: HeatmapMetric): string {
  if (max <= 0 || value === 0) return "rgba(255,255,255,0.05)";
  const alpha = 0.12 + (value / max) * 0.8;
  return `rgba(${METRIC_RGB[metric]}, ${alpha.toFixed(2)})`;
}

function buildHeatmap(turns: Turn[], metric: HeatmapMetric) {
  const matrix = new Map<string, number[]>();
  turns.forEach((t) => {
    const d = new Date(t.timestamp);
    const dayKey = formatDateInput(d);
    const hour = hourInObservabilityTimezone(d);
    if (!matrix.has(dayKey)) matrix.set(dayKey, new Array(24).fill(0));
    const row = matrix.get(dayKey)!;
    if (metric === "turns") {
      row[hour] += 1;
    } else if (metric === "tokens") {
      row[hour] += turnTokenCount(t);
    } else {
      row[hour] += turnDuration(t);
    }
  });
  const days = Array.from(matrix.keys()).sort();
  let max = 0;
  days.forEach((d) => matrix.get(d)!.forEach((v) => { if (v > max) max = v; }));
  return { days, matrix, max };
}

function turnTokenCount(turn: Turn): number {
  const llmUsages = turn.llmUsages || [];
  if (llmUsages.length) {
    return llmUsages.reduce((sum, usage) => sum + usage.tokensInput + usage.tokensOutput, 0);
  }
  return turn.executions.reduce((sum, execution) => sum + execution.tokensInput + execution.tokensOutput, 0);
}

function turnDuration(turn: Turn): number {
  return [
    ...turn.executions.map((execution) => execution.durationMs),
    ...(turn.llmUsages || []).map((usage) => usage.durationMs),
  ].reduce((sum, duration) => sum + duration, 0);
}

/* ================================= Componente ================================ */

export default function PhoenixDashboard({ turns: turnsProp }: PhoenixDashboardProps) {
  const allTurns = useMemo(() => turnsProp ?? generateMockTurns(), [turnsProp]);

  const allToolNames = useMemo(() => {
    const set = new Set<string>();
    allTurns.forEach((t) => t.executions.forEach((e) => set.add(e.toolName)));
    return Array.from(set).sort();
  }, [allTurns]);

  const minMaxDates = useMemo(() => {
    const ts = allTurns.map((t) => new Date(t.timestamp).getTime());
    return {
      min: ts.length ? new Date(Math.min(...ts)) : new Date(),
      max: ts.length ? new Date(Math.max(...ts)) : new Date(),
    };
  }, [allTurns]);

  const [dateFrom, setDateFrom] = useState(() => formatDateInput(minMaxDates.min));
  const [dateTo, setDateTo] = useState(() => formatDateInput(minMaxDates.max));
  const [hourFrom, setHourFrom] = useState(0);
  const [hourTo, setHourTo] = useState(23);
  const [selectedTools, setSelectedTools] = useState<Set<string>>(() => new Set(allToolNames));
  const [heatmapMetric, setHeatmapMetric] = useState<HeatmapMetric>("tokens");
  const [selectedErrorTool, setSelectedErrorTool] = useState<string | null>(null);
  const [expandedErrors, setExpandedErrors] = useState<Set<string>>(new Set());

  // O primeiro render ocorre com turns=[] enquanto a API ainda carrega.
  // Sincroniza os filtros quando os dados reais chegam, sem sobrescrever
  // alterações posteriores feitas pelo usuário.
  useEffect(() => {
    setDateFrom(formatDateInput(minMaxDates.min));
    setDateTo(formatDateInput(minMaxDates.max));
    setSelectedTools(new Set(allToolNames));
    setSelectedErrorTool(null);
  }, [minMaxDates.min.getTime(), minMaxDates.max.getTime(), allToolNames.join("\u0000")]);

  function toggleTool(tool: string) {
    setSelectedTools((prev) => {
      const next = new Set(prev);
      if (next.has(tool)) next.delete(tool);
      else next.add(tool);
      return next;
    });
  }

  function toggleExpanded(id: string) {
    setExpandedErrors((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function resetFilters() {
    setDateFrom(formatDateInput(minMaxDates.min));
    setDateTo(formatDateInput(minMaxDates.max));
    setHourFrom(0);
    setHourTo(23);
    setSelectedTools(new Set(allToolNames));
  }

  /* ----- turnos filtrados pelos controles do topo (data + hora + ferramentas) ----- */
  const filteredTurns = useMemo(() => {
    return allTurns
      .filter((t) => {
        const d = new Date(t.timestamp);
        const dayKey = formatDateInput(d);
        if (dayKey < dateFrom || dayKey > dateTo) return false;
        return hourInRange(hourInObservabilityTimezone(d), hourFrom, hourTo);
      })
      .map((t) => ({
        ...t,
        executions: t.executions.filter((e) => selectedTools.has(e.toolName)),
      }));
  }, [allTurns, dateFrom, dateTo, hourFrom, hourTo, selectedTools]);

  const filteredExecutions = useMemo(
    () => filteredTurns.flatMap((t) => t.executions),
    [filteredTurns]
  );

  const heatmap = useMemo(() => buildHeatmap(filteredTurns, heatmapMetric), [filteredTurns, heatmapMetric]);

  /* ----- estatísticas resumo ----- */

  const totalExecutions = filteredExecutions.length;
  const totalErrors = filteredExecutions.filter((e) => e.status === "error").length;
  const errorRate = totalExecutions ? (totalErrors / totalExecutions) * 100 : 0;
  const totalTokens = filteredTurns.reduce((sum, turn) => sum + turnTokenCount(turn), 0);
  const avgDurationMs = totalExecutions
    ? filteredExecutions.reduce((s, e) => s + e.durationMs, 0) / totalExecutions
    : 0;
  const totalActiveUsers = useMemo(() => {
    const set = new Set<string>();
    filteredTurns.forEach((t) => set.add(getUserId(t)));
    return set.size;
  }, [filteredTurns]);

  /* ----- tempo x custo x taxa de uso por ferramenta (mesmo painel, alternável) ----- */
  const [toolChartMetric, setToolChartMetric] = useState<"time" | "cost" | "usage">("time");

  const toolStats = useMemo(() => {
    const map = new Map<string, { total: number; count: number; costUsd: number }>();
    filteredExecutions.forEach((e) => {
      const cur = map.get(e.toolName) ?? { total: 0, count: 0, costUsd: 0 };
      cur.total += e.durationMs;
      cur.count += 1;
      cur.costUsd += estimateCostUsd(e.tokensInput, e.tokensOutput);
      map.set(e.toolName, cur);
    });
    return Array.from(map.entries()).map(([toolName, v]) => ({
      toolName,
      avgMs: Math.round(v.total / v.count),
      totalMs: v.total,
      count: v.count,
      costUsd: v.costUsd,
      sharePct: totalExecutions ? (v.count / totalExecutions) * 100 : 0,
    }));
  }, [filteredExecutions, totalExecutions]);

  const toolChartData = useMemo(() => {
    const sorted = [...toolStats];
    sorted.sort((a, b) => {
      if (toolChartMetric === "time") return b.avgMs - a.avgMs;
      if (toolChartMetric === "cost") return b.costUsd - a.costUsd;
      return b.count - a.count;
    });
    return sorted;
  }, [toolStats, toolChartMetric]);

  /* ----- tokens por ferramenta ----- */
  const tokensPerTool = useMemo(() => {
    const map = new Map<string, { input: number; output: number }>();
    filteredExecutions.forEach((e) => {
      const cur = map.get(e.toolName) ?? { input: 0, output: 0 };
      cur.input += e.tokensInput;
      cur.output += e.tokensOutput;
      map.set(e.toolName, cur);
    });
    return Array.from(map.entries())
      .map(([toolName, v]) => ({ toolName, ...v, total: v.input + v.output }))
      .sort((a, b) => b.total - a.total);
  }, [filteredExecutions]);

  /* ----- execuções por ferramenta, por turno (limitado aos últimos 30 p/ ficar legível) ----- */
  const execsPerTurnAll = useMemo(() => {
    return filteredTurns.map((t, idx) => {
      const row: Record<string, number | string> = {
        turnLabel: `#${idx + 1}`,
        timestamp: t.timestamp,
      };
      allToolNames.forEach((tool) => {
        row[tool] = t.executions.filter((e) => e.toolName === tool).length;
      });
      return row;
    });
  }, [filteredTurns, allToolNames]);
  const execsPerTurn = execsPerTurnAll.slice(-30);

  /* ----- usuários ativos por dia (mesmo filtro de data + hora de filteredTurns) ----- */
  const usersPerDay = useMemo(() => {
    const map = new Map<string, Set<string>>();
    filteredTurns.forEach((t) => {
      const dayKey = formatDateInput(new Date(t.timestamp));
      if (!map.has(dayKey)) map.set(dayKey, new Set());
      map.get(dayKey)!.add(getUserId(t));
    });
    return Array.from(map.entries())
      .map(([day, users]) => ({ day, dayLabel: formatShortDate(day), count: users.size }))
      .sort((a, b) => a.day.localeCompare(b.day));
  }, [filteredTurns]);

  /* ----- erros dentro do período, horário e ferramentas filtrados acima ----- */

  const filteredErrorEntries = useMemo(() => {
    const entries: Array<{
      id: string;
      chatId: string;
      toolName: string;
      timestamp: string;
      durationMs: number;
      errorType?: string;
      errorMessage?: string;
    }> = [];
    filteredTurns.forEach((t) => {
      t.executions.forEach((e) => {
        if (e.status !== "error") return;
        entries.push({
          id: e.id,
          chatId: t.chatId,
          toolName: e.toolName,
          timestamp: e.startTime,
          durationMs: e.durationMs,
          errorType: e.errorType,
          errorMessage: e.errorMessage,
        });
      });
    });
    return entries.sort((a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime());
  }, [filteredTurns]);

  const errorsByTool = useMemo(() => {
    const map = new Map<string, number>();
    filteredErrorEntries.forEach((e) => map.set(e.toolName, (map.get(e.toolName) ?? 0) + 1));
    return Array.from(map.entries())
      .map(([toolName, count]) => ({ toolName, count }))
      .sort((a, b) => b.count - a.count);
  }, [filteredErrorEntries]);

  const visibleErrorEntries = useMemo(() => {
    if (!selectedErrorTool) return filteredErrorEntries;
    return filteredErrorEntries.filter((e) => e.toolName === selectedErrorTool);
  }, [filteredErrorEntries, selectedErrorTool]);

  /* ----------------------------------- render ----------------------------------- */

  return (
    <div className="phx-root">
      <style>{styles}</style>

      <div className="phx-header">
        <div className="phx-title">Observabilidade do agente</div>
        <div className="phx-subtitle">
          Execuções de ferramentas capturadas via Phoenix — tempo, tokens e erros por turno.
        </div>
      </div>

      {/* Filtros */}
      <div className="phx-filters">
        <div className="phx-field">
          <label>De</label>
          <input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
        </div>
        <div className="phx-field">
          <label>Até</label>
          <input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
        </div>
        <div className="phx-field">
          <label>Faixa de horário</label>
          <div className="phx-hour-range">
            <select value={hourFrom} onChange={(e) => setHourFrom(Number(e.target.value))}>
              {Array.from({ length: 24 }).map((_, h) => (
                <option key={h} value={h}>{String(h).padStart(2, "0")}h</option>
              ))}
            </select>
            <span>até</span>
            <select value={hourTo} onChange={(e) => setHourTo(Number(e.target.value))}>
              {Array.from({ length: 24 }).map((_, h) => (
                <option key={h} value={h}>{String(h).padStart(2, "0")}h</option>
              ))}
            </select>
          </div>
        </div>
        <div className="phx-field" style={{ flex: 1, minWidth: 260 }}>
          <label>Ferramentas</label>
          <div className="phx-tool-toggles">
            {allToolNames.map((tool) => {
              const active = selectedTools.has(tool);
              const color = colorForTool(tool, allToolNames);
              return (
                <button
                  key={tool}
                  className={`phx-tool-chip${active ? " active" : ""}`}
                  style={active ? { background: color } : undefined}
                  onClick={() => toggleTool(tool)}
                  type="button"
                >
                  {tool}
                </button>
              );
            })}
          </div>
        </div>
        <button className="phx-reset-btn" onClick={resetFilters} type="button">
          Limpar filtros
        </button>
      </div>

      {/* Estatísticas resumo */}
      <div className="phx-stats">
        <div className="phx-stat">
          <div className="phx-stat-label">Turnos</div>
          <div className="phx-stat-value">{filteredTurns.length}</div>
        </div>
        <div className="phx-stat">
          <div className="phx-stat-label">Execuções de ferramentas</div>
          <div className="phx-stat-value">{totalExecutions}</div>
        </div>
        <div className="phx-stat">
          <div className="phx-stat-label">Tempo médio por execução</div>
          <div className="phx-stat-value">{formatDuration(Math.round(avgDurationMs))}</div>
        </div>
        <div className="phx-stat">
          <div className="phx-stat-label">Tokens totais</div>
          <div className="phx-stat-value">{totalTokens.toLocaleString("pt-BR")}</div>
        </div>
        <div className="phx-stat">
          <div className="phx-stat-label">Erros ({errorRate.toFixed(1)}%)</div>
          <div className={`phx-stat-value${totalErrors ? " error" : ""}`}>{totalErrors}</div>
        </div>
        <div className="phx-stat">
          <div className="phx-stat-label">Usuários ativos</div>
          <div className="phx-stat-value">{totalActiveUsers}</div>
        </div>
      </div>

      {/* Gráficos */}
      <div className="phx-grid">
        <div className="phx-panel">
          <div className="phx-panel-title">
            {toolChartMetric === "time" && "Tempo de execução por ferramenta"}
            {toolChartMetric === "cost" && "Custo estimado por ferramenta"}
            {toolChartMetric === "usage" && "Taxa de uso por ferramenta"}
          </div>
          <div className="phx-panel-desc">
            {toolChartMetric === "time" && "Duração média por chamada, em milissegundos"}
            {toolChartMetric === "cost" &&
              "Custo estimado de tokens consumidos, somado no período (preço por 1.000 tokens configurável no topo do arquivo)"}
            {toolChartMetric === "usage" && "Participação de cada ferramenta no total de execuções do período"}
          </div>
          <div className="phx-metric-toggle">
            <button
              type="button"
              className={`phx-tool-chip${toolChartMetric === "time" ? " active" : ""}`}
              style={toolChartMetric === "time" ? { background: "#4FB3A9" } : undefined}
              onClick={() => setToolChartMetric("time")}
            >
              Tempo
            </button>
            <button
              type="button"
              className={`phx-tool-chip${toolChartMetric === "cost" ? " active" : ""}`}
              style={toolChartMetric === "cost" ? { background: "#E8A33D" } : undefined}
              onClick={() => setToolChartMetric("cost")}
            >
              Custo
            </button>
            <button
              type="button"
              className={`phx-tool-chip${toolChartMetric === "usage" ? " active" : ""}`}
              style={toolChartMetric === "usage" ? { background: "#6C8EEF" } : undefined}
              onClick={() => setToolChartMetric("usage")}
            >
              Taxa de uso
            </button>
          </div>
          {toolChartData.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={toolChartData} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3140" vertical={false} />
                <XAxis
                  dataKey="toolName"
                  tick={{ fill: "#8b94a7", fontSize: 11 }}
                  interval={0}
                  angle={-18}
                  textAnchor="end"
                  height={54}
                />
                <YAxis
                  tick={{ fill: "#8b94a7", fontSize: 11 }}
                  tickFormatter={
                    toolChartMetric === "usage"
                      ? (v: number) => `${v}%`
                      : toolChartMetric === "cost"
                      ? (v: number) => `$${v.toFixed(2)}`
                      : undefined
                  }
                />
                <Tooltip
                  contentStyle={{ background: "#1b212b", border: "1px solid #2a3140", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#e6e9ef" }}
                  formatter={(value: number, _name, item) => {
                    if (toolChartMetric === "time") return [formatDuration(value), "média"];
                    if (toolChartMetric === "cost") return [formatCostUsd(value), "custo estimado"];
                    return [`${value.toFixed(1)}% (${item?.payload?.count ?? 0}x)`, "uso"];
                  }}
                />
                <Bar
                  dataKey={
                    toolChartMetric === "time" ? "avgMs" : toolChartMetric === "cost" ? "costUsd" : "sharePct"
                  }
                  radius={[4, 4, 0, 0]}
                >
                  {toolChartData.map((row) => (
                    <Cell key={row.toolName} fill={colorForTool(row.toolName, allToolNames)} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="phx-empty">Sem execuções no período selecionado.</div>
          )}
        </div>

        <div className="phx-panel">
          <div className="phx-panel-title">Tokens consumidos por ferramenta</div>
          <div className="phx-panel-desc">Entrada (prompt) x saída (completion), somados no período</div>
          {tokensPerTool.length ? (
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={tokensPerTool} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3140" vertical={false} />
                <XAxis
                  dataKey="toolName"
                  tick={{ fill: "#8b94a7", fontSize: 11 }}
                  interval={0}
                  angle={-18}
                  textAnchor="end"
                  height={54}
                />
                <YAxis tick={{ fill: "#8b94a7", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "#1b212b", border: "1px solid #2a3140", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#e6e9ef" }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                <Bar dataKey="input" stackId="tok" fill="#4FB3A9" name="entrada" />
                <Bar dataKey="output" stackId="tok" fill="#E8A33D" name="saída" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="phx-empty">Sem execuções no período selecionado.</div>
          )}
        </div>

        <div className="phx-panel" style={{ gridColumn: "1 / -1" }}>
          <div className="phx-panel-title">Execuções por ferramenta, por turno</div>
          <div className="phx-panel-desc">
            Cada turno agrupa o prompt do usuário e a resposta final do agente.
            {execsPerTurnAll.length > execsPerTurn.length
              ? ` Mostrando os últimos ${execsPerTurn.length} de ${execsPerTurnAll.length} turnos no período.`
              : ""}
          </div>
          {execsPerTurn.length ? (
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={execsPerTurn} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#2a3140" vertical={false} />
                <XAxis dataKey="turnLabel" tick={{ fill: "#8b94a7", fontSize: 11 }} />
                <YAxis tick={{ fill: "#8b94a7", fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  contentStyle={{ background: "#1b212b", border: "1px solid #2a3140", borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: "#e6e9ef" }}
                  labelFormatter={(label, payload) => {
                    const ts = payload?.[0]?.payload?.timestamp;
                    return ts ? `Turno ${label} — ${new Date(ts).toLocaleString("pt-BR")}` : `Turno ${label}`;
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 12 }} />
                {allToolNames.map((tool) => (
                  <Bar
                    key={tool}
                    dataKey={tool}
                    stackId="turn"
                    fill={colorForTool(tool, allToolNames)}
                    name={tool}
                    radius={[2, 2, 0, 0]}
                  />
                ))}
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <div className="phx-empty">Sem turnos no período selecionado.</div>
          )}
        </div>
      </div>

      {/* Usuários ativos por dia */}
      <div className="phx-panel">
        <div className="phx-panel-title">Usuários ativos por dia</div>
        <div className="phx-panel-desc">
          Usuários distintos com pelo menos um turno em cada dia, dentro do período e da faixa de
          horário selecionados nos filtros acima.
        </div>
        {usersPerDay.length ? (
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={usersPerDay} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#2a3140" vertical={false} />
              <XAxis dataKey="dayLabel" tick={{ fill: "#8b94a7", fontSize: 11 }} />
              <YAxis tick={{ fill: "#8b94a7", fontSize: 11 }} allowDecimals={false} />
              <Tooltip
                contentStyle={{ background: "#1b212b", border: "1px solid #2a3140", borderRadius: 8, fontSize: 12 }}
                labelStyle={{ color: "#e6e9ef" }}
                formatter={(value: number) => [value, "usuários ativos"]}
                labelFormatter={(label, payload) => {
                  const day = payload?.[0]?.payload?.day as string | undefined;
                  return day ? new Date(`${day}T00:00:00`).toLocaleDateString("pt-BR") : label;
                }}
              />
              <Bar dataKey="count" fill="#54B8E0" radius={[4, 4, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
        ) : (
          <div className="phx-empty">Sem usuários ativos no período selecionado.</div>
        )}
      </div>

      {/* Padrão por horário (heatmap) */}
      <div className="phx-panel">
        <div className="phx-panel-title">Padrão de uso por horário</div>
        <div className="phx-panel-desc">
          {heatmapMetric === "tokens" && "Tokens consumidos, somados por dia e hora — ajuda a achar picos de gasto."}
          {heatmapMetric === "duration" && "Tempo total gasto em execuções, somado por dia e hora."}
          {heatmapMetric === "turns" && "Número de turnos iniciados, por dia e hora."}
          {" "}Usa o período, a faixa de horário e as ferramentas selecionados nos filtros acima — horas fora da faixa aparecem zeradas.
        </div>
        <div className="phx-metric-toggle">
          {(["tokens", "duration", "turns"] as HeatmapMetric[]).map((m) => (
            <button
              key={m}
              type="button"
              className={`phx-tool-chip${heatmapMetric === m ? " active" : ""}`}
              style={heatmapMetric === m ? { background: `rgb(${METRIC_RGB[m]})` } : undefined}
              onClick={() => setHeatmapMetric(m)}
            >
              {METRIC_LABEL[m]}
            </button>
          ))}
        </div>
        {heatmap.days.length ? (
          <div style={{ overflowX: "auto", paddingBottom: 8 }}>
            <div style={{ display: "grid", gridTemplateColumns: "64px repeat(24, 26px)", gap: 3, minWidth: 700 }}>
              <div />
              {Array.from({ length: 24 }).map((_, h) => (
                <div key={h} style={{ fontSize: 10, color: "#8b94a7", textAlign: "center" }}>{h}</div>
              ))}
              {heatmap.days.map((day) => (
                <React.Fragment key={day}>
                  <div style={{ fontSize: 11, color: "#8b94a7", display: "flex", alignItems: "center" }}>
                    {formatShortDate(day)}
                  </div>
                  {heatmap.matrix.get(day)!.map((v, h) => (
                    <div
                      key={h}
                      title={`${formatShortDate(day)} ${String(h).padStart(2, "0")}h — ${formatMetricValue(v, heatmapMetric)}`}
                      style={{ height: 20, borderRadius: 3, background: heatCellColor(v, heatmap.max, heatmapMetric) }}
                    />
                  ))}
                </React.Fragment>
              ))}
            </div>
          </div>
        ) : (
          <div className="phx-empty">Sem dados no período selecionado.</div>
        )}
      </div>

      {/* Erros */}
      <div className="phx-panel">
        <div className="phx-panel-title">Detalhamento de erros</div>
        <div className="phx-panel-desc">
          {filteredErrorEntries.length} erro(s) no período, horário e ferramentas selecionados nos filtros acima.
        </div>
        <div className="phx-errors-layout">
          <div className="phx-error-list">
            {visibleErrorEntries.length ? (
              visibleErrorEntries.map((e) => {
                const expanded = expandedErrors.has(e.id);
                const message = e.errorMessage ?? "—";
                const isLong = message.length > 110;
                return (
                  <div key={e.id} className="phx-error-card">
                    <div className="phx-error-card-head">
                      <span style={{ color: colorForTool(e.toolName, allToolNames), fontWeight: 600 }}>
                        {e.toolName}
                      </span>
                      <span className="phx-error-badge">{e.errorType ?? "—"}</span>
                    </div>
                    <div className="phx-error-meta phx-mono">
                      chat {e.chatId} · {new Date(e.timestamp).toLocaleString("pt-BR")} · {formatDuration(e.durationMs)}
                    </div>
                    <div className="phx-error-message">
                      {isLong && !expanded ? message.slice(0, 110) + "…" : message}
                    </div>
                    {isLong && (
                      <button type="button" className="phx-link-btn" onClick={() => toggleExpanded(e.id)}>
                        {expanded ? "ver menos" : "ver mensagem completa"}
                      </button>
                    )}
                  </div>
                );
              })
            ) : (
              <div className="phx-empty">
                Nenhum erro no período selecionado{selectedErrorTool ? ` para ${selectedErrorTool}` : ""}.
              </div>
            )}
          </div>

          <div className="phx-error-rank">
            <div className="phx-error-rank-title">Erros por ferramenta</div>
            <button
              type="button"
              className={`phx-rank-item${selectedErrorTool === null ? " active" : ""}`}
              onClick={() => setSelectedErrorTool(null)}
            >
              <span>Todas</span>
              <span>{filteredErrorEntries.length}</span>
            </button>
            {errorsByTool.map((row) => (
              <button
                key={row.toolName}
                type="button"
                className={`phx-rank-item${selectedErrorTool === row.toolName ? " active" : ""}`}
                onClick={() => setSelectedErrorTool(selectedErrorTool === row.toolName ? null : row.toolName)}
              >
                <span style={{ color: colorForTool(row.toolName, allToolNames) }}>{row.toolName}</span>
                <span>{row.count}</span>
              </button>
            ))}
            {!errorsByTool.length && <div className="phx-empty">Sem erros no período selecionado.</div>}
          </div>
        </div>
      </div>
    </div>
  );
}
