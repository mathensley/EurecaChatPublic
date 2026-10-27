export type ProfileId =
  | 'publico'
  | 'aluno'
  | 'professor'
  | 'servidor'

export type ParticipantRole = ProfileId | 'assistente'

export interface PollOption {
  label: string
  votes: number
}

export interface PollData {
  question: string
  options: PollOption[]
  selectedOption: number
}

export interface TutorialMessage {
  at: number
  role: ParticipantRole | 'sistema'
  name?: string
  text?: string
  time?: string
  attachment?: { file: string; size: string }
  poll?: PollData
}

export interface TutorialStep {
  title: string
  location: string
  description: string
}

export interface TutorialCase {
  id: string
  title: string
  summary: string
  channel: string
  context: string
  steps: TutorialStep[]
  messages: TutorialMessage[]
}

export interface TutorialProfile {
  id: ProfileId
  name: string
  audience: string
  summary: string
  cases: TutorialCase[]
}

export type PermissionValue = 'sim' | 'nao' | 'leitura'

export interface TutorialScene {
  profile: ProfileId | 'geral'
  title: string
  duration: number
  screen: string
  narration: string
  tip: string
}

interface QuestionExample {
  id: string
  title: string
  question: string
  result: string
}

const system = (at: number, text: string): TutorialMessage => ({ at, role: 'sistema', text })

const message = (
  at: number,
  role: ParticipantRole,
  name: string,
  text: string,
  time: string,
): TutorialMessage => ({ at, role, name, text, time })

function createCases(
  profileId: ProfileId,
  profileName: string,
  examples: QuestionExample[],
): TutorialCase[] {
  return examples.map((example) => ({
    id: example.id,
    title: example.title,
    summary: `“${example.question}”`,
    channel: 'Eureca Chat',
    context: `Consulta para o perfil ${profileName}`,
    steps: [
      { title: 'Faça a pergunta', location: 'Campo de mensagem', description: example.question },
      {
        title: 'Acompanhe a consulta',
        location: 'Indicador de processamento',
        description: 'O Eureca Chat identifica os dados necessários e consulta as fontes disponíveis para o seu perfil.',
      },
      { title: 'Analise a resposta', location: 'Resposta do Eureca Chat', description: example.result },
    ],
    messages: [
      message(1, profileId, profileName, example.question, '10:00'),
      system(2, 'Consultando os dados disponíveis para este perfil…'),
      message(3, 'assistente', 'Eureca Chat', example.result, '10:01'),
    ],
  }))
}

