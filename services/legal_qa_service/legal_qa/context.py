"""User-grounded temporal facts; calendar precision is retained."""
from dataclasses import dataclass
from datetime import date
import calendar
import re
from decimal import Decimal

MONTHS = 'январ феврал март апрел ма июн июл август сентябр октябр ноябр декабр'.split()


@dataclass(frozen=True)
class Fact:
    role: str
    value: object
    precision: str
    message: int
    span: str


@dataclass(frozen=True)
class QueryContext:
    question: str
    document_candidates: tuple[str, ...]
    as_of_date: date | None
    date_conflict: bool
    facts: tuple[Fact, ...] = ()
    interval_end: date | None = None

    @property
    def resolved_facts(self):
        """Current user premises; superseded facts remain only in the provenance log."""
        latest = {fact.role: fact for fact in self.facts}
        return tuple(fact for fact in self.facts if
                     (fact.role == 'amount' and fact.message == latest['amount'].message)
                     or (fact.role != 'amount' and fact is latest[fact.role]))

    def fact(self, role):
        return next((f.value for f in reversed(self.facts) if f.role == role), None)



MONEY_PATTERN = re.compile(r'(?<![\d.,])(\d[\d \u00a0]*(?:[.,]\d+)?)\s*(млн|миллион\w*|тыс\.?|тысяч\w*|рубл\w*)', re.I)


def monetary_mentions(text):
    for match in MONEY_PATTERN.finditer(text):
        value = Decimal(re.sub(r'[ \u00a0]', '', match[1]).replace(',', '.'))
        unit = match[2].lower()
        if unit.startswith(('млн', 'миллион')):
            value *= 1000000
        elif unit.startswith(('тыс', 'тысяч')):
            value *= 1000
        yield match, value

def parse_context(messages, as_of_date=None):
    if not messages or messages[-1][0] != 'user' or not messages[-1][1].strip():
        raise ValueError('History must end with a nonempty user message')
    facts, candidates, conflicts = [], (), set()
    for index, (role, text) in enumerate(messages):
        if role not in ('user', 'assistant') or not text.strip():
            raise ValueError('Invalid history')
        if role != 'user':
            continue
        text = text.lower().replace('ё', 'е')
        found = []
        for pattern, reference in [(r'пт[-‑–—]05[/\-]2023|альфа[-‑–—]трейдинг', 'ПТ-05/2023'),
                                   (r'(?<![а-я])п[-‑–—]17[/\-]2024|альфа[-‑–—]трейд(?![а-я])', 'П-17/2024'),
                                   (r'а[-‑–—]08[/\-]2024|северн\w*\s+склад', 'А-08/2024')]:
            if re.search(pattern, text):
                found.append(reference)
        if found:
            candidates = tuple(found)
            facts.append(Fact('document_reference', candidates, 'explicit', index, text))
        elif not candidates and re.search(r'альф[аыойе]+', text):
            candidates = ('П-17/2024', 'ПТ-05/2023')
        date_pattern = r'\d{4}-\d{2}-\d{2}|\d{1,2}\.\d{1,2}\.\d{4}|(?:\d{1,2}\s+)?(?:январ\w*|феврал\w*|март\w*|апрел\w*|ма[йея]|июн\w*|июл\w*|август\w*|сентябр\w*|октябр\w*|ноябр\w*|декабр\w*)\s+\d{4}'
        local = {}
        correction = bool(re.search(r'\bнет\b|исправ|на самом|уточн|теперь|\bподтвержда\w*|\bверн\w*|\bправильн\w*|\bименно\b', text))
        for match in re.finditer(date_pattern, text):
            span = match[0]
            try:
                if '-' in span:
                    start = end = date.fromisoformat(span)
                elif '.' in span:
                    d, m, y = map(int, span.split('.')); start = end = date(y, m, d)
                else:
                    parts = span.split(); y = int(parts[-1]); word = parts[-2]
                    m = next(i + 1 for i, name in enumerate(MONTHS) if word.startswith(name))
                    start = date(y, m, int(parts[0]) if parts[0].isdigit() else 1)
                    end = start if parts[0].isdigit() else date(y, m, calendar.monthrange(y, m)[1])
            except (ValueError, StopIteration):
                continue
            prefix = text[max(0, match.start()-65):match.start()]
            # Nearest named event determines the date role.
            markers = [(m.start(), r) for pattern, r in [(r'спецификац', 'specification_signed_on'), (r'достав|поставк', 'delivery_on'), (r'договор|заключ', 'contract_signed_on')]
                       for m in re.finditer(pattern, prefix)]
            fact_role = max(markers)[1] if markers else 'legal_as_of'
            follows_question = index > 0 and messages[index-1][0] == 'assistant' and '?' in messages[index-1][1]
            if not markers and follows_question:
                if 'спецификац' in messages[index-1][1].lower():
                    fact_role = 'specification_signed_on'
                elif len(conflicts) == 1:
                    fact_role = next(iter(conflicts))
            if not markers and correction and len(conflicts) == 1:
                fact_role = next(iter(conflicts))
            if len(span.split()) == 2 and not re.match(r'\d', span):
                fact_role = 'contract_signed_on' if 'договор' in text else fact_role
            local.setdefault(fact_role, []).append((start, end))
            facts.append(Fact(fact_role, (start, end), 'day' if start == end else 'month', index, span))
        for fact_role, values in local.items():
            prior = next((f for f in reversed(facts) if f.role == fact_role and f.message != index), None)
            low = max(v[0] for v in values)
            high = min(v[1] for v in values)
            answering_conflict = index > 0 and messages[index-1][0] == 'assistant' and '?' in messages[index-1][1] and fact_role in conflicts
            if low > high:
                conflicts.add(fact_role)
            elif correction or answering_conflict:
                conflicts.discard(fact_role)
            elif prior and (prior.value[1] < low or high < prior.value[0]):
                conflicts.add(fact_role)
        for amount, value in monetary_mentions(text):
            facts.append(Fact('amount', value, 'explicit', index, amount[0]))
        if re.search(r'иностранн\w*\s+контрагент', text):
            facts.append(Fact('foreign_counterparty', not bool(re.search(r'не\s+иностранн', text)), 'explicit', index, text))
    legal = next((f.value for f in reversed(facts) if f.role == 'legal_as_of'), None)
    contract = next((f.value for f in reversed(facts) if f.role == 'contract_signed_on'), None)
    if as_of_date:
        if legal and not legal[0] <= as_of_date <= legal[1]:
            conflicts.add('legal_as_of')
        legal = (as_of_date, as_of_date)
        facts.append(Fact('legal_as_of', legal, 'day', -1, 'as_of_date'))
    interval = legal or contract
    return QueryContext(messages[-1][1], candidates, interval[0] if interval else None, bool(conflicts), tuple(facts), interval[1] if interval else None)
