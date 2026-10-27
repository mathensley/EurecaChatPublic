'use client'

import { useState } from 'react'
import { User, Lock, Eye, EyeOff, LoaderCircle } from 'lucide-react'
import { authService } from '@/services/auth'

export function LoginForm() {
  const [showPassword, setShowPassword] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!username.trim() || !password || loading) return
    setLoading(true)
    setError(null)
    try {
      await authService.login(username.trim(), password)
      window.location.replace('/')
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Não foi possível entrar.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <form className="space-y-5" onSubmit={submit}>
      <div className="space-y-1.5">
        <label htmlFor="usuario" className="block text-sm font-medium text-foreground">Usuário</label>
        <div className="group relative">
          <User className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-brand" />
          <input id="usuario" type="text" value={username} onChange={(event) => setUsername(event.target.value)} disabled={loading} required autoComplete="username" placeholder="Seu usuário acadêmico" className="w-full rounded-xl border border-input bg-background py-3 pl-10 pr-3.5 text-[0.95rem] text-foreground outline-none transition-all duration-200 placeholder:text-muted-foreground/70 focus:border-brand-accent/70 focus:ring-4 focus:ring-brand-accent/10" />
        </div>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="senha" className="block text-sm font-medium text-foreground">Senha</label>
        <div className="group relative">
          <Lock className="pointer-events-none absolute left-3.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground transition-colors group-focus-within:text-brand" />
          <input id="senha" type={showPassword ? 'text' : 'password'} value={password} onChange={(event) => setPassword(event.target.value)} disabled={loading} required autoComplete="current-password" placeholder="Sua senha" className="w-full rounded-xl border border-input bg-background py-3 pl-10 pr-11 text-[0.95rem] text-foreground outline-none transition-all duration-200 placeholder:text-muted-foreground/70 focus:border-brand-accent/70 focus:ring-4 focus:ring-brand-accent/10" />
          <button type="button" onClick={() => setShowPassword((current) => !current)} aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'} className="absolute right-2.5 top-1/2 grid size-8 -translate-y-1/2 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-brand">
            {showPassword ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
          </button>
        </div>
      </div>

      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      <button type="submit" disabled={loading || !username.trim() || !password} className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary py-3 text-sm font-semibold uppercase tracking-wide text-primary-foreground shadow-soft transition-all duration-200 hover:bg-brand-deep hover:shadow-card active:scale-[0.99] disabled:cursor-not-allowed disabled:opacity-60">
        {loading && <LoaderCircle className="size-4 animate-spin" />}
        {loading ? 'Entrando…' : 'Entrar'}
      </button>
    </form>
  )
}
