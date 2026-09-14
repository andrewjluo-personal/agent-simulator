import asyncio, sys, json

sys.path.insert(0, ".")
from app import prompts, validate
from app.llm import AnthropicClient, LLMRequest
from app.models import RunConfig
from app.paradigms import get_paradigm
from app.samples import SAMPLES_BY_ID
from app.validator import REVIEWER

sid = sys.argv[1]
agent_id = sys.argv[2] if len(sys.argv) > 2 else None
n = int(sys.argv[3]) if len(sys.argv) > 3 else 6
s = SAMPLES_BY_ID[sid]
agent = REVIEWER if agent_id is None else next(a for a in s.agents if a.id == agent_id)
hand = [f.id for f in s.facts] if agent_id is None else s.distribution[agent_id]
system = prompts.system_prompt(
    s, RunConfig(scenario_id=sid), agent, hand, get_paradigm("free_discussion")
)
user = prompts.alone_vote_message(s)


async def main():
    c = AnthropicClient()
    rs = await asyncio.gather(
        *(
            c.complete(
                LLMRequest(system=system, user=user, model="claude-haiku-4-5", max_tokens=200)
            )
            for _ in range(n)
        )
    )
    for r in rs:
        d = validate.parse_json_object(r.text) or {}
        print(d.get("vote"), d.get("confidence"), "|", d.get("reason"))


asyncio.run(main())
