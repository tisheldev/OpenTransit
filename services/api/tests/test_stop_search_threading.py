"""Stop search runs in worker threads: the per-generation index is built once.

Hot-path rewrites must return exactly what the original definitions returned.
"""

import gc
import random
import threading
import time

import opentransit.stop_search as stop_search_module


class _Reference:
    """Hashable reference double; every instance is its own generation."""

    def stop_search_candidates(self):
        return []


def test_concurrent_first_searches_build_one_index(monkeypatch):
    builds = []
    real_index = stop_search_module._SearchIndex

    def slow_index(rows, localities=None):
        builds.append(threading.get_ident())
        time.sleep(0.2)
        return real_index(rows, localities)

    monkeypatch.setattr(stop_search_module, "_SearchIndex", slow_index)
    reference = _Reference()
    results = []
    barrier = threading.Barrier(4)

    def search():
        barrier.wait()
        results.append(stop_search_module._search_index(reference))

    threads = [threading.Thread(target=search) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(builds) == 1
    assert len(results) == 4
    assert all(result is results[0] for result in results)


def _reference_coverage(tokens, labels):
    """The original word-by-word definition: tokens prefix-matched by one label's words."""
    best = 0
    for label in labels:
        words = label.split()
        best = max(best, sum(any(word.startswith(token) for word in words) for token in tokens))
    return best


def test_coverage_matches_the_word_prefix_definition_on_normalized_labels():
    rng = random.Random(20261001)
    alphabet = "abhstv תחנרכבאי"
    vocabulary = ["".join(rng.choice(alphabet.replace(" ", "")) for _ in range(rng.randint(1, 6)))]
    vocabulary += [
        "".join(rng.choice(alphabet.replace(" ", "")) for _ in range(rng.randint(1, 6)))
        for _ in range(40)
    ]
    raw = ["Tel-Aviv  Center", "תחנת רכבת/סבידור", "Ben Gurion Airport", "", "a  a", "ab"]
    raw += [" ".join(rng.choices(vocabulary, k=rng.randint(0, 5))) for _ in range(300)]
    # Production coverage labels are normalized and folded: single-space separated.
    labels = [stop_search_module.normalize_label(value) for value in raw]
    labels += [stop_search_module.fold_transliteration(label) for label in labels]
    for _ in range(3000):
        query = " ".join(rng.choices(vocabulary, k=rng.randint(1, 5)))
        tokens = list(dict.fromkeys(stop_search_module.normalize_label(query).split()))
        sample = rng.sample(labels, rng.randint(0, 8))
        assert stop_search_module._coverage(tokens, sample) == _reference_coverage(
            tokens, sample
        ), (tokens, sample)


def test_index_lives_and_dies_with_its_reference():
    references = [_Reference() for _ in range(3)]
    indexes = [stop_search_module._search_index(reference) for reference in references]
    # Each live generation keeps exactly its own index; nothing is evicted early.
    assert stop_search_module._search_index(references[0]) is indexes[0]
    assert stop_search_module._search_index(references[2]) is indexes[2]
    released = references.pop(0)
    del released
    gc.collect()
    assert len(stop_search_module._INDEXES) == 2
