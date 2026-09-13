// Client-side mirror of backend/app/truth.py: weighted verdict arithmetic over fact sets.
import type { Fact, Scenario } from './types'

export const UNDECIDED = 'undecided'

export function factsById(scenario: Scenario): Map<string, Fact> {
  return new Map(scenario.facts.map((f) => [f.id, f]))
}

/** Candidate a fact argues for: pro → its candidate; con → every other candidate (we return the "favored" side for 2-candidate tint). */
export function favoredCandidate(fact: Fact, scenario: Scenario): string | null {
  if (fact.valence === 'pro') return fact.candidateId
  const others = scenario.candidates.filter((c) => c.id !== fact.candidateId)
  return others.length === 1 ? others[0].id : null
}

export function scores(scenario: Scenario, factIds: Iterable<string>): Record<string, number> {
  const byId = factsById(scenario)
  const out: Record<string, number> = {}
  for (const c of scenario.candidates) out[c.id] = 0
  for (const id of factIds) {
    const f = byId.get(id)
    if (!f) continue
    out[f.candidateId] += f.valence === 'pro' ? f.weight : -f.weight
  }
  return out
}

export function verdict(scenario: Scenario, factIds: Iterable<string>): string {
  const s = scores(scenario, factIds)
  const ranked = scenario.candidates.map((c) => [c.id, s[c.id]] as const).sort((a, b) => b[1] - a[1])
  if (ranked.length === 0 || (ranked.length > 1 && ranked[0][1] === ranked[1][1])) return UNDECIDED
  return ranked[0][0]
}

export function holders(scenario: Scenario, factId: string): string[] {
  return scenario.agents.filter((a) => (scenario.distribution[a.id] ?? []).includes(factId)).map((a) => a.id)
}

export function sharedFactIds(scenario: Scenario): Set<string> {
  const n = scenario.agents.length
  return new Set(scenario.facts.filter((f) => holders(scenario, f.id).length === n && n > 0).map((f) => f.id))
}

export function uniqueFactIds(scenario: Scenario): Set<string> {
  return new Set(scenario.facts.filter((f) => holders(scenario, f.id).length === 1).map((f) => f.id))
}

export function heldFactIds(scenario: Scenario): Set<string> {
  return new Set(Object.values(scenario.distribution).flat())
}

export const pooledVerdict = (s: Scenario) => verdict(s, heldFactIds(s))
export const sharedOnlyVerdict = (s: Scenario) => verdict(s, sharedFactIds(s))

export function aloneVotes(scenario: Scenario): Record<string, string> {
  const out: Record<string, string> = {}
  for (const a of scenario.agents) out[a.id] = verdict(scenario, scenario.distribution[a.id] ?? [])
  return out
}

/** Unique facts that argue for the pooled-correct candidate. */
export function decisiveFactIds(scenario: Scenario): Set<string> {
  const correct = pooledVerdict(scenario)
  const unique = uniqueFactIds(scenario)
  return new Set(
    scenario.facts
      .filter((f) => unique.has(f.id))
      .filter((f) => (f.valence === 'pro' ? f.candidateId === correct : f.candidateId !== correct))
      .map((f) => f.id),
  )
}

export function tally(choices: Iterable<string>, scenario: Scenario): Record<string, number> {
  const out: Record<string, number> = {}
  for (const c of scenario.candidates) out[c.id] = 0
  for (const ch of choices) out[ch] = (out[ch] ?? 0) + 1
  return out
}

export function candidateName(scenario: Scenario, id: string): string {
  return scenario.candidates.find((c) => c.id === id)?.name ?? id
}

export function tallyText(t: Record<string, number>, scenario: Scenario): string {
  return scenario.candidates.map((c) => t[c.id] ?? 0).join('–')
}
