import re
from flat_pool import FLAT

SWAP = {
    "John": "Sally",
    "Sally": "John",
    "John's": "Sally's",
    "Sally's": "John's",
    "his": "her",
    "her": "his",
    "he": "she",
    "she": "he",
    "him": "her",
    "He": "She",
    "She": "He",
}
_pat = re.compile(r"\b(" + "|".join(re.escape(k) for k in SWAP) + r")\b")


def swap(s: str) -> str:
    return _pat.sub(lambda m: SWAP[m.group(1)], s)


MIRROR = FLAT.model_copy(deep=True)
MIRROR.id = "hiring-panel-flat-mirror"
for f in MIRROR.facts:
    f.candidate_id = "sally" if f.candidate_id == "john" else "john"
    f.text = swap(f.text)
    if f.memo_text:
        f.memo_text = swap(f.memo_text)
