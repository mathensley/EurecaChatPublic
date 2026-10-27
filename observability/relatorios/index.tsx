"use client";

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { getApps, initializeApp } from "firebase/app";
import { collection, getDocs, getFirestore } from "firebase/firestore";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

const firebaseConfig = {
  apiKey: "AIzaSyA4CPjvm2JVzuQIgPDia7ydtRuoaxbjD5M",
  authDomain: "eurecachat.firebaseapp.com",
  projectId: "eurecachat",
  storageBucket: "eurecachat.firebasestorage.app",
  messagingSenderId: "707952127854",
  appId: "1:707952127854:web:18058307ee7bf414751b7f",
  measurementId: "G-V404VGE2E0",
};

const firebaseApp =
  getApps()[0] ?? initializeApp(firebaseConfig);
const firestore = getFirestore(firebaseApp);
const FEEDBACKS_COLLECTION = "feedbacks_eureca";
const THEME_STORAGE_KEY = "eureca_relatorios_theme";
const THEME_BOOTSTRAP_SCRIPT = `(function(){try{var t=localStorage.getItem("${THEME_STORAGE_KEY}");if(t==="light"||t==="dark")document.documentElement.dataset.eurecaTheme=t}catch(e){}})();`;

/* =================================================================
   Tipos
   ================================================================= */

export interface FirestoreTimestamp {
  seconds?: number;
  _seconds?: number;
  toDate?: () => Date;
}

export interface RawFeedback {
  _doc_id?: string;
  id?: string;
  avaliacao?: string | null;
  conversa_id?: string | null;
  usuario_id?: string | null;
  tipo_usuario?: string | null;
  pergunta?: string | null;
  resposta?: string | null;
  feedback?: string | null;
  data_hora_local?: string | null;
  createdAt?: string | number | FirestoreTimestamp | null;
}

interface RawFeedbackDocument extends RawFeedback {
  feedback_list?: unknown;
}

/** Documento já normalizado para uso interno do relatório. */
export interface FeedbackRecord {
  id: string;
  positive: boolean;
  conversaId: string | null;
  usuarioId: string | null;
  tipoUsuario: string;
  pergunta: string;
  resposta: string;
  comentario: string;
  dateKey: string;
  dateLabel: string;
  timeLabel: string;
  sortTime: number;
}

export interface DayBucket {
  dateKey: string;
  dateLabel: string;
  positivo: number;
  negativo: number;
  items: FeedbackRecord[];
}

export interface Session {
  key: string;
  conversaId: string | null;
  items: FeedbackRecord[];
}

export type PresetValue = "7" | "30" | "90" | "all";
export type Theme = "light" | "dark";
type BarMode = "filled" | "scale";

interface Range {
  start: string;
  end: string;
}

interface Source {
  raw: RawFeedback[];
}

interface LoginCredentials {
  login: string;
  senha: string;
}

export interface FeedbacksEurecaProps {
  /** Documentos crus. Quando informado, substitui os dados do Firestore. */
  data?: RawFeedback[] | null;
  /** Mantido por compatibilidade com quem já usa o componente. */
  theme?: Theme;
  /** Guarda o JSON carregado no navegador entre sessões. */
  persist?: boolean;
  /** Chave usada no localStorage. */
  storageKey?: string;
}

/* =================================================================
   Utilitários puros (sem React)
   ================================================================= */

const pad2 = (n: number | string): string => String(n).padStart(2, "0");

function isPositive(rec: RawFeedback): boolean {
  const v = String(rec.avaliacao || rec.feedback || "").toLowerCase();
  if (
    v.includes("neg") ||
    v.includes("não") ||
    v.includes("nao") ||
    v.includes("ruim")
  )
    return false;
  if (v.includes("pos") || v.includes("gostei") || v.includes("bom")) return true;
  // valor desconhecido cai no bucket "não gostei" para não inflar o positivo
  return false;
}

function firestoreDateToJs(
  val: RawFeedback["createdAt"]
): Date | null {
  if (!val) return null;
  if (typeof val === "string") {
    const d = new Date(val);
    return Number.isNaN(d.getTime()) ? null : d;
  }
  if (typeof val === "number") return new Date(val);
  if (typeof val === "object") {
    if (typeof val.toDate === "function") {
      const d = val.toDate();
      return Number.isNaN(d.getTime()) ? null : d;
    }
    if (typeof val._seconds === "number") return new Date(val._seconds * 1000);
    if (typeof val.seconds === "number") return new Date(val.seconds * 1000);
  }
  return null;
}

/** Normaliza um documento cru do Firestore para o formato interno do relatório. */
function normalizeRecord(raw: RawFeedback, idx: number): FeedbackRecord {
  let dateKey: string | null = null;
  let dateLabel: string | null = null;
  let timeLabel = "";
  let sortTime = 0;

  if (
    raw.data_hora_local &&
    typeof raw.data_hora_local === "string" &&
    raw.data_hora_local.includes("/")
  ) {
    const parts = raw.data_hora_local.split(",");
    const datePart = parts[0].trim();
    const timePart = (parts[1] || "").trim();
    const dmy = datePart.split("/");
    if (dmy.length === 3) {
      const [d, m, y] = dmy.map((s) => s.trim());
      dateKey = `${y}-${pad2(m)}-${pad2(d)}`;
      dateLabel = `${pad2(d)}/${pad2(m)}/${y}`;
      timeLabel = timePart.slice(0, 5);
      const dt = new Date(`${y}-${pad2(m)}-${pad2(d)}T${timePart || "00:00:00"}`);
      sortTime = Number.isNaN(dt.getTime()) ? idx : dt.getTime();
    }
  }

  if (!dateKey) {
    const jsDate = firestoreDateToJs(raw.createdAt);
    if (jsDate) {
      dateKey = `${jsDate.getFullYear()}-${pad2(jsDate.getMonth() + 1)}-${pad2(
        jsDate.getDate()
      )}`;
      dateLabel = `${pad2(jsDate.getDate())}/${pad2(
        jsDate.getMonth() + 1
      )}/${jsDate.getFullYear()}`;
      timeLabel = `${pad2(jsDate.getHours())}:${pad2(jsDate.getMinutes())}`;
      sortTime = jsDate.getTime();
    }
  }

  if (!dateKey) {
    dateKey = "sem-data";
    dateLabel = "Sem data";
    sortTime = idx;
  }

  return {
    id: raw._doc_id || raw.id || `rec-${idx}`,
    positive: isPositive(raw),
    conversaId: raw.conversa_id || null,
    usuarioId: raw.usuario_id || null,
    tipoUsuario: raw.tipo_usuario || "anon",
    pergunta: raw.pergunta || "",
    resposta: raw.resposta || "",
    comentario: raw.feedback || "",
    dateKey,
    dateLabel: dateLabel ?? dateKey,
    timeLabel,
    sortTime,
  };
}

