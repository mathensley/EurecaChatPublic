import Image from 'next/image'
import { LoginForm } from '@/components/auth/login-form'
import { ThemeToggle } from '@/components/theme-toggle'

export default function LoginPage() {
  return (
    <main className="flex min-h-dvh flex-col items-center justify-center eureca-grid px-4 py-10">
      <ThemeToggle className="fixed right-4 top-4 z-10 size-10 rounded-xl border border-border bg-card shadow-soft" />
      <div className="w-full max-w-md">
        <div className="mb-6 flex items-center justify-center">
          <a href="/" aria-label="Voltar ao chat" className="rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-accent/30">
            <Image
              src="/Eureca_AI_logo.png"
              alt="EurecaChat"
              width={426}
              height={110}
              priority
              className="h-auto w-72 transition-opacity hover:opacity-85 dark:brightness-0 dark:invert sm:w-80"
            />
          </a>
        </div>

        <div className="overflow-hidden rounded-2xl border border-border bg-card shadow-card">
          <div className="bg-brand px-7 py-6 dark:bg-brand-deep">
            <p className="text-pretty text-sm leading-relaxed text-brand-foreground/90">
              Seja bem-vindo! Insira as suas credenciais do SIGAA para fazer login no EurecaChat.
            </p>
          </div>

          <div className="px-7 py-8">
            <LoginForm />
          </div>
        </div>

        <p className="mt-8 text-center text-xs text-muted-foreground">
          © 2026 Eureca — Todos os direitos reservados.
        </p>
      </div>
    </main>
  )
}
