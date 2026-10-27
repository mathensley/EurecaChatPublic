import type { Metadata } from 'next'
import { TutorialPage } from '@/components/tutorial/tutorial-page'
import './tutorial.css'

export const metadata: Metadata = {
  title: 'Tutorial — Eureca Chat',
  description: 'Guia interativo dos perfis, permissões e principais fluxos do Eureca Chat.',
}

export default function Page() {
  return <TutorialPage />
}