export const profiles: TutorialProfile[] = [
  {
    id: 'publico',
    name: 'Anônimo',
    audience: 'Visitante sem vínculo com a UFCG',
    summary: 'Consulte informações públicas sobre campi, cursos e formas de ingresso.',
    cases: createCases('publico', 'Anônimo', [
      {
        id: 'localizacao-campi',
        title: 'Localização dos campi',
        question: 'Quais são os campi da UFCG e em quais cidades eles ficam?',
        result: 'A resposta apresenta os campi da UFCG e as respectivas cidades, usando dados institucionais públicos.',
      },
      {
        id: 'cursos-oferecidos',
        title: 'Cursos oferecidos',
        question: 'Quais cursos de graduação a UFCG oferece atualmente?',
        result: 'A resposta lista os cursos de graduação disponíveis e pode organizá-los por campus.',
      },
      {
        id: 'oferta-curso-vagas',
        title: 'Oferta de curso e vagas',
        question: 'A UFCG oferece o curso de Ciência da Computação? Se sim, quantas vagas são disponibilizadas por semestre?',
        result: 'A resposta confirma a oferta do curso e informa a quantidade de vagas encontrada para cada período de ingresso.',
      },
    ]),
  },
  {
    id: 'aluno',
    name: 'Aluno',
    audience: 'Estudante da UFCG',
    summary: 'Consulte disciplinas, desempenho acadêmico e organize o próximo período.',
    cases: createCases('aluno', 'Aluno', [
      {
        id: 'taxa-aprovacao-professor',
        title: 'Taxa de aprovação de professor',
        question: 'Qual é a taxa de aprovação dos alunos nas disciplinas ministradas pelo professor Leandro Balby?',
        result: 'A resposta calcula a taxa de aprovação nas ofertas encontradas e apresenta o período considerado na análise.',
      },
      {
        id: 'disciplinas-curso',
        title: 'Disciplinas do curso',
        question: 'Quais disciplinas fazem parte da grade curricular de Ciência da Computação?',
        result: 'A resposta organiza os componentes curriculares do curso e identifica disciplinas obrigatórias e optativas quando esses dados estão disponíveis.',
      },
      {
        id: 'organizacao-horarios',
        title: 'Organização de horários',
        question: 'Estou planejando meu próximo período. Você pode organizar os horários das disciplinas ofertadas no período 2026.2 e montar uma grade semanal sem conflitos de horário?',
        result: 'A resposta cruza os horários das turmas e propõe uma grade semanal sem sobreposição, indicando eventuais alternativas.',
      },
    ]),
  },
  {
    id: 'professor',
    name: 'Professor',
    audience: 'Docente da UFCG',
    summary: 'Acompanhe matrículas e analise a preparação e o desempenho das suas turmas.',
    cases: createCases('professor', 'Professor', [
      {
        id: 'alunos-matriculados',
        title: 'Alunos matriculados',
        question: 'Quantos alunos estão matriculados nas disciplinas que estou ministrando neste período?',
        result: 'A resposta identifica as turmas do professor no período atual e apresenta a quantidade de matriculados em cada uma.',
      },
      {
        id: 'conhecimento-previo',
        title: 'Conhecimento prévio dos alunos',
        question: 'Com base nas notas dos meus alunos nas disciplinas anteriores de cálculo, como você avalia a preparação deles para cursar Cálculo II?',
        result: 'A resposta resume o desempenho anterior da turma e aponta níveis de preparação e conteúdos que podem precisar de revisão.',
      },
      {
        id: 'analise-desempenho',
        title: 'Análise de desempenho',
        question: 'Analise o desempenho dos meus alunos em Álgebra Linear no período 2026.1, destacando as médias, as taxas de aprovação e os principais pontos de dificuldade.',
        result: 'A resposta apresenta indicadores agregados da turma, compara resultados e destaca padrões que merecem atenção pedagógica.',
      },
    ]),
  },
  {
    id: 'servidor',
    name: 'Servidor',
    audience: 'Servidor da UFCG',
    summary: 'Consulte dados administrativos e indicadores acadêmicos de cursos, turmas e da universidade.',
    cases: createCases('servidor', 'Servidor', [
      {
        id: 'total-alunos-curso',
        title: 'Total de alunos do curso',
        question: 'Quantos alunos estão atualmente matriculados no curso de Ciência da Computação?',
        result: 'A resposta conta os vínculos acadêmicos ativos do curso e informa o critério usado para considerar um aluno matriculado.',
      },
      {
        id: 'matriculas-disciplina',
        title: 'Matrículas por disciplina',
        question: 'Quantos alunos estão matriculados em cada disciplina ofertada neste período?',
        result: 'A resposta agrupa as matrículas por disciplina e apresenta os totais do período acadêmico atual.',
      },
      {
        id: 'matriculas-curso-periodo',
        title: 'Matrículas por curso e período',
        question: 'No período passado, quantos alunos de cada curso estavam matriculados na disciplina de Cálculo I?',
        result: 'A resposta filtra o período anterior e distribui as matrículas de Cálculo I por curso de origem.',
      },
      {
        id: 'distribuicao-sexo',
        title: 'Distribuição por sexo',
        question: 'Quantos estudantes homens e mulheres estão matriculados atualmente no curso de Ciência da Computação?',
        result: 'A resposta apresenta a distribuição agregada dos estudantes ativos conforme os dados cadastrais disponíveis.',
      },
      {
        id: 'estudantes-pcd',
        title: 'Estudantes com deficiência (PCD)',
        question: 'Quantos estudantes com deficiência estão matriculados no curso e como estão distribuídos entre as turmas?',
        result: 'A resposta informa quantitativos agregados e a distribuição entre turmas, preservando a privacidade dos estudantes.',
      },
      {
        id: 'distribuicao-turma',
        title: 'Distribuição por turma',
        question: 'Quantos estudantes estão matriculados em cada turma de Teoria da Computação neste período?',
        result: 'A resposta localiza as turmas ofertadas no período e apresenta a quantidade de matriculados em cada uma.',
      },
      {
        id: 'distribuicao-universidade',
        title: 'Distribuição por sexo na universidade',
        question: 'Qual é a distribuição atual dos estudantes da UFCG por sexo, considerando todos os campi?',
        result: 'A resposta consolida os estudantes ativos de todos os campi e apresenta a distribuição agregada.',
      },
      {
        id: 'evolucao-estudantes',
        title: 'Evolução do número de estudantes',
        question: 'Como o número de estudantes matriculados na UFCG evoluiu nos últimos dez anos? Apresente os dados por ano em um gráfico.',
        result: 'A resposta organiza a série histórica anual e gera um gráfico para mostrar a evolução das matrículas.',
      },
      {
        id: 'alunos-evasao-curso',
        title: 'Número de alunos e evasão por curso',
        question: 'Quais cursos da UFCG possuem o maior número de estudantes matriculados e quais apresentam as maiores taxas de evasão? Compare os dados entre os últimos períodos.',
        result: 'A resposta compara cursos e períodos, separando volume de estudantes e taxa de evasão para evitar interpretações equivocadas.',
      },
    ]),
  },
]

