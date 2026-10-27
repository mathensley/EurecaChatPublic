'use client'

import { useCallback, useEffect, useRef, useState, type CSSProperties } from 'react'
import {
  permissionLabels,
  permissionProfiles,
  permissions,
  profileNames,
  profiles,
  roleLabels,
  scenes,
  type PollData,
  type ProfileId,
  type TutorialCase,
  type TutorialMessage,
  type TutorialProfile,
} from './tutorial-data'

const VIDEO_URL = ''

type CssVariables = CSSProperties & Record<`--${string}`, string | number>

function formatDuration(seconds: number) {
  return `${Math.floor(seconds / 60)}:${String(seconds % 60).padStart(2, '0')}`
}

function initials(name: string) {
  const words = name.split(' ').filter((word) => !word.endsWith('.'))
  return (words[0] || name).charAt(0).toUpperCase()
}

function fileExtension(file: string) {
  return file.split('.').pop()?.toUpperCase() ?? 'ARQ'
}

function buildScript() {
  const total = scenes.reduce((sum, scene) => sum + scene.duration, 0)
  const output = [`ROTEIRO DO VÍDEO TUTORIAL GERAL · Eureca Chat · ${formatDuration(total)}`, '']
  let elapsed = 0

  scenes.forEach((scene, index) => {
    output.push(
      `CENA ${index + 1} · ${scene.title} (${formatDuration(elapsed)} a ${formatDuration(elapsed + scene.duration)})`,
      `Tela: ${scene.screen}`,
      `Narração: ${scene.narration}`,
      `Dica de gravação: ${scene.tip}`,
      '',
    )
    elapsed += scene.duration
  })

  return output.join('\n')
}

function Poll({ poll }: { poll: PollData }) {
  const [animated, setAnimated] = useState(false)
  const total = poll.options.reduce((sum, option) => sum + option.votes, 0)
  const highest = Math.max(...poll.options.map((option) => option.votes))

  useEffect(() => {
    const timeout = window.setTimeout(() => setAnimated(true), 60)
    return () => window.clearTimeout(timeout)
  }, [])

  return (
    <div className="poll">
      <div className="q">{poll.question}</div>
      <ul>
        {poll.options.map((option, index) => {
          const percentage = Math.round((option.votes * 100) / total)

          return (
            <li
              key={option.label}
              data-mine={poll.selectedOption === index ? '1' : '0'}
              data-top={option.votes === highest ? '1' : '0'}
            >
              <div className="row">
                <span>
                  {option.label}
                  {poll.selectedOption === index ? ' (seu voto)' : ''}
                </span>
                <span>{option.votes} · {percentage}%</span>
              </div>
              <div className="track">
                <div className="fill" style={{ width: animated ? `${percentage}%` : '0%' }} />
              </div>
            </li>
          )
        })}
      </ul>
      <div className="foot">{total} votos</div>
    </div>
  )
}

function Message({ message }: { message: TutorialMessage }) {
  if (message.role === 'sistema') {
    return <div className="sys"><span>{message.text}</span></div>
  }

  const name = message.name ?? ''

  return (
    <div className="msg" data-role={message.role}>
      <div className="av" aria-hidden="true">{initials(name)}</div>
      <div className="mb">
        <div className="mh">
          <strong>{name}</strong>
          <span className="role">{roleLabels[message.role]}</span>
          <time>{message.time}</time>
        </div>
        {message.text && <p>{message.text}</p>}
        {message.attachment && (
          <div className="att">
            <span className="ext">{fileExtension(message.attachment.file)}</span>
            <span className="fn">{message.attachment.file}</span>
            <span className="sz">{message.attachment.size}</span>
          </div>
        )}
        {message.poll && <Poll poll={message.poll} />}
      </div>
    </div>
  )
}

