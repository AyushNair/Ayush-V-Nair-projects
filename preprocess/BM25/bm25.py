"""Small Okapi BM25 implementation used by the retrieval notebooks.

The previous implementation imported ``gensim.summarization.bm25``, which was
removed in Gensim 4. The notebooks pass document strings, so tokenize them as
words instead of letting the old API treat every character as a term.
"""

import re
import math

try:
    import numpy as np
except ImportError:  # Keep the retrieval implementation smoke-testable by itself.
    np = None

try:
    from tqdm import tqdm
except ImportError:
    tqdm = lambda values: values


_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_ENGLISH_TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z0-9]+)?")


def _tokenize(text):
    if not isinstance(text, str):
        return [str(token).lower() for token in text]

    text = text.lower()
    if _CJK_RE.search(text):
        try:
            import jieba
        except ImportError as exc:
            raise ImportError(
                "Chinese BM25 text requires jieba; install it with `pip install jieba`."
            ) from exc
        return [token.strip() for token in jieba.cut(text) if token.strip()]
    return _ENGLISH_TOKEN_RE.findall(text)


class BM25Okapi:
    """Okapi BM25 scorer with the standard k1=1.5 and b=0.75 defaults."""

    def __init__(self, corpus, k1=1.5, b=0.75, epsilon=0.25):
        if not corpus:
            raise ValueError("BM25 corpus must contain at least one document")

        self.corpus = [_tokenize(document) for document in corpus]
        self.k1 = k1
        self.b = b
        self.epsilon = epsilon
        self.corpus_size = len(self.corpus)
        self.doc_len = [len(document) for document in self.corpus]
        self.avgdl = sum(self.doc_len) / self.corpus_size or 1.0

        document_frequency = {}
        self.doc_freqs = []
        for document in self.corpus:
            frequencies = {}
            for term in document:
                frequencies[term] = frequencies.get(term, 0) + 1
            self.doc_freqs.append(frequencies)
            for term in frequencies:
                document_frequency[term] = document_frequency.get(term, 0) + 1

        self.idf = {
            term: math.log(self.corpus_size - frequency + 0.5)
            - math.log(frequency + 0.5)
            for term, frequency in document_frequency.items()
        }
        average_idf = sum(self.idf.values()) / max(len(self.idf), 1)
        floor = self.epsilon * average_idf
        self.idf = {term: max(value, floor) for term, value in self.idf.items()}

    def get_scores(self, query):
        scores = [0.0] * self.corpus_size
        for term in _tokenize(query):
            idf = self.idf.get(term)
            if idf is None:
                continue
            for index, frequencies in enumerate(self.doc_freqs):
                frequency = frequencies.get(term, 0)
                if frequency:
                    denominator = frequency + self.k1 * (
                        1 - self.b + self.b * self.doc_len[index] / self.avgdl
                    )
                    scores[index] += idf * frequency * (self.k1 + 1) / denominator
        return np.asarray(scores, dtype=np.float64) if np is not None else scores


def get_total_scores(queries, corpus, bm25_model=None):
    if bm25_model is None:
        print('Init BM25 model...')
        bm25_model = init_model(corpus)

    bm25_scores = ([[0.0] * len(corpus) for _ in queries] if np is None
                   else np.zeros((len(queries), len(corpus)), dtype=np.float64))
    for index, query in enumerate(tqdm(queries)):
        bm25_scores[index] = bm25_model.get_scores(query)

    shape = bm25_scores.shape if np is not None else (len(bm25_scores), len(corpus))
    print('bm25_scores: ', shape)
    return bm25_scores


def init_model(corpus):
    return BM25Okapi(corpus)


def get_a_query_scores(query, bm25_model):
    return bm25_model.get_scores(query)
