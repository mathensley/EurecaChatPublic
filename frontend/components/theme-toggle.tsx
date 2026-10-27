'use client'

import { useEffect, useState } from 'react'
import { Moon, Sun } from 'lucide-react'
import { cn } from '@/lib/utils'

const THEME_STORAGE_KEY = 'eurecachat.theme'

function applyTheme(dark: boolean) {
  document.documentElement.classList.toggle('dark', dark)
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light'
}

interface ThemeToggleProps {
  className?: string
  onDark?: boolean
}

export function ThemeToggle({ className, onDark = false }: ThemeToggleProps) {
  const [dark, setDark] = useState<boolean | null>(null)

  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)')

    function syncWithSystem() {
      if (window.localStorage.getItem(THEME_STORAGE_KEY)) return
      applyTheme(media.matches)
      setDark(media.matches)
    }

    setDark(document.documentElement.classList.contains('dark'))
    media.addEventListener('change', syncWithSystem)
    return () => media.removeEventListener('change', syncWithSystem)
  }, [])

  function toggleTheme() {
    const nextDark = !(dark ?? document.documentElement.classList.contains('dark'))
    applyTheme(nextDark)
    window.localStorage.setItem(THEME_STORAGE_KEY, nextDark ? 'dark' : 'light')
    setDark(nextDark)
  }

  const label = dark ? 'Usar modo claro' : 'Usar modo escuro'

  return (
    <button
      type="button"
      onClick={toggleTheme}
      aria-label={label}
      title={label}
      className={cn(
        'grid size-8 place-items-center rounded-lg transition-colors',
        onDark
          ? 'text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-foreground'
          : 'text-muted-foreground hover:bg-muted hover:text-foreground',
        className,
      )}
    >
      {dark ? <Sun className="size-4" /> : <Moon className="size-4" />}
    </button>
  )
}
