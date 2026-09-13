// Wire contract shared with backend/app/models.py (camelCase on the wire).

export type Valence = 'pro' | 'con'
export type Paradigm = 'free_discussion' | 'share_first'
export type TurnOrder = 'clockwise' | 'random'
export type TieBreak = 'none' | 'runoff' | 'chair'
export type RunStatus = 'queued' | 'running' | 'done' | 'error'
export type LlmProvider = 'anthropic' | 'fake'

export type Candidate = { id: string; name: string; blurb: string }
export type Fact = { id: string; candidateId: string; valence: Valence; weight: number; text: string }
export type AgentPersona = { id: string; name: string; role: string; style: string }

export type ValidationResult = {
  aloneWrongRate: Record<string, number>
  pooledRightRate: number
  trials: number
  date: string
  passed: boolean
  freeDiscussionRate?: number | null
  freeDiscussionRuns?: number
}

export type Scenario = {
  id: string
  title: string
  brief: string
  isSample: boolean
  candidates: Candidate[]
  facts: Fact[]
  agents: AgentPersona[]
  distribution: Record<string, string[]>
  validation?: Record<string, ValidationResult> | null
}

export type RunConfig = {
  scenarioId: string
  paradigm: Paradigm
  rounds: number
  sentencesPerTurn: number
  turnOrder: TurnOrder
  tieBreak: TieBreak
  model: string
  seed: number
}

export type Turn = {
  seq: number
  round: number
  agentId: string
  sentences: string[]
  cited: string[]
  hallucinated: string[]
  lean: string // candidateId | 'undecided'
  confidence: number
  latencyMs?: number | null
  inputTokens?: number | null
  outputTokens?: number | null
  heardBefore?: string[]
}

export type Vote = {
  round: number
  agentId: string
  choice: string // candidateId | 'undecided'
  confidence: number
  reason?: string | null
  saidLean: string // latest public turn lean at ballot time
}

export type Metrics = {
  correct: boolean
  correctCandidateId: string
  majorityCandidateId: string
  finalTally: Record<string, number>
  decisiveSurfaced: number
  decisiveTotal: number
  decisiveSurfacedCount: number
  agreement: number
  hallucinationCount: number
  voteTrajectory: Record<string, number>[]
  firstSurfaced?: Record<string, FirstSurfaced>
  unspokenDecisive?: string[]
  holders?: Record<string, string[]>
  mentions?: { shared: number; unique: number }
  voteRounds?: number[] // round index per *_ByRound entry; -1 = pre-discussion ballot
  agreementByRound?: number[]
  accuracyByRound?: number[]
  tokensTotal?: { input: number; output: number }
  llmCalls?: number
  latencyTotalMs?: number
}

export type FirstSurfaced = { seq: number; round: number; agentId: string }

export type RunState = {
  id: string
  scenarioId: string
  scenario: Scenario
  config: RunConfig
  status: RunStatus
  currentRound: number
  isDemo: boolean
  batchId?: string | null
  llmProvider: LlmProvider
  error?: string | null
  metrics?: Metrics | null
  engineVersion?: string
  turns: Turn[]
  votes: Vote[]
  createdAt: string
}

export type RunSummary = Omit<RunState, 'turns' | 'votes' | 'scenario'>

export type BatchState = { id: string; runs: RunSummary[] }

export type DemoSnapshot = { scenario: Scenario; runs: RunSummary[]; engineVersion?: string }
