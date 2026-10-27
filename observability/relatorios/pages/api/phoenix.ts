import type { NextApiRequest, NextApiResponse } from "next";

type Json = Record<string, unknown>;

const DEFAULT_PAGE_SIZE = 500;
const MAX_PAGE_SIZE = 1000;
const MAX_PAGES = 100;
const REQUEST_TIMEOUT_MS = 15_000;

function isObject(value: unknown): value is Json {
  return !!value && typeof value === "object" && !Array.isArray(value);
}

function value(obj: Json, ...keys: string[]): unknown {
  for (const key of keys) {
    if (obj[key] !== undefined && obj[key] !== null) return obj[key];
  }
  return undefined;
}

/** Converte o formato AnyValue do OpenTelemetry para um valor JavaScript simples. */
function anyValue(valueToNormalize: unknown): unknown {
  if (Array.isArray(valueToNormalize)) return valueToNormalize.map(anyValue);
  if (!isObject(valueToNormalize)) return valueToNormalize;

  for (const key of ["stringValue", "intValue", "doubleValue", "boolValue", "bytesValue"]) {
    if (valueToNormalize[key] !== undefined) return valueToNormalize[key];
  }
  if (valueToNormalize.arrayValue !== undefined) return anyValue(valueToNormalize.arrayValue);
  if (valueToNormalize.kvlistValue !== undefined) return anyValue(valueToNormalize.kvlistValue);
  if (valueToNormalize.values !== undefined) return anyValue(valueToNormalize.values);
  return valueToNormalize;
}

function attrs(span: Json): Json {
  const raw = value(span, "attributes", "span_attributes");
  if (Array.isArray(raw)) {
    return Object.fromEntries(
      raw
        .filter(isObject)
        .map((entry): [string, unknown] => [
          String(value(entry, "key", "name") ?? ""),
          anyValue(value(entry, "value")),
        ])
        .filter(([key]) => key.length > 0)
    );
  }
  if (!isObject(raw)) return {};
  return Object.fromEntries(Object.entries(raw).map(([key, item]) => [key, anyValue(item)]));
}

function context(span: Json): Json {
  const raw = value(span, "context");
  return isObject(raw) ? raw : {};
}

function scalar(raw: unknown): string | undefined {
  const normalized = anyValue(raw);
  if (normalized === undefined || normalized === null) return undefined;
  if (typeof normalized === "string") return normalized;
  if (typeof normalized === "number" || typeof normalized === "boolean") return String(normalized);
  try {
    return JSON.stringify(normalized);
  } catch {
    return undefined;
  }
}

function number(raw: unknown): number {
  const normalized = anyValue(raw);
  const parsed = typeof normalized === "string" && normalized.trim() === "" ? NaN : Number(normalized);
  return Number.isFinite(parsed) ? parsed : 0;
}

function firstAttribute(attributeMap: Json, ...keys: string[]): unknown {
  return value(attributeMap, ...keys);
}

function parseDate(raw: unknown): Date | undefined {
  if (raw === undefined || raw === null || raw === "") return undefined;

  if (typeof raw === "number" || (typeof raw === "string" && /^\d+(\.\d+)?$/.test(raw))) {
    const numeric = Number(raw);
    // Phoenix/OTel installations may serialize timestamps as seconds, ms, us or ns.
    const milliseconds =
      numeric >= 1e17 ? numeric / 1e6 :
      numeric >= 1e14 ? numeric / 1e3 :
      numeric >= 1e11 ? numeric :
      numeric * 1000;
    const date = new Date(milliseconds);
    return Number.isNaN(date.getTime()) ? undefined : date;
  }

  const date = new Date(String(raw));
  return Number.isNaN(date.getTime()) ? undefined : date;
}

function spanTime(span: Json, end = false): string | undefined {
  const raw = value(span, end ? "end_time" : "start_time", end ? "endTime" : "startTime");
  return parseDate(anyValue(raw))?.toISOString();
}

function spanId(span: Json, fallback: string): string {
  const spanContext = context(span);
  return String(value(span, "span_id", "spanId", "id") || spanContext.span_id || spanContext.spanId || fallback);
}

function traceId(span: Json, fallback: string): string {
  const spanContext = context(span);
  return String(value(span, "trace_id", "traceId") || spanContext.trace_id || spanContext.traceId || fallback);
}

function parentId(span: Json): string | undefined {
  return scalar(value(span, "parent_id", "parentId"));
}

function spanKind(span: Json, attributeMap = attrs(span)): string {
  return String(
    value(span, "span_kind", "spanKind") ||
    firstAttribute(attributeMap, "openinference.span.kind", "span.kind") ||
    ""
  ).toUpperCase();
}

