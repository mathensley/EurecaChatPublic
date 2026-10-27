import type { Metadata } from 'next'
import { Code2, ExternalLink, Mail, Sparkles, Users } from 'lucide-react'
import { InfoPageLayout } from '@/components/info/info-page-layout'

export const metadata: Metadata = {
  title: 'Sobre — EurecaChat',
  description: 'Conheça o projeto EurecaChat e sua equipe.',
}

const TEAM = [
  {
    name: 'Levi de Lima Pereira Júnior',
    email: 'levi.pereira.junior@ccc.ufcg.edu.br',
    github: 'https://github.com/levijunior21',
    avatar: 'https://avatars.githubusercontent.com/u/104105849?v=4',
    description:
      'Estudante de Ciência da Computação pela Universidade Federal de Campina Grande. No projeto Kunumi Lab — Agents4Good, atua nas áreas de Inteligência Artificial, Agentes Inteligentes, Ciência de Dados, backend e frontend.',
  },
  {
    name: 'Matheus Hensley de Figueiredo e Silva',
    email: 'matheus.figueiredo.silva@ccc.ufcg.edu.br',
    github: 'https://github.com/mathensley',
    avatar: 'https://avatars.githubusercontent.com/u/25806885?v=4',
    description:
      'Mestrando em Ciência da Computação pela Universidade Federal de Campina Grande. Trabalha em pesquisa e desenvolvimento no projeto Kunumi Lab — Agents4Good, com Inteligência Artificial, Agentes Inteligentes, avaliações, dados e backend.',
  },
  {
    name: 'Beatriz de Sousa Meneses',
    email: 'beatriz.souza.meneses@ccc.ufcg.edu.br',
    github: 'https://github.com/beatrizSM3',
    avatar: 'https://avatars.githubusercontent.com/u/87208381?v=4',
    description:
      'Estudante de Ciência da Computação pela Universidade Federal de Campina Grande. No projeto Kunumi Lab — Agents4Good (Eureca), trabalha com agentes inteligentes e aplicações de IA voltadas para impacto real e construção prática de soluções.',
  },
  {
    name: 'Anderson Breno Santos Silva',
    email: 'anderson.breno.santos.silva@ccc.ufcg.edu.br',
    github: 'https://github.com/AndersonBreno1',
    avatar: 'https://avatars.githubusercontent.com/u/214906578?v=4',
    description:
      'Estudante de Ciência da Computação pela Universidade Federal de Campina Grande. Trabalha em pesquisa e desenvolvimento de aplicações agênticas no laboratório Agents4Good / Kunumi Lab, atuando nas áreas de Inteligência Artificial, Análise e Avaliação de Dados.',
  },
]

export default function AboutPage() {
  return (
    <InfoPageLayout>
      <section className="mx-auto max-w-4xl text-center">
        <span className="inline-flex items-center gap-2 rounded-full bg-brand-accent/10 px-3 py-1.5 text-xs font-semibold text-brand">
          <Sparkles className="size-3.5 text-brand-accent" />
          Sobre o projeto
        </span>
        <h1 className="mt-5 text-balance text-3xl font-semibold tracking-tight text-brand sm:text-5xl">
          Informação acadêmica com a ajuda de agentes inteligentes
        </h1>
        <p className="mx-auto mt-5 max-w-3xl text-pretty text-base leading-7 text-muted-foreground sm:text-lg sm:leading-8">
          O EurecaChat é um projeto do Agents4Good criado para responder perguntas sobre a
          Universidade Federal de Campina Grande usando dados reais das APIs oficiais da UFCG.
        </p>
      </section>

      <section className="mt-10 rounded-2xl border border-border bg-card p-6 shadow-card sm:mt-14 sm:p-8">
        <div className="flex flex-col gap-6 sm:flex-row sm:items-start sm:justify-between">
          <div className="max-w-3xl">
            <div className="mb-4 grid size-11 place-items-center rounded-xl bg-brand text-brand-accent dark:bg-brand-deep">
              <Sparkles className="size-5" />
            </div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">
              Sobre o EurecaChat
            </h2>
            <p className="mt-3 text-pretty leading-7 text-muted-foreground">
              O sistema funciona como um chatbot capaz de responder perguntas relacionadas a
              campi, calendários, setores, docentes, cursos, currículos, disciplinas, turmas,
              estágios e estudantes, oferecendo respostas precisas e contextualizadas.
            </p>
          </div>

          <a
            href="https://github.com/Agents4Good/EurecaAI"
            target="_blank"
            rel="noreferrer"
            className="inline-flex shrink-0 items-center justify-center gap-2 rounded-xl bg-primary px-4 py-2.5 text-sm font-semibold text-primary-foreground shadow-soft transition-all hover:bg-brand-deep hover:shadow-card"
          >
            <Code2 className="size-4" />
            Ver no GitHub
            <ExternalLink className="size-3.5 opacity-70" />
          </a>
        </div>
      </section>

      <section className="mt-12">
        <div className="mb-6 flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-brand-accent/10 text-brand-accent">
            <Users className="size-5" />
          </div>
          <div>
            <h2 className="text-2xl font-semibold tracking-tight text-foreground">Integrantes</h2>
            <p className="mt-1 text-sm text-muted-foreground">
              Conheça as pessoas que constroem o projeto.
            </p>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-3">
          {TEAM.map((member) => (
            <article
              key={member.email}
              className="flex flex-col rounded-2xl border border-border bg-card p-6 shadow-soft transition-transform duration-200 hover:-translate-y-1 hover:shadow-card"
            >
              <a
                href={member.github}
                target="_blank"
                rel="noreferrer"
                aria-label={`GitHub de ${member.name}`}
                className="size-20 overflow-hidden rounded-full ring-4 ring-brand-accent/15 transition-shadow hover:ring-brand-accent/35"
              >
                <img
                  src={member.avatar}
                  alt=""
                  width={80}
                  height={80}
                  loading="lazy"
                  referrerPolicy="no-referrer"
                  className="size-full object-cover"
                />
              </a>

              <h3 className="mt-5 text-lg font-semibold leading-snug text-brand">{member.name}</h3>
              <a
                href={`mailto:${member.email}`}
                className="mt-2 inline-flex items-start gap-2 break-all text-xs leading-5 text-muted-foreground transition-colors hover:text-brand-accent"
              >
                <Mail className="mt-0.5 size-3.5 shrink-0" />
                {member.email}
              </a>
              <p className="mt-4 flex-1 text-sm leading-6 text-muted-foreground">
                {member.description}
              </p>
              <a
                href={member.github}
                target="_blank"
                rel="noreferrer"
                className="mt-5 inline-flex items-center gap-2 text-sm font-medium text-brand transition-colors hover:text-brand-accent"
              >
                <Code2 className="size-4" />
                Perfil no GitHub
              </a>
            </article>
          ))}
        </div>
      </section>
    </InfoPageLayout>
  )
}
