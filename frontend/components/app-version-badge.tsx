import { cn } from '@/lib/utils'

interface AppVersionBadgeProps {
  className?: string
  variant?: 'default' | 'sidebar'
}

const appVersion = process.env.NEXT_PUBLIC_APP_VERSION ?? 'local'
const releaseStage = process.env.NEXT_PUBLIC_RELEASE_STAGE ?? 'dev'
const formattedStage = releaseStage.charAt(0).toLocaleUpperCase('pt-BR') + releaseStage.slice(1)

export function AppVersionBadge({
  className,
  variant = 'default',
}: AppVersionBadgeProps) {
  return (
    <span
      aria-label={`Versão ${appVersion}, estágio ${formattedStage}`}
      title={`EurecaChat v${appVersion} — ${formattedStage}`}
      className={cn(
        'inline-flex shrink-0 items-center',
        variant === 'sidebar'
          ? 'gap-1.5 text-xs font-normal text-sidebar-foreground/50'
          : 'gap-1.5 rounded-full border border-border/80 bg-muted/55 px-2.5 py-1 text-[0.65rem] font-medium tracking-wide text-muted-foreground shadow-soft dark:bg-muted/35',
        className,
      )}
    >
      <span>v{appVersion}</span>
      {variant === 'sidebar' ? (
        <span aria-hidden>·</span>
      ) : (
        <span aria-hidden className="size-1 rounded-full bg-brand-accent" />
      )}
      <span className={variant === 'sidebar' ? undefined : 'text-brand'}>
        {formattedStage}
      </span>
    </span>
  )
}
