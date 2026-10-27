'use client'

import { memo, useEffect, useId, useRef, useState } from 'react'

interface MermaidDiagramProps {
  chart: string
  deferRender?: boolean
  onRendered?: () => void
}

const renderedDiagrams = new Map<string, string>()

type MermaidColorScheme = 'light' | 'dark'

function getColorScheme(): MermaidColorScheme {
  return document.documentElement.classList.contains('dark') ? 'dark' : 'light'
}

function getThemeVariables(colorScheme: MermaidColorScheme) {
  const dark = colorScheme === 'dark'

  return {
    background: dark ? '#101827' : '#ffffff',
    primaryColor: dark ? '#17345f' : '#e8f4fa',
    primaryTextColor: dark ? '#e9eef6' : '#172033',
    primaryBorderColor: dark ? '#39b9e7' : '#258eb8',
    lineColor: dark ? '#8290a5' : '#526176',
    textColor: dark ? '#e9eef6' : '#172033',
    xyChart: {
      backgroundColor: dark ? '#101827' : '#ffffff',
      titleColor: dark ? '#f1f5f9' : '#172033',
      dataLabelColor: dark ? '#f1f5f9' : '#172033',
      xAxisLabelColor: dark ? '#c7d0dc' : '#445166',
      xAxisTitleColor: dark ? '#e1e7ef' : '#29364a',
      xAxisTickColor: dark ? '#65738a' : '#9aa6b7',
      xAxisLineColor: dark ? '#65738a' : '#9aa6b7',
      yAxisLabelColor: dark ? '#c7d0dc' : '#445166',
      yAxisTitleColor: dark ? '#e1e7ef' : '#29364a',
      yAxisTickColor: dark ? '#65738a' : '#9aa6b7',
      yAxisLineColor: dark ? '#65738a' : '#9aa6b7',
      plotColorPalette: dark ? '#39b9e7' : '#177ca5',
    },
  }
}

/** Renders a fenced ```mermaid block received in a chat message. */
export const MermaidDiagram = memo(function MermaidDiagram({ chart, deferRender = false, onRendered }: MermaidDiagramProps) {
  const instanceId = useId().replace(/[^a-zA-Z0-9_-]/g, '')
  const renderSequenceRef = useRef(0)
  const onRenderedRef = useRef(onRendered)
  const [colorScheme, setColorScheme] = useState<MermaidColorScheme | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [svg, setSvg] = useState<string | null>(null)

  useEffect(() => {
    onRenderedRef.current = onRendered
  }, [onRendered])

  useEffect(() => {
    const root = document.documentElement
    const updateColorScheme = () => setColorScheme(getColorScheme())
    const observer = new MutationObserver(updateColorScheme)

    updateColorScheme()
    observer.observe(root, { attributes: true, attributeFilter: ['class'] })

    return () => observer.disconnect()
  }, [])

  useEffect(() => {
    if (deferRender || !colorScheme) return
    let active = true
    const activeColorScheme = colorScheme

    async function renderDiagram() {
      try {
        const source = chart.trim()
        const cacheKey = `${activeColorScheme}:${source}`
        const cachedSvg = renderedDiagrams.get(cacheKey)
        if (cachedSvg) {
          setSvg(cachedSvg)
          setError(null)
          return
        }

        const { default: mermaid } = await import('mermaid')
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'strict',
          suppressErrorRendering: true,
          theme: activeColorScheme === 'dark' ? 'dark' : 'default',
          themeVariables: getThemeVariables(activeColorScheme),
        })

        const renderSequence = ++renderSequenceRef.current
        const { svg } = await mermaid.render(
          `mermaid-${instanceId}-${renderSequence}`,
          source,
        )

        if (!active) return
        renderedDiagrams.set(cacheKey, svg)
        setSvg(svg)
        setError(null)
      } catch (cause) {
        if (!active) return
        setSvg(null)
        setError(cause instanceof Error ? cause.message : 'Diagrama inválido')
      }
    }

    setSvg(null)
    setError(null)
    void renderDiagram()
    return () => {
      active = false
    }
  }, [chart, colorScheme, deferRender, instanceId])

  useEffect(() => {
    if ((!svg && !error) || deferRender || !onRenderedRef.current) return

    // Dois frames garantem que o SVG (ou a mensagem de erro) já participou
    // do layout antes de o chat medir sua altura para o scroll final.
    let secondFrame: number | null = null
    const firstFrame = requestAnimationFrame(() => {
      secondFrame = requestAnimationFrame(() => onRenderedRef.current?.())
    })
    return () => {
      cancelAnimationFrame(firstFrame)
      if (secondFrame !== null) cancelAnimationFrame(secondFrame)
    }
  }, [svg, error, deferRender])

  if (deferRender || !colorScheme) return null

  if (error) {
    return (
      <div
        role="alert"
        className="my-3 rounded-lg border border-destructive/35 bg-destructive/10 p-3 text-sm text-card-foreground"
      >
        <p className="font-medium">Não foi possível renderizar este gráfico.</p>
        <details className="mt-1 text-xs text-muted-foreground">
          <summary className="cursor-pointer">Ver detalhes</summary>
          <p className="mt-1 break-words">{error}</p>
        </details>
      </div>
    )
  }

  return (
    <div
      aria-label="Diagrama Mermaid"
      className="my-3 min-h-40 overflow-x-auto rounded-lg border border-border bg-background p-3 [&_svg]:mx-auto [&_svg]:h-auto [&_svg]:max-w-full"
      dangerouslySetInnerHTML={svg ? { __html: svg } : undefined}
    />
  )
})
