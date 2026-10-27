"use client";

import { FormEvent, useEffect, useState } from "react";
import PhoenixDashboard from "./observabilidades";

interface LoginCredentials {
  login: string;
  senha: string;
}

const AUTH_SESSION_KEY = "eureca_relatorios_auth";

export default function ObservabilidadePage() {
  const [credentials, setCredentials] = useState<LoginCredentials | null>(null);
  const [authenticated, setAuthenticated] = useState(false);
  const [loading, setLoading] = useState(true);
  const [login, setLogin] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [phoenixTurns, setPhoenixTurns] = useState<import("./observabilidades").Turn[]>([]);
  const [phoenixLoading, setPhoenixLoading] = useState(false);
  const [phoenixError, setPhoenixError] = useState("");
  const [phoenixTruncated, setPhoenixTruncated] = useState(false);
  const [phoenixSpanCount, setPhoenixSpanCount] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function loadCredentials(): Promise<void> {
      try {
        const response = await fetch("/login.json", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const parsed = (await response.json()) as LoginCredentials;
        if (typeof parsed.login !== "string" || typeof parsed.senha !== "string") {
          throw new Error("formato inválido no login.json");
        }
        if (!cancelled) {
          setCredentials(parsed);
          try {
            setAuthenticated(sessionStorage.getItem(AUTH_SESSION_KEY) === "1");
          } catch {
            /* solicita login quando a sessão não estiver disponível */
          }
        }
      } catch (err) {
        if (!cancelled) {
          const detail = err instanceof Error ? err.message : String(err);
          setError(`Não foi possível carregar as credenciais. (${detail})`);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    loadCredentials();
    return () => {
      cancelled = true;
    };
  }, []);

  function handleSubmit(event: FormEvent<HTMLFormElement>): void {
    event.preventDefault();
    if (!credentials) {
      setError("As credenciais ainda não estão disponíveis.");
      return;
    }
    if (login === credentials.login && password === credentials.senha) {
      setError("");
      setAuthenticated(true);
      try {
        sessionStorage.setItem(AUTH_SESSION_KEY, "1");
      } catch {
        /* continua autenticado nesta aba */
      }
    } else {
      setError("Login ou senha inválidos.");
    }
  }

  function logout(): void {
    setAuthenticated(false);
    try {
      sessionStorage.removeItem(AUTH_SESSION_KEY);
    } catch {
      /* ignora */
    }
  }

  async function loadPhoenix(signal?: AbortSignal): Promise<void> {
    setPhoenixLoading(true);
    setPhoenixError("");
    try {
      const response = await fetch("/api/phoenix", { cache: "no-store", signal });
      const body = await response.json();
      if (!response.ok) throw new Error(body.error || `HTTP ${response.status}`);
      if (signal?.aborted) return;
      setPhoenixTurns(Array.isArray(body.turns) ? body.turns : []);
      setPhoenixTruncated(body.truncated === true);
      setPhoenixSpanCount(typeof body.spanCount === "number" ? body.spanCount : null);
    } catch (err) {
      if (signal?.aborted) return;
      setPhoenixError(err instanceof Error ? err.message : String(err));
    } finally {
      if (!signal?.aborted) setPhoenixLoading(false);
    }
  }

  useEffect(() => {
    if (!authenticated) return;
    const controller = new AbortController();
    void loadPhoenix(controller.signal);
    return () => controller.abort();
  }, [authenticated]);

  if (loading) {
    return (
      <div className="obs-page">
        <style>{OBS_PAGE_STYLES}</style>
        <div className="obs-loading">Carregando…</div>
      </div>
    );
  }

  if (!authenticated) {
    return (
      <div className="obs-page">
        <style>{OBS_PAGE_STYLES}</style>
        <main className="obs-login-shell">
          <form className="obs-login-card" onSubmit={handleSubmit}>
            <div className="obs-login-topbar">
              <span>Área restrita</span>
              <a href="/">Relatórios</a>
            </div>
            <div className="obs-login-mark">E</div>
            <h1>Acesso à observabilidade</h1>
            <p>Entre para visualizar a observabilidade do Eureca Chat.</p>

            <label htmlFor="obs-login">Login</label>
            <input
              id="obs-login"
              type="text"
              value={login}
              onChange={(event) => setLogin(event.target.value)}
              autoComplete="username"
              autoFocus
            />


            <label htmlFor="obs-password">Senha</label>
            <input
              id="obs-password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="current-password"
            />

            {error && <div className="obs-login-error" role="alert">{error}</div>}
            <button className="obs-login-submit" type="submit">Entrar</button>
          </form>
        </main>
      </div>
    );
  }

  return (
    <div className="obs-page">
      <style>{OBS_PAGE_STYLES}</style>
      <nav className="obs-navigation" aria-label="Navegação dos painéis">
        <strong>Observabilidade do Eureca Chat</strong>
        <div>
          <a href="/">Relatórios</a>
          <button type="button" onClick={logout}>Sair</button>
        </div>
      </nav>
      <div className="obs-toolbar">
        {phoenixSpanCount !== null && <span>{phoenixSpanCount.toLocaleString("pt-BR")} spans carregados</span>}
        <button type="button" onClick={() => void loadPhoenix()} disabled={phoenixLoading}>
          {phoenixLoading ? "Atualizando…" : "Atualizar dados"}
        </button>
      </div>
      {phoenixLoading && <div className="obs-loading">Carregando dados do Phoenix…</div>}
      {phoenixError && <div className="obs-login-error" role="alert">{phoenixError}</div>}
      {phoenixTruncated && (
        <div className="obs-warning" role="status">
          A consulta atingiu o limite de páginas. Reduza o período ou aumente PHOENIX_SPANS_MAX_PAGES.
        </div>
      )}
      {!phoenixLoading && !phoenixError && <PhoenixDashboard turns={phoenixTurns} />}
    </div>
  );
}

const OBS_PAGE_STYLES = `
  html, body { margin: 0; padding: 0; min-height: 100%; background: #12161d; }
  .obs-page { min-height: 100vh; box-sizing: border-box; padding: 20px; background: #12161d; color: #e6e9ef; font-family: -apple-system, "Inter", "Segoe UI", system-ui, sans-serif; }
  .obs-navigation { max-width: 1240px; margin: 0 auto 14px; display: flex; align-items: center; justify-content: space-between; gap: 16px; color: #e6e9ef; }
  .obs-navigation div { display: flex; align-items: center; gap: 8px; }
  .obs-navigation a, .obs-navigation button { border: 1px solid #2a3140; border-radius: 7px; padding: 7px 11px; background: #1b212b; color: #e6e9ef; text-decoration: none; cursor: pointer; font: inherit; font-size: 13px; }
  .obs-navigation a:hover, .obs-navigation button:hover { border-color: #6c8eef; }
  .obs-toolbar { max-width: 1240px; margin: 0 auto 12px; display: flex; justify-content: flex-end; align-items: center; gap: 12px; color: #8b94a7; font-size: 12px; }
  .obs-toolbar button { border: 1px solid #2a3140; border-radius: 7px; padding: 7px 11px; background: #1b212b; color: #e6e9ef; cursor: pointer; font: inherit; }
  .obs-toolbar button:disabled { opacity: .55; cursor: wait; }
  .obs-warning { max-width: 1240px; margin: 0 auto 12px; padding: 10px 12px; border: 1px solid rgba(232,163,61,.45); border-radius: 8px; background: rgba(232,163,61,.12); color: #e8c27b; font-size: 13px; }
  .obs-loading { min-height: 100vh; display: grid; place-items: center; color: #8b94a7; }
  .obs-login-shell { min-height: calc(100vh - 40px); display: grid; place-items: center; }
  .obs-login-card { width: min(100%, 390px); box-sizing: border-box; padding: 32px; background: #1b212b; border: 1px solid #2a3140; border-radius: 14px; box-shadow: 0 10px 30px rgba(0,0,0,.25); }
  .obs-login-topbar { display: flex; justify-content: space-between; margin-bottom: 22px; color: #8b94a7; font-size: 12px; }
  .obs-login-topbar a { color: #8b94a7; text-decoration: none; }
  .obs-login-topbar a:hover { color: #e6e9ef; }
  .obs-login-mark { width: 42px; height: 42px; display: grid; place-items: center; margin-bottom: 18px; border-radius: 12px; background: #e6e9ef; color: #12161d; font-size: 24px; font-weight: 700; }
  .obs-login-card h1 { margin: 0 0 7px; font-size: 25px; }
  .obs-login-card p { margin: 0 0 24px; color: #8b94a7; font-size: 14px; line-height: 1.5; }
  .obs-login-card label { display: block; margin: 14px 0 6px; font-size: 13px; font-weight: 600; }
  .obs-login-card input { width: 100%; box-sizing: border-box; padding: 11px 12px; border: 1px solid #2a3140; border-radius: 8px; background: #12161d; color: #e6e9ef; font: inherit; outline: none; }
  .obs-login-card input:focus { border-color: #6c8eef; box-shadow: 0 0 0 3px rgba(108,142,239,.18); }
  .obs-login-error { margin-top: 14px; padding: 10px 12px; border: 1px solid rgba(229,72,77,.45); border-radius: 8px; background: rgba(229,72,77,.14); color: #ff8d91; font-size: 13px; }
  .obs-login-submit { width: 100%; margin-top: 22px; padding: 10px 14px; border: 0; border-radius: 8px; background: #e6e9ef; color: #12161d; cursor: pointer; font: inherit; font-weight: 600; }
  @media (max-width: 600px) { .obs-page { padding: 12px; } .obs-navigation { align-items: flex-start; flex-direction: column; } }
`;