function computeDaily(records: FeedbackRecord[]): Map<string, DayBucket> {
  const map = new Map<string, DayBucket>();
  records.forEach((r) => {
    let day = map.get(r.dateKey);
    if (!day) {
      day = {
        dateKey: r.dateKey,
        dateLabel: r.dateLabel,
        positivo: 0,
        negativo: 0,
        items: [],
      };
      map.set(r.dateKey, day);
    }
    if (r.positive) day.positivo++;
    else day.negativo++;
    day.items.push(r);
  });
  map.forEach((day) => day.items.sort((a, b) => b.sortTime - a.sortTime));
  return map;
}

const keysSorted = (map: Map<string, DayBucket>): string[] =>
  Array.from(map.keys())
    .filter((k) => k !== "sem-data")
    .sort();

function shiftKey(key: string, days: number): string {
  const [y, m, d] = key.split("-").map(Number);
  const dt = new Date(y, m - 1, d);
  dt.setDate(dt.getDate() + days);
  return `${dt.getFullYear()}-${pad2(dt.getMonth() + 1)}-${pad2(dt.getDate())}`;
}

function keyToLabel(key: string): string {
  if (key === "sem-data") return "Sem data";
  const p = key.split("-");
  if (p.length !== 3 || p.some((part) => !part)) return "Sem data";
  return `${p[2]}/${p[1]}/${p[0]}`;
}

function keyToShortLabel(key: string): string {
  if (key === "sem-data") return "Sem data";
  const p = key.split("-");
  if (p.length !== 3 || p.some((part) => !part)) return "Sem data";
  return `${p[2]}/${p[1]}`;
}

function iterateKeys(startKey: string, endKey: string): string[] {
  const out: string[] = [];
  let k = startKey;
  let guard = 0;
  while (k <= endKey && guard < 4000) {
    out.push(k);
    k = shiftKey(k, 1);
    guard++;
  }
  return out;
}

function daysBetween(a: string, b: string): number {
  const pa = a.split("-").map(Number);
  const pb = b.split("-").map(Number);
  const da = new Date(pa[0], pa[1] - 1, pa[2]).getTime();
  const db = new Date(pb[0], pb[1] - 1, pb[2]).getTime();
  return Math.round((db - da) / 86400000);
}

/** Agrupa os feedbacks de um dia em conversas (ou avaliações avulsas). */
function sessionsForDay(day: DayBucket): Session[] {
  const groups = new Map<string, Session>();
  day.items.forEach((item) => {
    const key = item.conversaId ? `conv-${item.conversaId}` : `solo-${item.id}`;
    let group = groups.get(key);
    if (!group) {
      group = { key, conversaId: item.conversaId, items: [] };
      groups.set(key, group);
    }
    group.items.push(item);
  });
  const sessions = Array.from(groups.values());
  sessions.forEach((s) => s.items.sort((a, b) => a.sortTime - b.sortTime));
  sessions.sort(
    (a, b) =>
      b.items[b.items.length - 1].sortTime - a.items[a.items.length - 1].sortTime
  );
  return sessions;
}

async function loadFirestoreFeedbacks(): Promise<RawFeedback[]> {
  const snapshot = await getDocs(collection(firestore, FEEDBACKS_COLLECTION));
  const records: RawFeedback[] = [];

  snapshot.docs.forEach((item) => {
    const document = item.data() as RawFeedbackDocument;
    if (Array.isArray(document.feedback_list)) {
      document.feedback_list.forEach((entry, index) => {
        if (!entry || typeof entry !== "object") return;
        records.push({
          ...(entry as RawFeedback),
          _doc_id: `${item.id}-${index}`,
        });
      });
      return;
    }

    records.push({
      _doc_id: item.id,
      ...(document as Omit<RawFeedbackDocument, "_doc_id">),
    });
  });

  return records;
}

/* =================================================================
   Componente principal
   ================================================================= */

const PRESETS: ReadonlyArray<{ value: PresetValue; label: string }> = [
  { value: "7", label: "7 dias" },
  { value: "30", label: "30 dias" },
  { value: "90", label: "90 dias" },
  { value: "all", label: "Tudo" },
];

