"""BM25 keyword search with Indonesian stemming.

Indonesian words carry affixes ('pemutusan', 'diputuskan', 'memutus' all share 'putus'), so exact
keyword matching misses a lot. Sastrawi strips the affixes. Stemming is slow per word, so each
distinct word is stemmed once and cached.
"""

import re
from collections.abc import Callable
from functools import lru_cache

import numpy as np
from rank_bm25 import BM25Okapi
from Sastrawi.Stemmer.StemmerFactory import StemmerFactory

from pasalkini.corpus import Chunk

TOKEN = re.compile(r"[a-z0-9]+")
# Words so common in legal text that they carry no signal for ranking.
STOPWORDS = frozenset(
    """yang dan di ke dari dalam pada untuk dengan atau oleh sebagai adalah ini itu tersebut
    dimaksud sebagaimana ayat pasal huruf angka tidak dapat akan telah bagi atas serta secara
    apabila jika maka setiap para suatu lebih paling lain dengan""".split()
)

_stemmer = StemmerFactory().create_stemmer()


@lru_cache(maxsize=200_000)
def stem(word: str) -> str:
    return _stemmer.stem(word) if len(word) > 3 and not word.isdigit() else word


def tokenize(text: str) -> list[str]:
    return [stem(w) for w in TOKEN.findall(text.lower()) if w not in STOPWORDS]


def keyword_title(title: str) -> str:
    """'UU 13/2003 Pasal 59 (berlaku 25 Maret 2003 s.d. …)' → 'UU 13/2003 Pasal 59'.

    The validity dates would otherwise match month and year words in questions such as
    'di-PHK bulan Maret 2019'.
    """
    return re.sub(r"\s*\((berlaku|diucapkan)[^)]*\)\s*$", "", title)


class BM25Index:
    def __init__(self, chunks: list[Chunk], with_titles: bool = True) -> None:
        self.chunks = chunks
        documents = [
            tokenize(f"{keyword_title(c.title)}\n{c.text}" if with_titles else c.text)
            for c in chunks
        ]
        self.bm25 = BM25Okapi(documents)

    def search(
        self, query: str, k: int, allowed: Callable[[Chunk], bool] | None = None
    ) -> list[tuple[Chunk, float]]:
        scores = np.asarray(self.bm25.get_scores(tokenize(query)), dtype=np.float64)
        if allowed is not None:
            mask = np.array([allowed(c) for c in self.chunks])
            scores = np.where(mask, scores, -np.inf)
        order = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in order if np.isfinite(scores[i])]
