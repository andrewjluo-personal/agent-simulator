import asyncio
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
scenario = SAMPLES_BY_ID["hiring-panel-v1"]


async def one(client: CountingClient, seed: int, sem: asyncio.Semaphore) -> bool:
    store = MemoryStore()
    store.upsert_scenario(scenario)
    run = orchestrator.new_run(
        store,
        RunConfig(scenario_id=scenario.id, paradigm="free_discussion", seed=seed, fact_style=STYLE),
        provider="anthropic",
    )
    store.create_run(run)
    async with sem:
        final = await orchestrator.run_to_completion(store, client, run.id)
    m = final.metrics
    shared = set(scenario.distribution[scenario.agents[0].id]) & set(
        scenario.distribution[scenario.agents[1].id]
    )
    cited = sorted({c for t in final.turns for c in t.cited if c not in shared})
    print(
        f"seed {seed}: majority={m.majority_candidate_id if m else None} tally={m.final_tally if m else None} "
        f"decisive_surfaced={m.decisive_surfaced_count if m else None}/{m.decisive_total if m else None} "
        f"votes={[(v.agent_id, v.choice) for v in final.votes]} unique_cited={cited}",
        flush=True,
    )
    return bool(m and m.correct)


async def main() -> None:
    client = CountingClient(AnthropicClient())
    sem = asyncio.Semaphore(3)
    res = await asyncio.gather(*(one(client, s, sem) for s in range(RUNS)))
    print(f"free-discussion ({STYLE}) correct rate: {sum(res) / RUNS:.2f} over {RUNS} runs")
    print(f"tokens: {client.input_tokens} in / {client.output_tokens} out")


asyncio.run(main())
