"""The words a docs search looks for: a question's own words without stopwords, then what they also mean
(search_terms.yaml, which the kit ships next to lib/). Reads only that kit file."""
from __future__ import annotations

import re

from lib.core import yamlio
from lib.core.ctx import KIT

STOPWORDS = set("how are is was the an what which who does do did of to in on at for and or with by from it this that "
                "can should when where why be use uses used using we our my".split()) | set(
    "que qué como cómo el la los las de del en es un una y o por para con se lo al cuál cual quién quien dónde donde "
    "usa usan usar utiliza utilizan hay".split())
TERMS_FILE = KIT / "lib" / "search_terms.yaml"   # a kit data file, which stays in lib/ (spec §2)
IMPLIED = 0.6                  # a word the question implies (search_terms.yaml) weighs less than one it says


def search_terms() -> dict[str, list[str]]:
    return yamlio.safe_load(TERMS_FILE.read_text(encoding="utf-8")) or {}


def expand(query: str) -> dict[str, float]:
    """term → weight: the question's own words, then what they also mean (search_terms.yaml), followed once. A phrase
    key ("base de datos") stands for its words, so they are not searched one by one."""
    text = " ".join(re.findall(r"\w+", query.lower()))
    words = list(dict.fromkeys(t for t in text.split() if len(t) > 1))
    table = search_terms()
    norm = lambda k: " ".join(re.findall(r"\w+", str(k).lower()))  # noqa: E731
    keys = [k for k in table if re.search(r"(?<!\w)" + re.escape(norm(k)) + r"(?!\w)", text)]
    phrased = {w for k in keys if " " in k for w in k.split()}
    weights = {w: 1.0 for w in words if w not in STOPWORDS and w not in phrased} or \
        {w: 1.0 for w in words if w not in phrased}
    for k in keys:
        for e in table[k]:
            for t in [e, *table.get(e, [])]:
                weights.setdefault(str(t).lower(), IMPLIED)
    return weights