function Simulator({ tutorialCase, step }: { tutorialCase: TutorialCase; step: number }) {
  const chatBodyRef = useRef<HTMLDivElement>(null)
  const visibleMessages = tutorialCase.messages.filter((message) => message.at <= step + 1)

  useEffect(() => {
    const chatBody = chatBodyRef.current
    if (chatBody) chatBody.scrollTop = chatBody.scrollHeight
  }, [tutorialCase.id, step])

  return (
    <div className="chat">
      <div className="chat-head">
        <div>
          <div className="ch">{tutorialCase.channel}</div>
          <div className="ctx">{tutorialCase.context}</div>
        </div>
        <span className="tag">Exemplo</span>
      </div>
      <div
        className="chat-body"
        ref={chatBodyRef}
        role="log"
        aria-live="polite"
        aria-label="Conversa de exemplo"
      >
        {visibleMessages.map((message, index) => (
          <Message key={`${tutorialCase.id}-${index}`} message={message} />
        ))}
      </div>
    </div>
  )
}

interface WorkbenchProps {
  profile: TutorialProfile
  caseId: string
  step: number
  autoRunKey: number
  onCaseChange: (caseId: string) => void
  onStepChange: (step: number) => void
}

function Workbench({ profile, caseId, step, autoRunKey, onCaseChange, onStepChange }: WorkbenchProps) {
  const tutorialCase = profile.cases.find((item) => item.id === caseId) ?? profile.cases[0]
  const lastStep = tutorialCase.steps.length - 1
  const autoRunTimerRef = useRef<number | null>(null)
  const stopAutoRun = useCallback(() => {
    if (autoRunTimerRef.current !== null) {
      window.clearInterval(autoRunTimerRef.current)
      autoRunTimerRef.current = null
    }
  }, [])

  useEffect(() => {
    stopAutoRun()
    if (autoRunKey === 0) return

    let nextStep = 0
    onStepChange(0)
    const timer = window.setInterval(() => {
      nextStep += 1
      onStepChange(nextStep)
      if (nextStep >= lastStep) {
        window.clearInterval(timer)
        if (autoRunTimerRef.current === timer) autoRunTimerRef.current = null
      }
    }, 1800)

    autoRunTimerRef.current = timer
    return () => {
      window.clearInterval(timer)
      if (autoRunTimerRef.current === timer) autoRunTimerRef.current = null
    }
  }, [autoRunKey, lastStep, onStepChange, stopAutoRun, tutorialCase.id])

  function selectStep(nextStep: number) {
    stopAutoRun()
    onStepChange(nextStep)
  }

  return (
    <div className="bench" data-p={profile.id}>
      <div className="col">
        <div>
          <span className="label">Exemplos de uso · {profile.name}</span>
          <div className="cases">
            {profile.cases.map((item) => (
              <button
                key={item.id}
                type="button"
                className="case"
                aria-pressed={item.id === tutorialCase.id}
                onClick={() => onCaseChange(item.id)}
              >
                <b>{item.title}</b>
                <span>{item.summary}</span>
              </button>
            ))}
          </div>
        </div>

        <div>
          <span className="label">Passo a passo</span>
          <ol className="steps">
            {tutorialCase.steps.map((item, index) => {
              const state = index < step ? 'done' : index === step ? 'active' : 'todo'

              return (
                <li key={`${tutorialCase.id}-${item.title}`}>
                  <button
                    type="button"
                    className="step"
                    data-state={state}
                    aria-current={index === step ? 'step' : undefined}
                    onClick={() => selectStep(index)}
                  >
                    <span className="num">{index + 1}</span>
                    <span>
                      <span className="tt">{item.title}</span>
                      {index === step && (
                        <span className="more">
                          <span>{item.description}</span>
                          <span className="onde">{item.location}</span>
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              )
            })}
          </ol>
        </div>

        <div className="ctrl">
          <button type="button" className="btn" disabled={step === 0} onClick={() => selectStep(step - 1)}>
            Passo anterior
          </button>
          <button type="button" className="btn primary" disabled={step === lastStep} onClick={() => selectStep(step + 1)}>
            Próximo passo
          </button>
          <button type="button" className="btn" onClick={() => selectStep(0)}>
            Reiniciar
          </button>
        </div>
      </div>
      <div className="sim"><Simulator tutorialCase={tutorialCase} step={step} /></div>
    </div>
  )
}

function PermissionMatrix() {
  return (
    <div className="scroll-x">
      <table>
        <thead>
          <tr>
            <th scope="col">Ação</th>
            {permissionProfiles.map((profile) => (
              <th scope="col" data-p={profile.id} key={profile.id}>{profile.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {permissions.map(([action, ...values]) => (
            <tr key={action}>
              <td>{action}</td>
              {values.map((value, index) => (
                <td className="c" key={`${action}-${index}`}>
                  <span className="pill" data-v={value}>{permissionLabels[value]}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function VideoGuide() {
  const total = scenes.reduce((sum, scene) => sum + scene.duration, 0)
  const [fallbackScript, setFallbackScript] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  let elapsed = 0
  const starts = scenes.map((scene) => {
    const start = elapsed
    elapsed += scene.duration
    return start
  })

  async function copyScript() {
    const text = buildScript()

    try {
      await navigator.clipboard.writeText(text)
      setCopied(true)
      setFallbackScript(null)
      window.setTimeout(() => setCopied(false), 2000)
    } catch {
      setFallbackScript(text)
    }
  }

  useEffect(() => {
    if (fallbackScript && textareaRef.current) {
      textareaRef.current.focus()
      textareaRef.current.select()
    }
  }, [fallbackScript])

  return (
    <div className="vgrid">
      <div>
        <div className="poster">
          <div className="inner">
            <div className="play" aria-hidden="true" />
            <div className="len">{formatDuration(total)}</div>
            {VIDEO_URL ? (
              <a
                className="btn primary"
                style={{ '--acc': 'var(--ink)', textDecoration: 'none' } as CssVariables}
                href={VIDEO_URL}
                target="_blank"
                rel="noopener noreferrer"
              >
                Assistir ao vídeo
              </a>
            ) : (
              <span className="kicker">Vídeo em produção · roteiro ao lado</span>
            )}
          </div>
        </div>

        <div className="tline" role="img" aria-label="Linha do tempo das cenas">
          {scenes.map((scene, index) => (
            <i
              key={scene.title}
              data-p={scene.profile}
              style={{ flex: `${scene.duration} 1 0` }}
              title={scene.title}
            >
              {index + 1}
            </i>
          ))}
        </div>
        <div className="tl-scale">
          <span>0:00</span>
          <span>{formatDuration(Math.round(total / 2))}</span>
          <span>{formatDuration(total)}</span>
        </div>
        <div className="legend">
          {(['geral', ...profiles.map((item) => item.id)] as const).map((profile) => (
            <span
              key={profile}
              data-p={profile === 'geral' ? undefined : profile}
              style={profile === 'geral' ? { '--acc': 'var(--ink-2)' } as CssVariables : undefined}
            >
              <b />{profileNames[profile]}
            </span>
          ))}
        </div>
        <div className="copybox">
          <div className="ctrl">
            <button type="button" className="btn" onClick={copyScript}>
              {copied ? 'Roteiro copiado' : 'Copiar roteiro completo'}
            </button>
          </div>
          {fallbackScript && (
            <div>
              <span className="label">Selecione e copie o texto abaixo</span>
              <textarea ref={textareaRef} readOnly value={fallbackScript} aria-label="Roteiro completo" />
            </div>
          )}
        </div>
      </div>

      <div className="scenes">
        {scenes.map((scene, index) => (
          <details
            className="scene"
            key={scene.title}
            data-p={scene.profile === 'geral' ? undefined : scene.profile}
            style={scene.profile === 'geral' ? { '--acc': 'var(--ink-2)', '--acc-bg': 'var(--line)' } as CssVariables : undefined}
          >
            <summary>
              <span className="num">{index + 1}</span>
              <b>{scene.title}</b>
              <span className="tm">{formatDuration(starts[index])} · {scene.duration}s</span>
            </summary>
            <div className="body">
              <dl>
                <div><dt>O que gravar</dt><dd>{scene.screen}</dd></div>
                <div><dt>Narração</dt><dd className="speech">{scene.narration}</dd></div>
                <div><dt>Dica de gravação</dt><dd>{scene.tip}</dd></div>
              </dl>
            </div>
          </details>
        ))}
      </div>
    </div>
  )
}

export function TutorialPage() {
  const [profileId, setProfileId] = useState<ProfileId>('publico')
  const profile = profiles.find((item) => item.id === profileId) ?? profiles[0]
  const [caseId, setCaseId] = useState(profile.cases[0].id)
  const [step, setStep] = useState(0)
  const [autoRunKey, setAutoRunKey] = useState(0)
  const exampleCount = profiles.reduce((total, item) => total + item.cases.length, 0)
  const videoDuration = scenes.reduce((total, scene) => total + scene.duration, 0)

  useEffect(() => {
    const hash = window.location.hash.slice(1) as ProfileId
    const hashProfile = profiles.find((item) => item.id === hash)
    if (hashProfile) {
      setProfileId(hashProfile.id)
      setCaseId(hashProfile.cases[0].id)
    }
  }, [])

  function selectProfile(nextProfileId: ProfileId) {
    const nextProfile = profiles.find((item) => item.id === nextProfileId) ?? profiles[0]
    setProfileId(nextProfile.id)
    setCaseId(nextProfile.cases[0].id)
    setStep(0)
    setAutoRunKey((current) => current + 1)
  }

  function selectCase(nextCaseId: string) {
    setCaseId(nextCaseId)
    setStep(0)
    setAutoRunKey((current) => current + 1)
  }

  return (
    <div className="tutorial-page">
      <header className="bar">
        <div className="in">
          <a className="brand-logo" href="/" aria-label="Eureca Chat">
            <span className="brand-eureca">E<span className="brand-u">u<span className="brand-u-accent" aria-hidden="true" /></span>reca</span>
            <span className="brand-chat">Chat</span>
          </a>
          <nav aria-label="Seções">
            <a href="#perfis">Perfis</a>
            <a href="#permissoes">Permissões</a>
            <a href="#video">Vídeo</a>
          </nav>
        </div>
      </header>

      <main>
        <section className="hero">
          <div className="in">
            <div className="kicker">Tutorial de uso · {profiles.length} perfis · {exampleCount} exemplos</div>
            <h1>Eureca Chat <span className="mark">na prática</span></h1>
            <p className="lede">Veja exemplos de perguntas para cada perfil de acesso. Escolha uma consulta e acompanhe como o Eureca Chat organiza a busca e apresenta o resultado.</p>
            <div className="tiles" role="group" aria-label="Escolha um perfil">
              {profiles.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  className="tile"
                  data-p={item.id}
                  aria-pressed={item.id === profileId}
                  onClick={() => selectProfile(item.id)}
                >
                  <span className="who"><span className="dot" />{item.audience}</span>
                  <strong>{item.name}</strong>
                  <span className="d">{item.summary}</span>
                  <span className="n">{item.cases.length} exemplos</span>
                </button>
              ))}
            </div>
          </div>
        </section>

        <section className="block" id="perfis">
          <div className="in">
            <div className="sec-head">
              <span className="kicker">Perfil: {profile.name}</span>
              <h2>Exemplos para quem usa como {profile.name.toLowerCase()}</h2>
              <p>Escolha uma pergunta, avance pelos passos e acompanhe a simulação da consulta ao lado.</p>
            </div>
            <Workbench
              profile={profile}
              caseId={caseId}
              step={step}
              autoRunKey={autoRunKey}
              onCaseChange={selectCase}
              onStepChange={setStep}
            />
          </div>
        </section>

        <section className="block" id="permissoes">
          <div className="in">
            <div className="sec-head">
              <span className="kicker">Comparativo</span>
              <h2>O que cada perfil pode fazer</h2>
              <p>Use a tabela para decidir com qual perfil entrar e o que esperar de cada um.</p>
            </div>
            <PermissionMatrix />
          </div>
        </section>

        <section className="block" id="video">
          <div className="in">
            <div className="sec-head">
              <span className="kicker">Vídeo tutorial geral</span>
              <h2>Roteiro cena a cena</h2>
              <p>{scenes.length} cenas, {formatDuration(videoDuration)}, passando pelos quatro perfis. Abra cada cena para ver o que gravar, a narração e uma dica.</p>
            </div>
            <VideoGuide />
          </div>
        </section>
      </main>

      <footer>
        <div className="in">Exemplos ilustrativos. Nomes de telas, botões e permissões podem variar conforme a configuração da sua escola.</div>
      </footer>
    </div>
  )
}
