'use client'

import Link from 'next/link'
import { cn, truncate } from '@/lib/utils'
import { LogIn, LogOut, PanelLeft, Plus, X, Trash2 } from 'lucide-react'
import { ScrollArea } from '@/components/ui/scroll-area'
import { ThemeToggle } from '@/components/theme-toggle'
import { AppVersionBadge } from '@/components/app-version-badge'
import type { Conversation } from '@/types'

interface ChatSidebarProps {
  conversations: Conversation[]
  activeId: string | null
  onSelect: (id: string) => void
  onNewChat: () => void
  onDeleteConversation?: (id: string) => void
  open: boolean
  onClose: () => void
  onToggle: () => void
  authReady: boolean
  userName?: string
  onLogout: () => void | Promise<void>
}

function displayName(name?: string) {
  if (!name) return null
  const particles = new Set(['da', 'das', 'de', 'do', 'dos', 'e'])
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((part, index) => {
      const normalized = part.toLocaleLowerCase('pt-BR')
      if (index > 0 && particles.has(normalized)) return normalized
      return normalized.charAt(0).toLocaleUpperCase('pt-BR') + normalized.slice(1)
    })
    .join(' ')
}

function initials(name: string) {
  return name
    .split(/\s+/)
    .map((part) => part.charAt(0))
    .join('')
    .toLocaleUpperCase('pt-BR')
}

