'use client'

import { useEffect, useRef, useState } from 'react'
import { Paperclip, Mic, ArrowUp, LoaderCircle, Square, X } from 'lucide-react'
import { cn } from '@/lib/utils'
import { audioService } from '@/services'

interface ChatInputProps {
  onSend: (text: string, files: File[]) => void | Promise<void>
  disabled?: boolean
  focusRequest?: number
}

const MAX_FILES = 3
const MAX_FILE_SIZE = 5 * 1024 * 1024

export function ChatInput({ onSend, disabled, focusRequest = 0 }: ChatInputProps) {
  const [value, setValue] = useState('')
  const [files, setFiles] = useState<File[]>([])
  const [fileError, setFileError] = useState<string | null>(null)
  const [audioError, setAudioError] = useState<string | null>(null)
  const [isRecording, setIsRecording] = useState(false)
  const [isTranscribing, setIsTranscribing] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const mediaStreamRef = useRef<MediaStream | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const discardRecordingRef = useRef(false)
  const canSubmit = Boolean(value.trim()) && !disabled && !isRecording && !isTranscribing
  const inputDisabled = disabled || isRecording || isTranscribing

  useEffect(() => {
    if (!inputDisabled) textareaRef.current?.focus()
  }, [inputDisabled, focusRequest])

  useEffect(() => {
    discardRecordingRef.current = false
    return () => {
      discardRecordingRef.current = true
      const recorder = mediaRecorderRef.current
      if (recorder?.state === 'recording') recorder.stop()
      mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    }
  }, [])

  function submit() {
    if (!canSubmit) return
    void onSend(value.trim(), files)
    setValue('')
    setFiles([])
    if (textareaRef.current) textareaRef.current.style.height = 'auto'
  }

  function selectFiles(event: React.ChangeEvent<HTMLInputElement>) {
    const selected = Array.from(event.target.files ?? [])
    event.target.value = ''
    if (files.length + selected.length > MAX_FILES) {
      setFileError(`Envie no máximo ${MAX_FILES} arquivos.`)
      return
    }
    if (selected.some((file) => file.size > MAX_FILE_SIZE)) {
      setFileError('Cada arquivo deve ter no máximo 5 MB.')
      return
    }
    setFileError(null)
    setFiles((current) => [...current, ...selected])
  }

  function releaseMicrophone() {
    mediaStreamRef.current?.getTracks().forEach((track) => track.stop())
    mediaStreamRef.current = null
    mediaRecorderRef.current = null
  }

  async function startRecording() {
    if (disabled || isTranscribing || isRecording) return
    setAudioError(null)

    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === 'undefined') {
      setAudioError('A gravação de voz não é compatível com este navegador.')
      return
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      const recorder = new MediaRecorder(stream)
      discardRecordingRef.current = false
      mediaStreamRef.current = stream
      mediaRecorderRef.current = recorder
      audioChunksRef.current = []

      recorder.addEventListener('dataavailable', (event) => {
        if (event.data.size > 0) audioChunksRef.current.push(event.data)
      })

      recorder.addEventListener('stop', () => {
        const audio = new Blob(audioChunksRef.current, {
          type: recorder.mimeType || 'audio/webm',
        })
        audioChunksRef.current = []
        releaseMicrophone()
        if (discardRecordingRef.current) return
        void transcribeRecording(audio)
      }, { once: true })

      recorder.start()
      setIsRecording(true)
    } catch (cause) {
      releaseMicrophone()
      const denied = cause instanceof DOMException && cause.name === 'NotAllowedError'
      setAudioError(
        denied
          ? 'Permita o acesso ao microfone para usar a entrada por voz.'
          : 'Não foi possível acessar o microfone.',
      )
    }
  }

  function stopRecording() {
    const recorder = mediaRecorderRef.current
    if (!recorder || recorder.state !== 'recording') return
    setIsRecording(false)
    setIsTranscribing(true)
    recorder.stop()
  }

  async function transcribeRecording(audio: Blob) {
    if (audio.size === 0) {
      setAudioError('Nenhum áudio foi capturado. Tente novamente.')
      setIsTranscribing(false)
      return
    }

    try {
      const extension = audio.type.includes('ogg')
        ? 'ogg'
        : audio.type.includes('mp4')
          ? 'm4a'
          : 'webm'
      const response = await audioService.transcribe(audio, `recording.${extension}`)
      const transcription = response.transcription?.trim()
      if (!transcription) throw new Error('Transcrição vazia')

      setValue('')
      setFiles([])
      await onSend(transcription, files)
    } catch (cause) {
      setAudioError(
        cause instanceof Error && cause.message
          ? cause.message
          : 'Não foi possível transcrever o áudio.',
      )
    } finally {
      setIsTranscribing(false)
    }
  }

  return (
    <div className="mx-auto w-full max-w-3xl">
      {files.length > 0 && (
        <div className="mb-2 flex flex-wrap gap-2">
          {files.map((file, index) => (
            <span key={`${file.name}-${index}`} className="inline-flex items-center gap-1 rounded-lg bg-muted px-2 py-1 text-xs">
              {file.name}
              <button type="button" onClick={() => setFiles((current) => current.filter((_, itemIndex) => itemIndex !== index))} aria-label={`Remover ${file.name}`}>
                <X className="size-3" />
              </button>
            </span>
          ))}
        </div>
      )}
      {(fileError || audioError) && (
        <p className="mb-2 text-xs text-destructive">{fileError || audioError}</p>
      )}

      <div className={cn(
        'flex items-end gap-2 rounded-2xl border bg-card p-2 shadow-card transition-all duration-200',
        'border-border focus-within:border-brand-accent/70 focus-within:shadow-float focus-within:ring-4 focus-within:ring-brand-accent/10',
      )}>
        <input ref={fileInputRef} type="file" multiple accept=".pdf,.png,.jpg,.jpeg,.csv,.txt,.json,.xlsx" className="hidden" onChange={selectFiles} />
        <button type="button" onClick={() => fileInputRef.current?.click()} disabled={inputDisabled} aria-label="Anexar arquivo" title="Anexar PDF, imagem, CSV ou documento" className="grid size-10 shrink-0 place-items-center rounded-xl text-muted-foreground transition-colors hover:bg-muted hover:text-brand disabled:opacity-40">
          <Paperclip className="size-5" />
        </button>

        <textarea
          ref={textareaRef}
          rows={1}
          value={value}
          disabled={inputDisabled}
          onChange={(event) => {
            setValue(event.target.value)
            event.target.style.height = 'auto'
            event.target.style.height = `${Math.min(event.target.scrollHeight, 200)}px`
          }}
          onKeyDown={(event) => {
            if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing && event.keyCode !== 229) {
              event.preventDefault()
              submit()
            }
          }}
          placeholder="Pergunte sobre a UFCG..."
          className="max-h-[200px] flex-1 resize-none bg-transparent px-1 py-2.5 text-[0.95rem] leading-relaxed text-foreground outline-none placeholder:text-muted-foreground disabled:opacity-60"
        />

        <button
          type="button"
          onClick={isRecording ? stopRecording : () => void startRecording()}
          disabled={disabled || isTranscribing}
          aria-label={isRecording ? 'Parar gravação' : isTranscribing ? 'Transcrevendo áudio' : 'Gravar mensagem de voz'}
          title={isRecording ? 'Parar e enviar' : isTranscribing ? 'Transcrevendo…' : 'Gravar mensagem de voz'}
          className={cn(
            'grid size-10 shrink-0 place-items-center rounded-xl transition-all duration-200 disabled:cursor-not-allowed disabled:opacity-50',
            isRecording
              ? 'animate-pulse bg-brand-accent text-white shadow-soft'
              : 'text-muted-foreground hover:bg-muted hover:text-brand',
          )}
        >
          {isTranscribing
            ? <LoaderCircle className="size-5 animate-spin" />
            : isRecording
              ? <Square className="size-4 fill-current" />
              : <Mic className="size-5" />}
        </button>
        <button type="button" onClick={submit} disabled={!canSubmit} aria-label="Enviar mensagem" className={cn(
          'grid size-10 shrink-0 place-items-center rounded-xl transition-all duration-200',
          canSubmit ? 'bg-primary text-primary-foreground shadow-soft hover:bg-brand-deep active:scale-95' : 'cursor-not-allowed bg-muted text-muted-foreground opacity-60',
        )}>
          <ArrowUp className="size-5" strokeWidth={2.5} />
        </button>
      </div>
      {(isRecording || isTranscribing) && (
        <p role="status" className="mt-2 text-center text-xs font-medium text-brand">
          {isRecording ? 'Gravando… clique novamente para enviar.' : 'Transcrevendo áudio…'}
        </p>
      )}
      <p className="mt-2.5 text-center text-xs text-muted-foreground">O EurecaChat é um agente de IA e pode cometer erros. Confira informações importantes.</p>
    </div>
  )
}