export default function FeedbacksEureca({
  data = null,
  theme,
  persist = true,
  storageKey = "eureca_feedbacks_raw_v1",
}: FeedbacksEurecaProps) {
  const detailRef = useRef<HTMLDivElement>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [authLoading, setAuthLoading] = useState(true);
  const [credentials, setCredentials] = useState<LoginCredentials | null>(null);
  const [authLogin, setAuthLogin] = useState("");
  const [authPassword, setAuthPassword] = useState("");
  const [authError, setAuthError] = useState("");
  const [currentTheme, setCurrentTheme] = useState<Theme>(theme || "light");
  const [themeReady, setThemeReady] = useState(Boolean(theme));

  useEffect(() => {
    let cancelled = false;

    async function loadLogin(): Promise<void> {
      try {
        const response = await fetch("/login.json", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const parsed: unknown = await response.json();
        if (
          !parsed ||
          typeof parsed !== "object" ||
          typeof (parsed as LoginCredentials).login !== "string" ||
          typeof (parsed as LoginCredentials).senha !== "string"
        ) {
          throw new Error("formato inválido no login.json");
        }

        if (cancelled) return;
        setCredentials(parsed as LoginCredentials);
        try {
          setAuthenticated(
            window.sessionStorage.getItem("eureca_relatorios_auth") === "1"
          );
        } catch {
          /* sessão indisponível: o login será solicitado normalmente */
        }
      } catch (err) {
        if (!cancelled) {
          const detail = err instanceof Error ? err.message : String(err);
          setAuthError(`Não foi possível carregar as credenciais. (${detail})`);
        }
      } finally {
        if (!cancelled) setAuthLoading(false);
      }
    }

    loadLogin();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (theme) {
      setCurrentTheme(theme);
      setThemeReady(true);
      return;
    }

    try {
      const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
      if (saved === "light" || saved === "dark") setCurrentTheme(saved);
    } catch {
      /* preferência indisponível: usa claro */
    } finally {
      setThemeReady(true);
    }
  }, [theme]);

  useEffect(() => {
    if (!themeReady || theme) return;
    try {
      window.localStorage.setItem(THEME_STORAGE_KEY, currentTheme);
    } catch {
      /* ignora modo privado ou armazenamento indisponível */
    }
  }, [currentTheme, theme, themeReady]);

  useEffect(() => {
    if (currentTheme === "dark") {
      document.documentElement.dataset.eurecaTheme = "dark";
    } else {
      delete document.documentElement.dataset.eurecaTheme;
    }
  }, [currentTheme]);

  const loadLocal = useCallback((): RawFeedback[] | null => {
    if (!persist) return null;
    try {
      const v = window.localStorage.getItem(storageKey);
      return v ? (JSON.parse(v) as RawFeedback[]) : null;
    } catch {
      return null;
    }
  }, [persist, storageKey]);

  const saveLocal = useCallback(
    (rawArray: RawFeedback[]): void => {
      if (!persist) return;
      try {
        window.localStorage.setItem(storageKey, JSON.stringify(rawArray));
      } catch {
        /* silencioso: quota ou modo privado */
      }
    },
    [persist, storageKey]
  );

  const [source, setSource] = useState<Source>(() => {
    if (Array.isArray(data)) return { raw: data };
    const saved = loadLocal();
    if (Array.isArray(saved)) return { raw: saved };
    return { raw: [] };
  });

  const [preset, setPreset] = useState<PresetValue | null>(null); // null = automático
  const [customRange, setCustomRange] = useState<Range | null>(null);
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const [openSession, setOpenSession] = useState<string | null>(null);
  const [barMode, setBarMode] = useState<BarMode>("filled");
  const [erro, setErro] = useState("");
  const [firebaseLoading, setFirebaseLoading] = useState(
    () => !Array.isArray(data)
  );

  // Dados vindos por prop têm prioridade
  useEffect(() => {
    if (Array.isArray(data)) {
      setSource({ raw: data });
      setFirebaseLoading(false);
      setPreset(null);
      setCustomRange(null);
      setSelectedDay(null);
      setOpenSession(null);
    }
  }, [data]);

  useEffect(() => {
    if (!authenticated || Array.isArray(data)) return;

    let cancelled = false;
    setFirebaseLoading(true);

    loadFirestoreFeedbacks()
      .then((raw) => {
        if (cancelled) return;
        setErro("");
        setSelectedDay(null);
        setOpenSession(null);
        setPreset(null);
        setCustomRange(null);
        setSource({ raw });
        saveLocal(raw);
      })
      .catch((err) => {
        if (cancelled) return;
        const detail = err instanceof Error ? err.message : String(err);
        setErro(
          `Não foi possível carregar os feedbacks do Firestore. (${detail})`
        );
      })
      .finally(() => {
        if (!cancelled) setFirebaseLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [authenticated, data, saveLocal]);

  /* ---------- derivações ---------- */

  const records = useMemo(() => source.raw.map(normalizeRecord), [source]);
  const daily = useMemo(() => computeDaily(records), [records]);

  const { minKey, maxKey } = useMemo(() => {
    const keys = keysSorted(daily);
    return {
      minKey: keys.length ? keys[0] : null,
      maxKey: keys.length ? keys[keys.length - 1] : null,
    };
  }, [daily]);

  const autoPreset: PresetValue =
    minKey && maxKey && daysBetween(minKey, maxKey) <= 30 ? "all" : "30";
  const activePreset: PresetValue | null = customRange ? null : preset ?? autoPreset;

  const range = useMemo<Range | null>(() => {
    if (customRange) return customRange;
    if (!minKey || !maxKey) return null;
    if (activePreset === "all") return { start: minKey, end: maxKey };
    let start = shiftKey(maxKey, -(parseInt(activePreset as string, 10) - 1));
    if (start < minKey) start = minKey;
    return { start, end: maxKey };
  }, [customRange, activePreset, minKey, maxKey]);

  const chartKeys = useMemo(
    () => (range ? iterateKeys(range.start, range.end) : []),
    [range]
  );

  const chartStats = useMemo(() => {
    let maxTotal = 1;
    let sumTotal = 0;
    let sumPos = 0;
    chartKeys.forEach((k) => {
      const d = daily.get(k);
      const t = d ? d.positivo + d.negativo : 0;
      if (t > maxTotal) maxTotal = t;
      sumTotal += t;
      sumPos += d ? d.positivo : 0;
    });
    return {
      maxTotal,
      sumTotal,
      pct: sumTotal ? Math.round((sumPos / sumTotal) * 100) : 0,
      showLabelEvery: chartKeys.length > 45 ? 7 : chartKeys.length > 20 ? 3 : 1,
    };
  }, [chartKeys, daily]);

  const summary = useMemo(() => {
    const total = records.length;
    const pos = records.filter((r) => r.positive).length;
    const pct = total ? Math.round((pos / total) * 100) : 0;
    const periodo =
      minKey && maxKey ? `${keyToLabel(minKey)} – ${keyToLabel(maxKey)}` : "—";
    let peak: { key: string | null; total: number } = { key: null, total: -1 };
    daily.forEach((d, k) => {
      const t = d.positivo + d.negativo;
      if (t > peak.total) peak = { key: k, total: t };
    });
    return [
      { v: String(total), l: "Feedbacks no total" },
      { v: `${pct}%`, l: "Avaliações positivas" },
      { v: periodo, l: "Período coberto" },
      {
        v: peak.key ? `${keyToShortLabel(peak.key)} · ${peak.total}` : "—",
        l: "Dia com mais feedbacks",
      },
    ];
  }, [records, daily, minKey, maxKey]);

  const selected: DayBucket | null = selectedDay
    ? daily.get(selectedDay) ?? {
        dateKey: selectedDay,
        dateLabel: keyToLabel(selectedDay),
        positivo: 0,
        negativo: 0,
        items: [],
      }
    : null;

  /* ---------- ações ---------- */

  useEffect(() => {
    if (selectedDay && detailRef.current) {
      detailRef.current.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  }, [selectedDay]);

  function selectDay(key: string): void {
    setSelectedDay(key);
    setOpenSession(null);
  }

  function handlePreset(value: PresetValue): void {
    setPreset(value);
    setCustomRange(null);
  }

  function handleDateChange(which: "start" | "end", value: string): void {
    if (!range || !value) return;
    let s = which === "start" ? value : range.start;
    let e = which === "end" ? value : range.end;
    if (s > e) [s, e] = [e, s];
    setCustomRange({ start: s, end: e });
  }

  async function handleClear(): Promise<void> {
    if (persist) {
      try {
        window.localStorage.removeItem(storageKey);
      } catch {
        /* ignora */
      }
    }
    setErro("");
    setSelectedDay(null);
    setOpenSession(null);
    setPreset(null);
    setCustomRange(null);
    if (Array.isArray(data)) {
      setSource({ raw: data });
      return;
    }

    setFirebaseLoading(true);
    try {
      const raw = await loadFirestoreFeedbacks();
      setSource({ raw });
      saveLocal(raw);
    } catch (err) {
      const detail = err instanceof Error ? err.message : String(err);
      setSource({ raw: [] });
      setErro(`Não foi possível carregar os feedbacks do Firestore. (${detail})`);
    } finally {
      setFirebaseLoading(false);
    }
  }

  function handleLoginSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!credentials) {
      setAuthError("As credenciais ainda não estão disponíveis.");
      return;
    }

    if (authLogin === credentials.login && authPassword === credentials.senha) {
      setAuthError("");
      setAuthenticated(true);
      try {
        window.sessionStorage.setItem("eureca_relatorios_auth", "1");
      } catch {
        /* sessão indisponível: o acesso continua válido nesta aba */
      }
      return;
    }

    setAuthError("Login ou senha inválidos.");
  }

  function handleLogout(): void {
    setAuthenticated(false);
    setAuthLogin("");
    setAuthPassword("");
    try {
      window.sessionStorage.removeItem("eureca_relatorios_auth");
    } catch {
      /* ignora */
    }
  }

  /* ---------- render ---------- */

  if (authLoading) {
    return (
      <div className="eureca-report" data-theme={currentTheme}>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
        <style>{CSS}</style>
        <main className="login-shell">
          <div className="login-loading">Carregando…</div>
        </main>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="eureca-report" data-theme={currentTheme}>
        <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
        <style>{CSS}</style>
        <LoginCard
          login={authLogin}
          password={authPassword}
          error={authError}
          loading={authLoading}
          onLoginChange={setAuthLogin}
          onPasswordChange={setAuthPassword}
          onSubmit={handleLoginSubmit}
          theme={currentTheme}
          onToggleTheme={() =>
            setCurrentTheme((value) => (value === "light" ? "dark" : "light"))
          }
        />
      </div>
    );
  }

  return (
    <div className="eureca-report" data-theme={currentTheme}>
      <script dangerouslySetInnerHTML={{ __html: THEME_BOOTSTRAP_SCRIPT }} />
      <style>{CSS}</style>

      <div className="shell">
        <div className="header">
          <div>
            <h1>Feedbacks do Eureca Chat</h1>
            <p>
              Avaliações de respostas do chatbot — volume por dia, e as perguntas e
              respostas por trás de cada avaliação.
            </p>
          </div>
          <div className="toolbar">
            <button
              className="btn"
              type="button"
              onClick={() =>
                setCurrentTheme((value) => (value === "light" ? "dark" : "light"))
              }
            >
              {currentTheme === "light" ? "☾ Modo escuro" : "☀ Modo claro"}
            </button>
            <a className="btn" href="/observabilidade">
              Observabilidade
            </a>
            <button
              className="btn btn-danger-ghost"
              type="button"
              onClick={handleClear}
              disabled={firebaseLoading}
            >
              {firebaseLoading ? "Carregando…" : "Recarregar"}
            </button>
            <button className="btn" type="button" onClick={handleLogout}>
              Sair
            </button>
          </div>
        </div>

        {erro && (
          <div className="banner banner-error" role="alert">
            <span>{erro}</span>
          </div>
        )}

        {firebaseLoading && (
          <div className="banner">
            <span>Carregando dados salvos…</span>
          </div>
        )}


        <div className="summary">
          {summary.map((c) => (
            <div className="summary-card" key={c.l}>
              <div className="summary-value">{c.v}</div>
              <div className="summary-label">{c.l}</div>
            </div>
          ))}
        </div>

        <div className="range-row">
          <div className="presets">
            {PRESETS.map((p) => (
              <button
                key={p.value}
                type="button"
                className={`preset-btn${activePreset === p.value ? " active" : ""}`}
                onClick={() => handlePreset(p.value)}
              >
                {p.label}
              </button>
            ))}
          </div>
          <div className="dates">
            De{" "}
            <input
              type="date"
              value={range?.start ?? ""}
              min={minKey ?? undefined}
              max={maxKey ?? undefined}
              onChange={(e) => handleDateChange("start", e.target.value)}
            />{" "}
            até{" "}
            <input
              type="date"
              value={range?.end ?? ""}
              min={minKey ?? undefined}
              max={maxKey ?? undefined}
              onChange={(e) => handleDateChange("end", e.target.value)}
            />
          </div>
        </div>

        <div className="chart-card">
          <div className="chart-head">
            <div className="chart-title">Gostei × Não gostei por dia</div>
            <div className="chart-actions">
              <div className="chart-caption">
                {range
                  ? `${chartStats.sumTotal} feedbacks no intervalo · ${chartStats.pct}% positivos`
                  : ""}
              </div>
              <button
                className="chart-mode-btn"
                type="button"
                onClick={() =>
                  setBarMode((mode) => (mode === "filled" ? "scale" : "filled"))
                }
                title="Alternar a escala das barras"
              >
                {barMode === "filled" ? "Barras cheias" : "Escala real"}
              </button>
            </div>
          </div>
          <div className="legend">
            <span className="legend-item">
              <span className="dot blue" /> Gostei
            </span>
            <span className="legend-item">
              <span className="dot red" /> Não gostei
            </span>
          </div>
          <div className="hint">
            Clique em uma barra para ver as perguntas e respostas daquele dia.
          </div>
          <div className="chart-scroll">
            <div className="chart">
              {!range ? (
                <div className="empty-chart">Carregue dados para ver o gráfico.</div>
              ) : (
                chartKeys.map((k, i) => {
                  const d = daily.get(k);
                  const positivo = d ? d.positivo : 0;
                  const negativo = d ? d.negativo : 0;
                  const total = positivo + negativo;
                  const barHeight =
                    barMode === "filled" || !total
                      ? total ? 150 : 0
                      : (total / chartStats.maxTotal) * 150;
                  const hPos = total ? (positivo / total) * barHeight : 0;
                  const hNeg = total ? (negativo / total) * barHeight : 0;
                  const label =
                    i % chartStats.showLabelEvery === 0 ? keyToShortLabel(k) : "";
                  return (
                    <div
                      key={k}
                      className={`col${selectedDay === k ? " selected" : ""}`}
                      title={`${keyToLabel(k)} — ${positivo} gostei, ${negativo} não gostei`}
                      onClick={() => selectDay(k)}
                    >
                      <div className="bar-wrap">
                        {hNeg > 0 && (
                          <div className="seg red" style={{ height: `${hNeg}px` }} />
                        )}
                        {hPos > 0 && (
                          <div className="seg blue" style={{ height: `${hPos}px` }} />
                        )}
                      </div>
                      <div className="col-label">{label}</div>
                    </div>
                  );
                })
              )}
            </div>
          </div>
        </div>

        {selected && (
          <div className="detail open" ref={detailRef}>
            <div className="detail-head">
              <div className="detail-title">Feedbacks de {selected.dateLabel}</div>
              <button
                className="detail-close"
                type="button"
                onClick={() => setSelectedDay(null)}
              >
                fechar ✕
              </button>
            </div>
            <DayBody
              day={selected}
              openSession={openSession}
              onToggleSession={(key) =>
                setOpenSession((cur) => (cur === key ? null : key))
              }
            />
          </div>
        )}

      </div>
    </div>
  );
}

/* =================================================================
   Login
   ================================================================= */

interface LoginCardProps {
  login: string;
  password: string;
  error: string;
  loading: boolean;
  onLoginChange: (value: string) => void;
  onPasswordChange: (value: string) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
  theme: Theme;
  onToggleTheme: () => void;
}

function LoginCard({
  login,
  password,
  error,
  loading,
  onLoginChange,
  onPasswordChange,
  onSubmit,
  theme,
  onToggleTheme,
}: LoginCardProps) {
  return (
    <main className="login-shell">
      <form className="login-card" onSubmit={onSubmit}>
        <div className="login-topbar">
          <span>Área restrita</span>
          <button className="login-theme" type="button" onClick={onToggleTheme}>
            {theme === "light" ? "☾ Escuro" : "☀ Claro"}
          </button>
        </div>
        <div className="login-mark">E</div>
        <h1>Acesso aos relatórios</h1>
        <p>Entre para visualizar os feedbacks do Eureca Chat.</p>

        <label htmlFor="report-login">Login</label>
        <input
          id="report-login"
          type="text"
          value={login}
          onChange={(event) => onLoginChange(event.target.value)}
          autoComplete="username"
          autoFocus
          disabled={loading}
        />

        <label htmlFor="report-password">Senha</label>
        <input
          id="report-password"
          type="password"
          value={password}
          onChange={(event) => onPasswordChange(event.target.value)}
          autoComplete="current-password"
          disabled={loading}
        />

        {error && (
          <div className="login-error" role="alert">
            {error}
          </div>
        )}

        <button className="btn btn-primary login-submit" type="submit" disabled={loading}>
          {loading ? "Carregando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}

/* =================================================================
   Detalhe do dia
   ================================================================= */

interface DayBodyProps {
  day: DayBucket;
  openSession: string | null;
  onToggleSession: (key: string) => void;
}

function DayBody({ day, openSession, onToggleSession }: DayBodyProps) {
  const total = day.positivo + day.negativo;
  if (total === 0)
    return <div className="empty-chart">Nenhum feedback nesse dia.</div>;

  const pctPos = Math.round((day.positivo / total) * 100);
  const pctNeg = 100 - pctPos;
  const sessions = sessionsForDay(day);

  return (
    <>
      <div className="prop-bar">
        {day.positivo > 0 && (
          <div className="prop-seg blue" style={{ flex: day.positivo }}>
            {pctPos >= 10 ? `${pctPos}%` : ""}
          </div>
        )}
        {day.negativo > 0 && (
          <div className="prop-seg red" style={{ flex: day.negativo }}>
            {pctNeg >= 10 ? `${pctNeg}%` : ""}
          </div>
        )}
      </div>
      <div className="prop-legend">
        <b>{day.positivo}</b> gostei · <b>{day.negativo}</b> não gostei
      </div>

      <div className="chat-list">
        {sessions.map((s) => (
          <SessionRow
            key={s.key}
            session={s}
            open={openSession === s.key}
            onToggle={() => onToggleSession(s.key)}
          />
        ))}
      </div>
    </>
  );
}

interface SessionRowProps {
  session: Session;
  open: boolean;
  onToggle: () => void;
}

function SessionRow({ session, open, onToggle }: SessionRowProps) {
  const isGroup = session.items.length > 1;
  const first = session.items[0];
  const pos = session.items.filter((i) => i.positive).length;
  const neg = session.items.length - pos;
  const badgeClass = pos > 0 && neg > 0 ? "mixed" : pos > 0 ? "blue" : "red";

  const title = isGroup
    ? `Conversa · ${session.items.length} perguntas`
    : first.pergunta.slice(0, 72) + (first.pergunta.length > 72 ? "…" : "");

  const times = session.items.map((i) => i.timeLabel).filter(Boolean);
  const timeRange = times.length
    ? times[0] === times[times.length - 1]
      ? times[0]
      : `${times[0]}–${times[times.length - 1]}`
    : "";
  const sub = `${timeRange} · ${first.tipoUsuario === "anon" ? "anônimo" : "logado"}`;

  function handleKeyDown(e: KeyboardEvent<HTMLDivElement>): void {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onToggle();
    }
  }

  return (
    <div className={`chat-row${open ? " open" : ""}`}>
      <div
        className="chat-row-head"
        onClick={onToggle}
        onKeyDown={handleKeyDown}
        role="button"
        tabIndex={0}
        aria-expanded={open}
      >
        <span className={`chat-badge ${badgeClass}`} />
        <div className="chat-row-main">
          <div className="chat-row-title">{title}</div>
          <div className="chat-row-sub">{sub}</div>
        </div>
        <span className="chat-caret">▸</span>
      </div>

      {open && (
        <div className="chat-thread">
          {session.items.map((item) => (
            <div className="qa-pair" key={item.id}>
              <div
                className={`bubble bubble-pergunta ${item.positive ? "pos" : "neg"}`}
              >
                <div className="bubble-label">Pergunta</div>
                {item.pergunta}
                <div className="bubble-meta">
                  <span className={`dot ${item.positive ? "blue" : "red"}`} />{" "}
                  {item.positive ? "Gostei" : "Não gostei"} · {item.timeLabel}
                </div>
              </div>
              <div className="bubble bubble-resposta">
                <div className="bubble-label">Resposta</div>
                <div className="markdown-answer">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {item.resposta || "_Sem resposta registrada._"}
                  </ReactMarkdown>
                </div>
                {item.comentario && (
                  <div className="bubble-note">“{item.comentario}”</div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

/* =================================================================
   Estilos (escopados em .eureca-report)
   ================================================================= */

const CSS = `
html, body{margin:0; padding:0; min-width:100%; min-height:100%;}
body{overflow-x:hidden;}
html:has(.eureca-report[data-theme="dark"]){scrollbar-color:#596b7e #11161c;}
html:has(.eureca-report[data-theme="dark"])::-webkit-scrollbar{width:12px; background:#11161c;}
html:has(.eureca-report[data-theme="dark"])::-webkit-scrollbar-thumb{background:#596b7e; border-radius:8px; border:3px solid #11161c;}
.eureca-report{
  --paper:#ffffff; --surface:#ffffff; --surface-2:#f5f7f9;
  --ink:#182430; --ink-soft:#5b6672; --line:#d9dee3;
  --blue:#2d5fae; --blue-soft:rgba(45,95,174,.12); --blue-line:rgba(45,95,174,.35);
  --red:#c23b2b; --red-soft:rgba(194,59,43,.12); --red-line:rgba(194,59,43,.35);
  --radius:10px;
  --serif:'Source Serif 4', Georgia, 'Times New Roman', serif;
  --sans:'IBM Plex Sans', -apple-system, 'Segoe UI', Roboto, Arial, sans-serif;
  --shadow:0 1px 2px rgba(24,36,48,.06), 0 1px 12px rgba(24,36,48,.05);
  width:100%; background:var(--paper); color:var(--ink); font-family:var(--sans);
  -webkit-font-smoothing:antialiased; min-height:100vh;
}
.eureca-report[data-theme="dark"],
html[data-eureca-theme="dark"] .eureca-report{
  --paper:#11161c; --surface:#181f27; --surface-2:#1f2833;
  --ink:#e9edf1; --ink-soft:#a2adb8; --line:#2c3946;
  --blue:#7aa6ff; --blue-soft:rgba(122,166,255,.16); --blue-line:rgba(122,166,255,.4);
  --red:#ff9382; --red-soft:rgba(255,147,130,.16); --red-line:rgba(255,147,130,.4);
  --shadow:0 1px 2px rgba(0,0,0,.3), 0 1px 12px rgba(0,0,0,.25);
}

.eureca-report *{box-sizing:border-box;}
.eureca-report .shell{max-width:980px; margin:0 auto; padding:32px 20px 80px;}

/* ---------- login ---------- */
.eureca-report .login-shell{min-height:100vh; display:grid; place-items:center; padding:24px;}
.eureca-report .login-loading{color:var(--ink-soft); font-size:14px;}
.eureca-report .login-card{width:min(100%,390px); padding:32px; background:var(--surface); border:1px solid var(--line); border-radius:14px; box-shadow:var(--shadow);}
.eureca-report .login-topbar{display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:22px; color:var(--ink-soft); font-size:12px;}
.eureca-report .login-theme{border:0; background:transparent; color:var(--ink-soft); cursor:pointer; font:inherit;}
.eureca-report .login-theme:hover{color:var(--ink);}
.eureca-report .login-mark{width:42px; height:42px; display:grid; place-items:center; margin-bottom:18px; border-radius:12px; background:var(--ink); color:var(--surface); font-family:var(--serif); font-size:24px; font-weight:700;}
.eureca-report .login-card h1{margin:0 0 7px; font-family:var(--serif); font-size:25px;}
.eureca-report .login-card p{margin:0 0 24px; color:var(--ink-soft); font-size:14px; line-height:1.5;}
.eureca-report .login-card label{display:block; margin:14px 0 6px; font-size:13px; font-weight:600;}
.eureca-report .login-card input{width:100%; padding:11px 12px; border:1px solid var(--line); border-radius:8px; background:var(--surface); color:var(--ink); font:inherit; outline:none;}
.eureca-report .login-card input:focus{border-color:var(--blue); box-shadow:0 0 0 3px var(--blue-soft);}
.eureca-report .login-card input:disabled{opacity:.65;}
.eureca-report .login-submit{width:100%; justify-content:center; margin-top:22px;}
.eureca-report .login-error{margin-top:14px; padding:10px 12px; border:1px solid var(--red-line); border-radius:8px; background:var(--red-soft); color:var(--red); font-size:13px; line-height:1.4;}

/* ---------- header ---------- */
.eureca-report .header{display:flex; flex-wrap:wrap; gap:16px; justify-content:space-between; align-items:flex-end; margin-bottom:22px;}
.eureca-report .header h1{font-family:var(--serif); font-weight:600; font-size:30px; margin:0 0 6px; letter-spacing:-.01em;}
.eureca-report .header p{margin:0; color:var(--ink-soft); font-size:14.5px; max-width:52ch;}
.eureca-report .toolbar{display:flex; gap:8px; flex-wrap:wrap;}
.eureca-report .btn{
  font-family:var(--sans); font-size:13.5px; font-weight:500; cursor:pointer;
  border-radius:8px; padding:9px 14px; border:1px solid var(--line);
  background:var(--surface); color:var(--ink); transition:border-color .15s, background .15s;
  display:inline-flex; align-items:center; gap:6px; white-space:nowrap;
}
.eureca-report .btn:hover{border-color:var(--ink-soft);}
.eureca-report .btn:disabled{cursor:wait; opacity:.6;}
.eureca-report .btn-primary{background:var(--ink); color:var(--surface); border-color:var(--ink);}
.eureca-report .btn-primary:hover{opacity:.88;}
.eureca-report .btn-danger-ghost{color:var(--red);}
.eureca-report input[type=file]{display:none;}

.eureca-report .banner{
  display:flex; align-items:center; justify-content:space-between; gap:12px; flex-wrap:wrap;
  background:var(--surface-2); border:1px dashed var(--line); border-radius:var(--radius);
  padding:12px 16px; margin-bottom:22px; font-size:13.5px; color:var(--ink-soft);
}
.eureca-report .banner strong{color:var(--ink);}
.eureca-report .banner-error{border-style:solid; border-color:var(--red-line); color:var(--red); background:var(--red-soft);}

/* ---------- summary ---------- */
.eureca-report .summary{display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin-bottom:26px;}
.eureca-report .summary-card{background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); padding:14px 16px; box-shadow:var(--shadow);}
.eureca-report .summary-value{font-family:var(--serif); font-size:24px; font-weight:600; line-height:1.1;}
.eureca-report .summary-label{font-size:12px; color:var(--ink-soft); margin-top:4px;}
@media (max-width:680px){ .eureca-report .summary{grid-template-columns:repeat(2,1fr);} }

/* ---------- range controls ---------- */
.eureca-report .range-row{display:flex; align-items:center; gap:14px; flex-wrap:wrap; margin-bottom:16px;}
.eureca-report .presets{display:flex; gap:6px; background:var(--surface-2); padding:4px; border-radius:9px; border:1px solid var(--line);}
.eureca-report .preset-btn{
  border:none; background:transparent; color:var(--ink-soft); font-family:var(--sans);
  font-size:13px; font-weight:500; padding:6px 11px; border-radius:6px; cursor:pointer;
}
.eureca-report .preset-btn.active{background:var(--surface); color:var(--ink); box-shadow:var(--shadow);}
.eureca-report .dates{display:flex; align-items:center; gap:8px; font-size:13px; color:var(--ink-soft);}
.eureca-report .dates input{
  font-family:var(--sans); font-size:13px; color:var(--ink); background:var(--surface);
  border:1px solid var(--line); border-radius:7px; padding:6px 8px;
}

/* ---------- chart ---------- */
.eureca-report .chart-card{background:var(--surface); border:1px solid var(--line); border-radius:var(--radius); box-shadow:var(--shadow); padding:20px 20px 8px; margin-bottom:26px;}
.eureca-report .chart-head{display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:8px; margin-bottom:4px;}
.eureca-report .chart-title{font-family:var(--serif); font-size:18px; font-weight:600;}
.eureca-report .chart-actions{display:flex; align-items:center; gap:10px; flex-wrap:wrap; justify-content:flex-end;}
.eureca-report .chart-caption{font-size:12.5px; color:var(--ink-soft);}
.eureca-report .chart-mode-btn{border:1px solid var(--line); border-radius:7px; padding:6px 9px; background:var(--surface-2); color:var(--ink); cursor:pointer; font:12px var(--sans);}
.eureca-report .chart-mode-btn:hover{border-color:var(--ink-soft);}
.eureca-report .legend{display:flex; gap:16px; margin:10px 0 4px; font-size:12.5px; color:var(--ink-soft);}
.eureca-report .legend-item{display:flex; align-items:center; gap:6px;}
.eureca-report .dot{width:9px; height:9px; border-radius:50%; display:inline-block;}
.eureca-report .dot.blue{background:var(--blue);}
.eureca-report .dot.red{background:var(--red);}
.eureca-report .hint{font-size:12px; color:var(--ink-soft); margin:2px 0 14px;}
.eureca-report .chart-scroll{overflow-x:auto; padding-bottom:6px;}
.eureca-report .chart{display:flex; align-items:flex-end; gap:7px; height:190px; min-width:100%;}
.eureca-report .col{display:flex; flex-direction:column; align-items:center; gap:6px; flex:0 0 auto; width:26px;}
.eureca-report .bar-wrap{
  width:100%; height:150px; display:flex; flex-direction:column-reverse; justify-content:flex-start;
  border-radius:4px 4px 2px 2px; overflow:hidden; cursor:pointer; background:var(--surface-2);
  border:1px solid transparent;
}
.eureca-report .col.selected .bar-wrap{border-color:var(--ink);}
.eureca-report .bar-wrap:hover{filter:brightness(0.94);}
.eureca-report .seg{width:100%;}
.eureca-report .seg.blue{background:var(--blue);}
.eureca-report .seg.red{background:var(--red);}
.eureca-report .col-label{font-size:10.5px; color:var(--ink-soft); writing-mode:vertical-rl; transform:rotate(180deg); height:38px;}
.eureca-report .empty-chart{padding:40px 0; text-align:center; color:var(--ink-soft); font-size:14px;}

/* ---------- day detail ---------- */
.eureca-report .detail{
  background:var(--surface); border:1px solid var(--line); border-radius:var(--radius);
  box-shadow:var(--shadow); padding:22px; margin-bottom:26px; display:none;
}
.eureca-report .detail.open{display:block; animation:eurecaSlideIn .22s ease;}
@keyframes eurecaSlideIn{ from{opacity:0; transform:translateY(-6px);} to{opacity:1; transform:none;} }
@media (prefers-reduced-motion: reduce){ .eureca-report .detail.open{animation:none;} }
.eureca-report .detail-head{display:flex; justify-content:space-between; align-items:baseline; flex-wrap:wrap; gap:10px; margin-bottom:14px;}
.eureca-report .detail-title{font-family:var(--serif); font-size:19px; font-weight:600;}
.eureca-report .detail-close{font-size:13px; color:var(--ink-soft); cursor:pointer; background:none; border:none; font-family:var(--sans);}
.eureca-report .detail-close:hover{color:var(--ink);}
.eureca-report .prop-bar{display:flex; height:26px; border-radius:6px; overflow:hidden; border:1px solid var(--line); margin-bottom:8px;}
.eureca-report .prop-seg{display:flex; align-items:center; justify-content:center; font-size:11.5px; font-weight:600; color:#fff;}
.eureca-report .prop-seg.blue{background:var(--blue);}
.eureca-report .prop-seg.red{background:var(--red);}
.eureca-report .prop-legend{font-size:12.5px; color:var(--ink-soft); margin-bottom:20px;}
.eureca-report .prop-legend b{color:var(--ink); font-weight:600;}

.eureca-report .chat-list{display:flex; flex-direction:column; gap:8px;}
.eureca-report .chat-row{border:1px solid var(--line); border-radius:9px; overflow:hidden;}
.eureca-report .chat-row-head{display:flex; align-items:center; gap:10px; padding:11px 13px; cursor:pointer; background:var(--surface);}
.eureca-report .chat-row-head:hover{background:var(--surface-2);}
.eureca-report .chat-badge{width:8px; height:8px; border-radius:50%; flex:0 0 auto;}
.eureca-report .chat-badge.blue{background:var(--blue);}
.eureca-report .chat-badge.red{background:var(--red);}
.eureca-report .chat-badge.mixed{background:linear-gradient(90deg,var(--blue) 50%, var(--red) 50%);}
.eureca-report .chat-row-main{flex:1; min-width:0;}
.eureca-report .chat-row-title{font-size:13.5px; font-weight:500; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.eureca-report .chat-row-sub{font-size:11.5px; color:var(--ink-soft); margin-top:1px;}
.eureca-report .chat-caret{font-size:11px; color:var(--ink-soft); transition:transform .15s; flex:0 0 auto;}
.eureca-report .chat-row.open .chat-caret{transform:rotate(90deg);}
.eureca-report .chat-thread{padding:16px; background:var(--surface-2); border-top:1px solid var(--line);}

.eureca-report .qa-pair{display:flex; flex-direction:column; gap:8px; margin-bottom:16px;}
.eureca-report .qa-pair:last-child{margin-bottom:0;}
.eureca-report .bubble{max-width:74%; padding:10px 13px; border-radius:12px; font-size:13.5px; line-height:1.48;}
.eureca-report .bubble-label{font-size:10.5px; font-weight:600; text-transform:uppercase; letter-spacing:.04em; opacity:.6; margin-bottom:3px;}
.eureca-report .bubble-pergunta{align-self:flex-end; background:var(--surface); border:1.5px solid var(--line); border-top-right-radius:3px;}
.eureca-report .bubble-pergunta.pos{border-color:var(--blue-line);}
.eureca-report .bubble-pergunta.neg{border-color:var(--red-line);}
.eureca-report .bubble-resposta{align-self:flex-start; background:var(--surface); border:1px solid var(--line); border-top-left-radius:3px;}
.eureca-report .markdown-answer{overflow-wrap:anywhere;}
.eureca-report .markdown-answer p{margin:0 0 10px;}
.eureca-report .markdown-answer p:last-child{margin-bottom:0;}
.eureca-report .markdown-answer h1,
.eureca-report .markdown-answer h2,
.eureca-report .markdown-answer h3,
.eureca-report .markdown-answer h4{font-family:var(--serif); line-height:1.25; margin:14px 0 7px;}
.eureca-report .markdown-answer h1{font-size:22px;}
.eureca-report .markdown-answer h2{font-size:19px;}
.eureca-report .markdown-answer h3{font-size:17px;}
.eureca-report .markdown-answer ul,
.eureca-report .markdown-answer ol{margin:8px 0 10px; padding-left:22px;}
.eureca-report .markdown-answer li{margin:4px 0;}
.eureca-report .markdown-answer blockquote{margin:10px 0; padding:8px 12px; border-left:3px solid var(--blue); background:var(--blue-soft); color:var(--ink-soft);}
.eureca-report .markdown-answer code{padding:2px 5px; border-radius:4px; background:var(--surface-2); font-size:.92em;}
.eureca-report .markdown-answer pre{margin:10px 0; padding:11px 12px; overflow:auto; border-radius:7px; background:var(--surface-2); border:1px solid var(--line);}
.eureca-report .markdown-answer pre code{padding:0; background:transparent;}
.eureca-report .markdown-answer table{width:100%; margin:10px 0; border-collapse:collapse; font-size:12.5px;}
.eureca-report .markdown-answer th,
.eureca-report .markdown-answer td{padding:7px 8px; border:1px solid var(--line); text-align:left; vertical-align:top;}
.eureca-report .markdown-answer th{background:var(--surface-2); font-weight:600;}
.eureca-report .markdown-answer a{color:var(--blue); text-decoration:underline;}
.eureca-report .bubble-meta{display:flex; align-items:center; gap:6px; font-size:11px; color:var(--ink-soft); margin-top:5px;}
.eureca-report .bubble-note{margin-top:8px; padding:8px 10px; background:var(--surface-2); border-radius:8px; font-size:12.5px; color:var(--ink-soft); font-style:italic;}
@media (max-width:600px){ .eureca-report .bubble{max-width:100%;} }

.eureca-report .footer-note{margin-top:34px; font-size:12px; color:var(--ink-soft); text-align:center;}
.eureca-report .footer-note a{color:var(--ink-soft);}

@media print{
  .eureca-report .toolbar,
  .eureca-report .banner,
  .eureca-report .presets,
  .eureca-report .range-row .dates,
  .eureca-report .btn,
  .eureca-report .detail-close{display:none !important;}
  .eureca-report{background:#fff;}
  .eureca-report .shell{max-width:none; padding:0;}
  .eureca-report .chart-card,
  .eureca-report .detail,
  .eureca-report .summary-card,
  .eureca-report .chat-row{box-shadow:none; break-inside:avoid;}
  .eureca-report *{-webkit-print-color-adjust:exact; print-color-adjust:exact;}
  @page{ size:A4; margin:16mm; }
}
`;
