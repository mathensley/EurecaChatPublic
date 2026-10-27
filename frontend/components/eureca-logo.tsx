import { cn } from '@/lib/utils'

interface EurecaLogoProps {
  className?: string
  /** Rendered on a dark surface (sidebar / hero) */
  onDark?: boolean
  showChat?: boolean
}

export function EurecaLogo({ className, onDark = false, showChat = true }: EurecaLogoProps) {
  return (
    <span className={cn('inline-flex items-end leading-none select-none', className)}>
      <span
        className={cn(
          'font-serif font-semibold tracking-tight text-[1.7em] leading-none',
          onDark ? 'text-white' : 'text-brand dark:text-[#e8eef8]',
        )}
      >
        E
        <span className="relative inline-block">
          u
          {/* cyan filament accent under the u */}
          <span
            aria-hidden
            className="absolute -bottom-[0.14em] left-1/2 h-[0.11em] w-[0.78em] -translate-x-1/2 rounded-full bg-brand-accent dark:bg-[#39b9e7]"
          />
        </span>
        reca
      </span>
      {showChat && (
        <span
          className={cn(
            'ml-1 mb-[0.15em] font-sans text-[0.62em] font-semibold tracking-tight',
            onDark ? 'text-brand-accent' : 'text-brand dark:text-[#39b9e7]',
          )}
        >
          Chat
        </span>
      )}
    </span>
  )
}