export const permissionProfiles = profiles.map(({ id, name }) => ({ id, name }))

export const permissions: [string, ...PermissionValue[]][] = [
  ['Consultar informações institucionais públicas', 'sim', 'sim', 'sim', 'sim'],
  ['Planejar a própria grade acadêmica', 'nao', 'sim', 'nao', 'nao'],
  ['Analisar as próprias turmas', 'nao', 'nao', 'sim', 'leitura'],
  ['Consultar matrículas por disciplina e curso', 'nao', 'nao', 'leitura', 'sim'],
  ['Analisar indicadores do curso', 'nao', 'nao', 'leitura', 'sim'],
  ['Analisar indicadores de toda a universidade', 'leitura', 'leitura', 'leitura', 'sim'],
]

export const permissionLabels: Record<PermissionValue, string> = {
  sim: 'Sim',
  nao: 'Não',
  leitura: 'Agregado',
}

export const scenes: TutorialScene[] = [
  { profile: 'geral', title: 'Abertura', duration: 15, screen: 'Logo do Eureca Chat e apresentação do objetivo do tutorial.', narration: 'Conheça exemplos de perguntas para cada perfil de acesso ao Eureca Chat.', tip: 'Apresente rapidamente o propósito da ferramenta.' },
  { profile: 'geral', title: 'Escolha do perfil', duration: 25, screen: 'Tela do tutorial com os quatro perfis disponíveis.', narration: 'Escolha o perfil que representa sua forma de usar os dados acadêmicos.', tip: 'Mostre os quatro cartões antes de selecionar um deles.' },
  { profile: 'publico', title: 'Anônimo', duration: 30, screen: 'Perguntas sobre campi, cursos e vagas.', narration: 'Usuários anônimos podem consultar informações institucionais e conhecer as oportunidades oferecidas pela UFCG.', tip: 'Use uma consulta que não exija autenticação.' },
  { profile: 'aluno', title: 'Aluno', duration: 35, screen: 'Perguntas sobre currículo, professores e organização de horários.', narration: 'Alunos podem planejar o período e explorar informações acadêmicas relevantes para sua trajetória.', tip: 'Demonstre uma grade semanal sem conflitos.' },
  { profile: 'professor', title: 'Professor', duration: 35, screen: 'Perguntas sobre matrículas e desempenho das turmas.', narration: 'Professores podem acompanhar suas turmas e apoiar decisões pedagógicas com indicadores agregados.', tip: 'Não mostre dados pessoais de estudantes.' },
  { profile: 'servidor', title: 'Servidor', duration: 45, screen: 'Consultas administrativas e indicadores de cursos, turmas e universidade.', narration: 'Servidores podem consultar quantitativos e indicadores agregados para apoiar rotinas acadêmicas e administrativas.', tip: 'Mostre filtros de período, curso e campus.' },
  { profile: 'geral', title: 'Fechamento', duration: 15, screen: 'Retorno à seleção de perfis.', narration: 'Escolha um exemplo, adapte a pergunta ao seu contexto e converse com o Eureca Chat.', tip: 'Deixe o endereço do sistema visível.' },
]

export const profileNames: Record<TutorialScene['profile'], string> = {
  geral: 'Geral',
  publico: 'Anônimo',
  aluno: 'Aluno',
  professor: 'Professor',
  servidor: 'Servidor',
}

export const roleLabels: Record<ParticipantRole, string> = {
  publico: 'Anônimo',
  aluno: 'Aluno',
  professor: 'Professor',
  servidor: 'Servidor',
  assistente: 'Assistente',
}
