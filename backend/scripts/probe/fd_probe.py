import asyncio
import os
import sys

from app import orchestrator
from app.llm import AnthropicClient

sys.path.insert(0, "scripts")
from validate_scenario import CountingClient
from app.models import RunConfig
from app.samples import SAMPLES_BY_ID
from app.store import MemoryStore

RUNS = int(sys.argv[1])
STYLE = sys.argv[2] if len(sys.argv) > 2 else "memo"
sys.path.insert(0, os.path.dirname(__file__))
from flat_pool import FLAT
from mirror_pool import MIRROR

scenario = MIRROR if STYLE == "mirror" else FLAT

from app import prompts
from app import orchestrator as _orch


def naive_system_prompt(scenario, cfg, agent, hand_fact_ids, paradigm):
    notes = prompts._memo_lines(scenario, cfg, agent, hand_fact_ids)
    schema = f'{{"sentences": string[], "current_lean": "{prompts._lean_options(scenario, None, None)}", "confidence": 0..1}}'
    return f"""You are {agent.name}, {agent.role} on the panel. Style: {agent.style}.
The panel has {len(scenario.agents)} interviewers and must recommend exactly one candidate:
{prompts._candidate_lines(scenario, None, None)}

{scenario.brief}
The panel will discuss and then each of you will give a private recommendation.

Here is some information available to you:
{notes}

Keep your response concise, just one or two sentences.

Run nonce: {cfg.seed}

Respond with JSON only:
{schema}"""


prompts.system_prompt = naive_system_prompt
_orch.prompts.system_prompt = naive_system_prompt


async def one(client: CountingClient, seed: int, sem: asyncio.Semaphore) -> bool:
    store = MemoryStore()
    store.upsert_scenario(scenario)
    run = orchestrator.new_run(
        store,
        RunConfig(
            scenario_id=scenario.id, paradigm="free_discussion", seed=seed, fact_style="memo"
        ),
        provider="anthropic",
    )
    store.create_run(run)
    async with sem:
        final = await orchestrator.run_to_completion(store, client, run.id)
    m = final.metrics
    out_dir = os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, f"fd_{STYLE}_seed{seed}.txt"), "w") as fh:
        for t in final.turns:
            fh.write(
                f"R{t.round + 1} {t.agent_id}: {' '.join(t.sentences)}  [{','.join(t.cited)}]\n"
            )
        for v in final.votes:
            fh.write(f"vote r{v.round} {v.agent_id}: {v.choice} -- {v.reason}\n")
    shared = set(scenario.distribution[scenario.agents[0].id]) & set(
        scenario.distribution[scenario.agents[1].id]
    )
    from app import truth

    spoken = truth.verdict(scenario, shared | {c for t in final.turns for c in t.cited})
    cited = sorted({c for t in final.turns for c in t.cited if c not in shared})
    print(
        f"seed {seed}: spoken_tally_verdict={spoken} majority={m.majority_candidate_id if m else None} tally={m.final_tally if m else None} "
        f"decisive_surfaced={m.decisive_surfaced_count if m else None}/{m.decisive_total if m else None} "
        f"votes={[(v.agent_id, v.choice) for v in final.votes]} unique_cited={cited}",
        flush=True,
    )
    return bool(m and m.correct)


async def main() -> None:
    client = CountingClient(AnthropicClient())
    sem = asyncio.Semaphore(3)
    res = await asyncio.gather(
        *(one(client, s, sem) for s in range(int(sys.argv[3]) if len(sys.argv) > 3 else 0, RUNS))
    )
    print(
        f"free-discussion PROBE naive-prompt ({STYLE}) correct rate: {sum(res) / RUNS:.2f} over {RUNS} runs"
    )
    print(f"tokens: {client.input_tokens} in / {client.output_tokens} out")


asyncio.run(main())
