"""Deterministic text retrieval and reviewed applicability rules."""
from __future__ import annotations

from collections import Counter
from datetime import date
import math
import re


def tokens(text: str) -> list[str]:
    return [re.sub(r'(иями|ами|ого|ему|ение|ения|ется|ются|ать|ить|ый|ий|ая|ой|ом|ов|ам|ах|ы|а|у|е|и)$', '', t) if len(t) > 5 else t for t in re.findall(r'[а-яёa-z0-9]+', text.lower().replace('ё', 'е'))]


def effect_applicability(effect: dict, facts: dict, as_of: date | None) -> str:
    if effect.get('resolution_status') != 'reviewed':
        return 'unknown'
    if as_of is None:
        return 'unknown'
    if as_of < date.fromisoformat(effect['effective_from']):
        return 'does_not_apply'
    if effect.get('effective_to') and as_of >= date.fromisoformat(effect['effective_to']):
        return 'does_not_apply'
    unknown = False
    for condition in effect['conditions']:
        value = facts.get(condition['fact_key'])
        expected = condition['value']
        if value is None:
            unknown = True
            continue
        if isinstance(expected, bool):
            if type(value) is not bool:
                return 'unknown'
        elif condition['fact_key'].endswith('_date'):
            if type(value) is not date:
                return 'unknown'
            expected = date.fromisoformat(expected)
        if condition['operator'] == 'eq':
            matches = value == expected
        elif condition['operator'] == 'gt':
            matches = value > expected
        else:
            return 'unknown'
        if not matches:
            return 'does_not_apply'
    return 'unknown' if unknown else 'applies'


def search(manifest: dict, query: str, *, as_of: date | None = None, limit: int = 10) -> list[dict]:
    """Rank original excerpts; historical statute excerpts are never assumed applicable."""
    files = {f['id']: f for f in manifest['files']}
    candidates = []
    for chunk in manifest['chunks']:
        f = files[chunk['file_id']]
        if chunk['content_kind'] != 'normative_text':
            continue
        if as_of and f['coverage_kind'] == 'statute_excerpt' and as_of.isoformat() != f.get('observed_on'):
            continue
        if f['version_label'] and as_of:
            if f['effective_from'] and as_of < date.fromisoformat(f['effective_from']):
                continue
            if f['effective_to'] and as_of >= date.fromisoformat(f['effective_to']):
                continue
        if f['version_label'] == '2023' and as_of is None:
            continue
        terms = tokens(f['title'] + ' ' + chunk['text'])
        candidates.append((chunk, f, terms))
    query_terms = set(tokens(query))
    if not candidates or not query_terms:
        return []
    counts = Counter(t for _, _, terms in candidates for t in set(terms) if t in query_terms)
    n = len(candidates)
    avg = sum(len(t) for _, _, t in candidates) / n or 1
    result = []
    for chunk, f, terms in candidates:
        frequencies = Counter(terms)
        score = sum(math.log(1 + (n - counts[t] + .5) / (counts[t] + .5)) *
                    frequencies[t] * 2.2 / (frequencies[t] + 1.2 * (.25 + .75 * len(terms) / avg))
                    for t in query_terms if frequencies[t])
        if score:
            result.append({'chunk': chunk, 'file': f, 'score': score})
    return sorted(result, key=lambda x: (-x['score'], x['chunk']['id']))[:max(0, limit)]
