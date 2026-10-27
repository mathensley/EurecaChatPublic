import { EurecaLogo } from '@/components/eureca-logo'
import { AppVersionBadge } from '@/components/app-version-badge'
import { Menu } from 'lucide-react'

interface ChatHeaderProps {
  onOpenSidebar: () => void
}

export function ChatHeader({ onOpenSidebar }: ChatHeaderProps) {
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 bg-background/90 px-4 backdrop-blur-md">
      <div className="flex items-center gap-2">
        {/* Mobile: opens sidebar */}
        <button
          type="button"
          onClick={onOpenSidebar}
          aria-label="Abrir histórico"
          title="Abrir histórico"
          className="grid size-9 place-items-center rounded-lg text-foreground/70 transition-colors hover:bg-muted hover:text-foreground md:hidden"
        >
          <Menu className="size-5" />
        </button>

        <EurecaLogo className="text-[1.15rem]" />
      </div>
      <AppVersionBadge className="ml-auto hidden md:inline-flex" />
    </header>
  )
}