function errorDetails(span: Json, attributeMap: Json): { type?: string; message?: string } {
  const events = Array.isArray(span.events) ? span.events.filter(isObject) : [];
  const exception = events.find((event) => String(event.name || "").toLowerCase() === "exception");
  const exceptionAttrs = exception && isObject(exception.attributes) ? exception.attributes : {};
  const type = scalar(firstAttribute(
    attributeMap,
    "error.type",
    "exception.type",
    "error_type",
    "errorType",
    "status_message"
  ) || value(span, "error_type", "errorType", "status_message"));
  const rawMessage = scalar(firstAttribute(
    attributeMap,
    "error.message",
    "exception.message",
    "error_message",
    "errorMessage"
  ) || value(span, "error_message", "errorMessage")) || scalar(firstAttribute(exceptionAttrs, "exception.message", "message"));
  return { type, message: rawMessage?.slice(0, 2000) };
}

function tokenCounts(span: Json, attributeMap: Json): { input: number; output: number; cacheRead: number; hasUsage: boolean } {
  const input = number(value(span, "token_count_prompt", "prompt_token_count") || firstAttribute(
    attributeMap,
    "llm.token_count.prompt",
    "llm.token_count.input"
  ));
  const output = number(value(span, "token_count_completion", "completion_token_count") || firstAttribute(
    attributeMap,
    "llm.token_count.completion",
    "llm.token_count.output"
  ));
  const cacheRead = number(firstAttribute(
    attributeMap,
    "llm.token_count.prompt_details.cache_read",
    "llm.token_count.cache_read",
    "llm.token_count.cache_read_input"
  ));
  return { input, output, cacheRead, hasUsage: input > 0 || output > 0 || cacheRead > 0 };
}

function modelName(attributeMap: Json): string | undefined {
  return scalar(firstAttribute(attributeMap, "llm.model_name", "llm.request.model", "gen_ai.request.model"));
}

function extractRows(payload: unknown): Json[] {
  if (Array.isArray(payload)) return payload.filter(isObject);
  if (!isObject(payload)) return [];
  const rows = payload.data ?? payload.spans ?? payload.items;
  return Array.isArray(rows) ? rows.filter(isObject) : [];
}

function extractNextCursor(payload: unknown): string | undefined {
  if (!isObject(payload)) return undefined;
  const pagination = isObject(payload.pagination) ? payload.pagination : {};
  return scalar(
    value(payload, "next_cursor", "nextCursor") ||
    value(pagination, "next_cursor", "nextCursor")
  );
}

function toTurns(payload: unknown) {
  const spans = extractRows(payload)
    .map((span, index) => ({ span, index, startTime: spanTime(span) }))
    .filter((item): item is { span: Json; index: number; startTime: string } => !!item.startTime);

  const groups = new Map<string, Json[]>();
  spans.forEach(({ span, index }) => {
    const id = spanId(span, `orphan-${index}`);
    const trace = traceId(span, `orphan:${id}`);
    groups.set(trace, [...(groups.get(trace) || []), span]);
  });

  return [...groups.entries()]
    .map(([trace, group]) => {
      const root = [...group]
        .sort((a, b) => (parseDate(spanTime(a))?.getTime() || Number.MAX_SAFE_INTEGER) - (parseDate(spanTime(b))?.getTime() || Number.MAX_SAFE_INTEGER))
        .find((span) => !parentId(span)) || group[0];
      const rootAttrs = attrs(root);
      const rootStart = spanTime(root);
      if (!rootStart) return null;

      const executions = group.flatMap((span, index) => {
        const attributeMap = attrs(span);
        if (spanKind(span, attributeMap) !== "TOOL") return [];
        const start = spanTime(span);
        if (!start) return [];
        const end = spanTime(span, true) || start;
        const error = errorDetails(span, attributeMap);
        const status = String(value(span, "status_code", "statusCode") || "").toUpperCase();
        const usage = tokenCounts(span, attributeMap);
        return [{
          id: spanId(span, `${trace}-tool-${index}`),
          toolName: scalar(value(span, "name") || firstAttribute(attributeMap, "tool.name", "openinference.tool.name")) || "tool",
          turnId: trace,
          startTime: start,
          endTime: end,
          durationMs: Math.max(0, new Date(end).getTime() - new Date(start).getTime()),
          tokensInput: usage.input,
          tokensOutput: usage.output,
          status: status.includes("ERROR") || !!error.message ? "error" as const : "success" as const,
          errorType: error.type,
          errorMessage: error.message,
        }];
      });

      const llmUsages = group.flatMap((span, index) => {
        const attributeMap = attrs(span);
        const usage = tokenCounts(span, attributeMap);
        if (spanKind(span, attributeMap) !== "LLM" && !usage.hasUsage) return [];
        const start = spanTime(span);
        if (!start) return [];
        const end = spanTime(span, true) || start;
        const error = errorDetails(span, attributeMap);
        const status = String(value(span, "status_code", "statusCode") || "").toUpperCase();
        return [{
          id: spanId(span, `${trace}-llm-${index}`),
          turnId: trace,
          modelName: modelName(attributeMap),
          startTime: start,
          endTime: end,
          durationMs: Math.max(0, new Date(end).getTime() - new Date(start).getTime()),
          tokensInput: usage.input,
          tokensOutput: usage.output,
          tokensCacheRead: usage.cacheRead,
          status: status.includes("ERROR") || !!error.message ? "error" as const : "success" as const,
          errorType: error.type,
          errorMessage: error.message,
        }];
      });

      return {
        id: trace,
        chatId: scalar(firstAttribute(rootAttrs, "session.id", "session_id")) || trace,
        userId: scalar(firstAttribute(rootAttrs, "user.id", "user_id")),
        timestamp: rootStart,
        executions,
        llmUsages,
      };
    })
    .filter((turn): turn is NonNullable<typeof turn> => turn !== null);
}

