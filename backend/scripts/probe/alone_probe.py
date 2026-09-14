import asyncio, sys
import os

sys.argv = ["x", "0", "memo"]
exec(
    open(os.path.join(os.path.dirname(__file__), "fd_probe.py")).read().split("async def main")[0]
)  # reuse naive prompt patch
from app import prompts, validate
from app.models import RunConfig
from app.llm import LLMRequest
from app.paradigms import get_paradigm
from app.llm import AnthropicClient


async def go():
    client = AnthropicClient()
    cfg = RunConfig(fact_style="memo", seed=0)
    spec = get_paradigm(cfg.paradigm)
    for a in scenario.agents:
        sysm = prompts.system_prompt(scenario, cfg, a, list(scenario.distribution[a.id]), spec)
        for t in range(2):
            resp = await client.complete(
                LLMRequest(
                    system=sysm,
                    user=prompts.alone_vote_message(scenario),
                    model="claude-haiku-4-5",
                    max_tokens=300,
                )
            )
            print(a.id, resp.text.replace("\n", " ")[:260])


asyncio.run(go())
