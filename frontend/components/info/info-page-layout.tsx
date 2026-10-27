import type { ReactNode } from 'react'
import Image from 'next/image'
import Link from 'next/link'
import { ArrowLeft } from 'lucide-react'
import { ThemeToggle } from '@/components/theme-toggle'

interface InfoPageLayoutProps {
  children: ReactNode
}

export function InfoPageLayout({ children }: InfoPageLayoutProps) {
  return (
    <div className="studio-canvas flex min-h-dvh flex-col bg-background">
      <header className="sticky top-0 z-20 border-b border-border/70 bg-background/90 backdrop-blur-md">
        <div className="mx-auto flex h-16 w-full max-w-6xl items-center justify-between gap-4 px-4 sm:px-6">
          <Link
            href="/"
            aria-label="Ir para o EurecaChat"
            className="rounded-lg focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-brand-accent/30"
          >
            <Image
              src="/Eureca_AI_logo.png"
              alt="EurecaChat"
              width={426}
              height={110}
              priority
              className="h-auto w-36 dark:brightness-0 dark:invert sm:w-44"
            />
          </Link>

          <div className="flex items-center gap-1">
            <ThemeToggle />
            <Link
              href="/"
              className="inline-flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-muted-foreground transition-colors hover:bg-muted hover:text-brand sm:text-sm"
            >
              <ArrowLeft className="size-4" />
              Voltar ao chat
            </Link>
          </div>
        </div>
      </header>

      <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6 sm:py-14">
        {children}
      </main>

      <footer className="border-t border-border/70 bg-background/85">
        <div className="mx-auto flex min-h-16 w-full max-w-6xl items-center justify-center gap-3 px-4 text-xs text-muted-foreground">
          <Link href="/sobre/" className="transition-colors hover:text-brand">
            © 2026 Eureca
          </Link>
          <span aria-hidden>·</span>
          <Link href="/politica_termos/" className="transition-colors hover:text-brand">
            Termos
          </Link>
        </div>
      </footer>
    </div>
  )
}