function integerEnv(name: string, fallback: number, max: number): number {
  const parsed = Number.parseInt(process.env[name] || "", 10);
  return Number.isFinite(parsed) && parsed > 0 ? Math.min(parsed, max) : fallback;
}

async function fetchAllSpans(base: string, project: string, headers: Record<string, string>) {
  const pageSize = integerEnv("PHOENIX_SPANS_LIMIT", DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE);
  const maxPages = integerEnv("PHOENIX_SPANS_MAX_PAGES", MAX_PAGES, MAX_PAGES);
  const rows: Json[] = [];
  const seenCursors = new Set<string>();
  let cursor: string | undefined;
  let truncated = false;

  for (let page = 0; page < maxPages; page += 1) {
    const url = new URL(`${base.replace(/\/$/, "")}/v1/projects/${project}/spans`);
    url.searchParams.set("limit", String(pageSize));
    if (cursor) url.searchParams.set("cursor", cursor);

    const response = await fetch(url, { headers, signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS) });
    if (!response.ok) throw new Error(`Phoenix respondeu HTTP ${response.status}`);

    const body = await response.json();
    const pageRows = extractRows(body);
    rows.push(...pageRows);
    const nextCursor = extractNextCursor(body);
    if (!nextCursor || seenCursors.has(nextCursor)) {
      truncated = !nextCursor && pageRows.length >= pageSize;
      break;
    }
    seenCursors.add(nextCursor);
    cursor = nextCursor;
  }

  if (cursor && seenCursors.size >= maxPages) truncated = true;
  const uniqueRows = [...new Map(rows.map((row, index) => [spanId(row, `row-${index}`), row])).values()];
  return { rows: uniqueRows, truncated };
}

export default async function handler(req: NextApiRequest, res: NextApiResponse) {
  if (req.method !== "GET") return res.status(405).json({ error: "Método não permitido" });

  const base = process.env.PHOENIX_URL || "http://phoenix:6006";
  const project = encodeURIComponent(process.env.PHOENIX_PROJECT_NAME || "EurecaChat");

  try {
    const headers: Record<string, string> = { accept: "application/json" };
    if (process.env.PHOENIX_API_KEY && process.env.PHOENIX_API_KEY !== "API_KEY") {
      headers.authorization = `Bearer ${process.env.PHOENIX_API_KEY}`;
    }

    if (!headers.authorization && process.env.PHOENIX_USER && process.env.PHOENIX_PASSWORD) {
      const login = await fetch(`${base.replace(/\/$/, "")}/auth/login`, {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ email: process.env.PHOENIX_USER, password: process.env.PHOENIX_PASSWORD }),
        signal: AbortSignal.timeout(REQUEST_TIMEOUT_MS),
      });
      const getSetCookie = (login.headers as Headers & { getSetCookie?: () => string[] }).getSetCookie;
      const setCookies = typeof getSetCookie === "function"
        ? getSetCookie.call(login.headers)
        : [login.headers.get("set-cookie") || ""];
      const cookie = setCookies
        .map((entry) => entry.split(";", 1)[0])
        .filter(Boolean)
        .join("; ");
      if (!login.ok || !cookie) return res.status(401).json({ error: "Falha na autenticação com o Phoenix" });
      headers.cookie = cookie;
    }

    const result = await fetchAllSpans(base, project, headers);
    return res.status(200).json({
      turns: toTurns(result.rows),
      source: "phoenix",
      spanCount: result.rows.length,
      truncated: result.truncated,
    });
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    return res.status(502).json({ error: `Não foi possível consultar o Phoenix: ${detail}` });
  }
}
