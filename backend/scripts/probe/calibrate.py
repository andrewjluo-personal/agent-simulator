import asyncio
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(__file__))
from flat_pool import FLAT  # noqa: E402

from app.llm import AnthropicClient, LLMRequest  # noqa: E402

BRIEF = (
    "You are on a hiring panel for a senior backend engineer on a payments team "
    "choosing between two candidates, John and Sally."
)
SYSTEM = f"""{BRIEF}
You will be shown ONE observation from an interviewer's notes. Rate how much that single
observation, on its own, should move a reasonable panel's recommendation.
Scale: 1 = trivial/minor, 2 = a small point, 3 = a solid point, 4 = a major factor,
5 = decisive on its own.
Respond with JSON only: {{"rating": 1..5, "direction": "john"|"sally"|"neutral"}}"""

N = 5
ONLY = set(sys.argv[1].split(",")) if len(sys.argv) > 1 else set()


async def rate(client: AnthropicClient, text: str, sem: asyncio.Semaphore) -> list[int]:
    out: list[int] = []
    for _ in range(N):
        async with sem:
            resp = await client.complete(
                LLMRequest(system=SYSTEM, user=text, model="claude-haiku-4-5", max_tokens=60)
            )
        m = re.search(r"\{.*\}", resp.text, re.S)
        out.append(int(json.loads(m.group(0))["rating"]) if m else -1)
    return out


async def main() -> None:
    client = AnthropicClient()
    sem = asyncio.Semaphore(6)
    facts = [f for f in FLAT.facts if not ONLY or f.id in ONLY]
    results = await asyncio.gather(*(rate(client, f.memo_text or f.text, sem) for f in facts))
    shared = set(FLAT.distribution["dana"]) & set(FLAT.distribution["tom"])
    rows = []
    for f, r in zip(facts, results, strict=True):
        kind = "shared" if f.id in shared else "unique"
        rows.append((kind, f.id, f.valence, f.weight, sum(r) / len(r), f.memo_text))
    rows.sort(key=lambda x: (x[0], -x[4]))
    for kind, fid, val, w, avg, txt in rows:
        print(f"{kind:6} {fid:4} {val:3} w={w} rated={avg:.2f}  {txt}")
    for kind in ("shared", "unique"):
        xs = [r[4] for r in rows if r[0] == kind]
        if xs:
            print(f"{kind} mean rating {sum(xs) / len(xs):.2f}")


asyncio.run(main())