export function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDeleteConversation,
  open,
  onClose,
  onToggle,
  authReady,
  userName,
  onLogout,
}: ChatSidebarProps) {
  const shortName = displayName(userName)

  return (
    <>
      {/* Mobile overlay */}
      {open && (
        <div
          className="fixed inset-0 z-30 bg-brand-deep/40 backdrop-blur-sm md:hidden"
          onClick={onClose}
          aria-hidden
        />
      )}

      <aside
        className={cn(
          'fixed inset-y-0 left-0 z-40 flex h-full w-72 shrink-0 flex-col overflow-hidden bg-sidebar text-sidebar-foreground transition-[width,transform] duration-300 ease-in-out md:static md:z-auto md:translate-x-0',
          open
            ? 'translate-x-0 border-r border-sidebar-border md:w-72'
            : '-translate-x-full border-r-0 md:w-14 md:border-r md:border-sidebar-border',
        )}
      >
        <div className={cn('flex min-w-72 flex-1 flex-col overflow-hidden', !open && 'md:hidden')}>
          {/* Header */}
          <div className="flex items-center justify-between px-4 pt-5 pb-3">
            <span className="text-sm font-semibold tracking-tight text-sidebar-foreground">
              Histórico
            </span>
            <div className="flex items-center gap-0.5">
              <ThemeToggle onDark />
              <button
                onClick={onClose}
                className="grid size-8 place-items-center rounded-lg text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground md:hidden"
                aria-label="Fechar menu"
              >
                <X className="size-4" />
              </button>
              <button
                type="button"
                onClick={onToggle}
                className="hidden size-8 place-items-center rounded-lg text-sidebar-foreground/70 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground md:grid"
                aria-label="Recolher histórico"
                title="Recolher histórico"
              >
                <PanelLeft className="size-4" />
              </button>
            </div>
          </div>

          {/* New chat button */}
          <div className="px-3 pb-2">
            <button
              onClick={onNewChat}
              className="group flex w-full items-center gap-2 rounded-xl px-3 py-2.5 text-sm font-medium text-sidebar-foreground transition-colors hover:bg-sidebar-accent"
            >
              <span className="grid size-6 place-items-center rounded-lg bg-brand-accent/15 text-brand-accent transition-transform duration-200 group-hover:rotate-90">
                <Plus className="size-4" strokeWidth={2.5} />
              </span>
              Novo Chat
            </button>
          </div>

          <div className="px-3 pb-1">
            <p className="px-1 text-[0.7rem] font-semibold uppercase tracking-widest text-sidebar-foreground/45">
              Recentes
            </p>
          </div>

          {/* Conversation list */}
          <ScrollArea className="flex-1 px-3 pb-4">
            {conversations.length === 0 ? (
              <p className="px-3 py-8 text-center text-xs leading-relaxed text-sidebar-foreground/50">
                Suas conversas aparecerão aqui.
              </p>
            ) : (
              <nav className="space-y-0.5">
                {conversations.map((c) => {
                  const active = c.id === activeId
                  return (
                    <div key={c.id} className="group flex items-center gap-1 pr-1">
                      <button
                        onClick={() => onSelect(c.id)}
                        className={cn(
                          'flex min-w-0 flex-1 items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm transition-colors duration-150',
                          active
                            ? 'bg-sidebar-accent font-medium text-sidebar-foreground'
                            : 'text-sidebar-foreground/75 hover:bg-sidebar-accent/60 hover:text-sidebar-foreground',
                        )}
                      >
                        <span className="truncate">{truncate(c.title, 28)}</span>
                      </button>

                      {onDeleteConversation && (
                        <button
                          type="button"
                          onClick={() => onDeleteConversation(c.id)}
                          aria-label="Excluir conversa"
                          title="Excluir conversa"
                          className="grid size-7 shrink-0 place-items-center rounded-md text-sidebar-foreground/55 opacity-60 transition-all hover:bg-destructive/20 hover:text-red-200 hover:opacity-100"
                        >
                          <Trash2 className="size-3.5" />
                        </button>
                      )}
                    </div>
                  )
                })}
              </nav>
            )}
          </ScrollArea>

          {/* Account */}
          <div className="px-3 pb-2">
            {!authReady ? (
              <div
                aria-label="Verificando sessão"
                className="flex items-center gap-2.5 rounded-xl bg-sidebar-accent/40 p-2.5 ring-1 ring-inset ring-sidebar-border/50"
              >
                <span className="size-9 shrink-0 animate-pulse rounded-full bg-sidebar-foreground/10" />
                <span className="min-w-0 flex-1 space-y-1.5">
                  <span className="block h-3 w-24 animate-pulse rounded bg-sidebar-foreground/10" />
                  <span className="block h-2.5 w-16 animate-pulse rounded bg-sidebar-foreground/10" />
                </span>
              </div>
            ) : shortName ? (
              <div className="flex items-center gap-2.5 rounded-xl bg-sidebar-accent/70 p-2.5 shadow-soft ring-1 ring-inset ring-sidebar-border/80">
                <div className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-accent text-xs font-bold text-sidebar-primary-foreground shadow-soft">
                  {initials(shortName)}
                </div>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-semibold text-sidebar-foreground" title={userName}>
                    {shortName}
                  </p>
                  <p className="text-[0.7rem] text-sidebar-foreground/60">Conta conectada</p>
                </div>
                <button
                  type="button"
                  onClick={() => void onLogout()}
                  aria-label={`Sair da conta de ${shortName}`}
                  title="Sair"
                  className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-lg px-2 text-xs font-medium text-sidebar-foreground/75 transition-colors hover:bg-sidebar hover:text-sidebar-foreground"
                >
                  <LogOut className="size-4" />
                  <span>Sair</span>
                </button>
              </div>
            ) : (
              <a
                href="/login/"
                className="flex items-center gap-2.5 rounded-xl bg-sidebar-accent/70 p-2.5 text-sidebar-foreground shadow-soft ring-1 ring-inset ring-sidebar-border/80 transition-colors hover:bg-sidebar-accent"
              >
                <span className="grid size-9 shrink-0 place-items-center rounded-full bg-brand-accent text-sidebar-primary-foreground shadow-soft">
                  <LogIn className="size-4" />
                </span>
                <span className="min-w-0">
                  <span className="block text-sm font-semibold">Entrar</span>
                  <span className="block text-[0.7rem] text-sidebar-foreground/60">Acesse sua conta</span>
                </span>
              </a>
            )}
          </div>

          {/* Footer */}
          <div className="px-5 pb-3 pt-1">
            <div className="flex items-center gap-3 text-xs text-sidebar-foreground/50">
              <Link
                href="/sobre/"
                prefetch={false}
                className="underline-offset-2 transition-colors hover:text-sidebar-foreground hover:underline"
              >
                © 2026 Eureca
              </Link>
              <span>·</span>
              <Link
                href="/politica_termos/"
                prefetch={false}
                className="underline-offset-2 transition-colors hover:text-sidebar-foreground hover:underline"
              >
                Termos
              </Link>
              <AppVersionBadge variant="sidebar" className="ml-auto md:hidden" />
            </div>
          </div>
        </div>

        {!open && (
          <div className="hidden h-full w-14 flex-col items-center pb-4 pt-3 md:flex">
            <button
              type="button"
              onClick={onToggle}
              aria-label="Abrir histórico"
              title="Abrir histórico"
              className="grid size-9 place-items-center rounded-lg text-sidebar-foreground/75 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
            >
              <PanelLeft className="size-4" />
            </button>
            <ThemeToggle onDark className="mt-1" />
            <div className="mt-auto">
              {!authReady ? (
                <span
                  aria-label="Verificando sessão"
                  className="block size-9 animate-pulse rounded-lg bg-sidebar-accent/45 ring-1 ring-inset ring-sidebar-border/50"
                />
              ) : shortName ? (
                <button
                  type="button"
                  onClick={() => void onLogout()}
                  aria-label={`Sair da conta de ${shortName}`}
                  title={`Sair da conta de ${shortName}`}
                  className="grid size-9 place-items-center rounded-lg bg-sidebar-accent/70 text-sidebar-foreground/80 ring-1 ring-inset ring-sidebar-border/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
                >
                  <LogOut className="size-4" />
                </button>
              ) : (
                <a
                  href="/login/"
                  aria-label="Entrar"
                  title="Entrar"
                  className="grid size-9 place-items-center rounded-lg bg-sidebar-accent/70 text-brand-accent ring-1 ring-inset ring-sidebar-border/80 transition-colors hover:bg-sidebar-accent hover:text-sidebar-foreground"
                >
                  <LogIn className="size-4" />
                </a>
              )}
            </div>
          </div>
        )}
      </aside>
    </>
  )
}
