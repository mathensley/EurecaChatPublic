import type { Metadata } from 'next'
import Link from 'next/link'
import { FileText, ShieldCheck, Users } from 'lucide-react'
import { InfoPageLayout } from '@/components/info/info-page-layout'

export const metadata: Metadata = {
  title: 'Termos e Privacidade — EurecaChat',
  description: 'Termos de serviço e política de privacidade do EurecaChat.',
}

export default function TermsPage() {
  return (
    <InfoPageLayout>
      <section className="mx-auto max-w-4xl text-center">
        <span className="inline-flex items-center gap-2 rounded-full bg-brand-accent/10 px-3 py-1.5 text-xs font-semibold text-brand">
          <ShieldCheck className="size-3.5 text-brand-accent" />
          Transparência e responsabilidade
        </span>
        <h1 className="mt-5 text-balance text-3xl font-semibold tracking-tight text-brand sm:text-5xl">
          Termos e privacidade
        </h1>
        <p className="mx-auto mt-5 max-w-2xl text-pretty text-base leading-7 text-muted-foreground sm:text-lg">
          Saiba como o EurecaChat deve ser utilizado e como tratamos as informações necessárias
          para o funcionamento da plataforma.
        </p>
      </section>

      <div className="mx-auto mt-10 grid max-w-5xl gap-6 sm:mt-14 lg:grid-cols-2 lg:items-start">
        <article className="rounded-2xl border border-border bg-card p-6 shadow-card sm:p-8">
          <div className="grid size-11 place-items-center rounded-xl bg-brand text-brand-accent dark:bg-brand-deep">
            <FileText className="size-5" />
          </div>
          <h2 className="mt-5 text-2xl font-semibold tracking-tight text-foreground">
            Termos de Serviço
          </h2>
          <div className="mt-4 space-y-4 text-sm leading-7 text-muted-foreground sm:text-base">
            <p>
              Este projeto foi desenvolvido por estudantes de graduação em Ciência da Computação
              da Universidade Federal de Campina Grande (UFCG), como parte de pesquisas acadêmicas
              voltadas à inovação tecnológica por meio do Kunumi Lab.
            </p>
            <p>
              Nosso objetivo é oferecer uma experiência confiável, transparente e de qualidade,
              sempre prezando pelo respeito, pela ética e pela responsabilidade no uso da
              plataforma.
            </p>
            <p>
              Ao utilizar nossos serviços, você concorda em colaborar para um ambiente seguro e
              construtivo, respeitando as diretrizes estabelecidas e contribuindo para o
              aprimoramento contínuo do projeto.
            </p>
            <p>
              Agradecemos seu interesse e sua confiança em nosso trabalho acadêmico e tecnológico.
            </p>
          </div>
          <Link
            href="/sobre/"
            className="mt-6 inline-flex items-center gap-2 rounded-xl bg-secondary px-4 py-2.5 text-sm font-semibold text-secondary-foreground transition-colors hover:bg-muted"
          >
            <Users className="size-4" />
            Conheça nossa equipe
          </Link>
        </article>

        <article className="rounded-2xl border border-border bg-card p-6 shadow-card sm:p-8">
          <div className="grid size-11 place-items-center rounded-xl bg-brand-accent/15 text-brand-accent">
            <ShieldCheck className="size-5" />
          </div>
          <h2 className="mt-5 text-2xl font-semibold tracking-tight text-foreground">
            Política de Privacidade
          </h2>
          <div className="mt-4 space-y-4 text-sm leading-7 text-muted-foreground sm:text-base">
            <p>
              Esta Política de Privacidade descreve como coletamos, utilizamos e protegemos as
              informações dos usuários que acessam nossa plataforma. Nosso compromisso é garantir
              transparência, segurança e respeito à privacidade.
            </p>
            <p>
              Podemos coletar dados fornecidos, como logs de erros e outras informações necessárias
              para o funcionamento adequado do sistema. Esses dados são utilizados exclusivamente
              para melhorar a experiência do usuário e para fins acadêmicos ou administrativos
              relacionados ao projeto.
            </p>
            <p>
              Adotamos medidas técnicas e organizacionais para proteger suas informações contra
              acesso não autorizado ou uso indevido. Apenas pessoas autorizadas têm acesso aos
              dados armazenados, que são tratados com responsabilidade e confidencialidade.
            </p>
            <p>
              Ao utilizar a plataforma, você concorda com estes termos. Caso tenha dúvidas sobre
              como seus dados são tratados, entre em contato conosco para esclarecimentos.
            </p>
          </div>
        </article>
      </div>
    </InfoPageLayout>
  )
}
