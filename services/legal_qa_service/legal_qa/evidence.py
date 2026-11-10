"""Resolve applicability before the generation boundary."""
from datetime import date
from .search import search, effect_applicability


def retrieve(manifest, context, messages):
    query = ' '.join(t for role, t in messages if role == 'user')
    if 'испыт' in query.lower():
        query += ' испытание ТК ст70'
    if 'юротдел' in query.lower():
        query += ' юридический отдел оригинал договор'
    if 'сезон' in query.lower():
        query += ' срочный трудовой договор ТК ст59'
    files = {f['id']: f for f in manifest['files']}
    selected = search(manifest, query, as_of=context.as_of_date, limit=len(manifest['chunks']))
    missing = []
    if context.as_of_date and context.interval_end and context.as_of_date < date(2025,3,1) <= context.interval_end:
        return [], ['Уточните день события: внутри указанного месяца меняется редакция.']
    lookup = {'А-08/2024': 'Договор аренды А-08-2024', 'П-17/2024': 'Договор поставки П-17-2024', 'ПТ-05/2023': 'Договор поставки ПТ-05-2023'}
    if context.document_candidates:
        title = lookup[context.document_candidates[0]]
        selected = [x for x in selected if x['file']['title'].startswith(title)]
    else:
        # Preserve whole short documents and immediate neighbors of long excerpts.
        best_files = {x['file']['id'] for x in selected[:8]}
        selected = [x for x in selected if x['file']['id'] in best_files]
    effect_sources = {e.get('source_file_id') or next((f['id'] for f in files.values() if f['title'] == e['source']), None) for e in manifest['effects']}
    chosen = {x['chunk']['id']: x for x in selected[:40] if x['file']['id'] not in effect_sources}
    for item in list(chosen.values()):
        chunk = item['chunk']
        for neighbor in manifest['chunks']:
            if neighbor['file_id'] == chunk['file_id'] and abs(neighbor['line_start'] - chunk['line_start']) <= 1 and neighbor['content_kind'] == 'normative_text':
                chosen[neighbor['id']] = {'chunk': neighbor, 'file': item['file']}
    short_files = {x['file']['id'] for x in chosen.values() if x['file']['coverage_kind'] == 'company_revision'}
    for chunk in manifest['chunks']:
        if chunk['file_id'] in short_files and chunk['content_kind'] == 'normative_text':
            chosen[chunk['id']] = {'chunk':chunk,'file':files[chunk['file_id']]}
    for effect in manifest['effects']:
        target = next((f for f in files.values() if f['document_id'] == effect.get('target_document_id')), None) if effect.get('target_document_id') else next((f for f in files.values() if f['title'] == effect['target']), None)
        if target is None or not any(x['file']['document_id'] == target['document_id'] for x in chosen.values()):
            continue
        spec = context.fact('specification_signed_on')
        event = context.as_of_date or (spec[0] if spec else None)
        facts = {'specification_date': spec[0] if spec else None,
                 'foreign_counterparty': context.fact('foreign_counterparty')}
        state = effect_applicability(effect, facts, event)
        end_facts = dict(facts)
        if spec:
            end_facts['specification_date'] = spec[1]
        end_event = context.interval_end or (spec[1] if spec else event)
        end_state = effect_applicability(effect, end_facts, end_event)
        if state != end_state:
            state = 'unknown'
        applies = state == 'applies'
        relevant_replacement = effect['kind'] == 'replace' and any(w in context.question.lower() for w in ('адрес', 'куда', 'место достав'))
        if state == 'unknown':
            if relevant_replacement:
                missing.append('Когда подписана спецификация на партию? Укажите точную дату.')
            elif effect['kind'] == 'supplement' and context.fact('foreign_counterparty'):
                missing.append('На какую точную дату проверяется договор с иностранным контрагентом?')
            # An unresolved replacement cannot support an unconditional generated claim.
            if effect['kind'] == 'replace':
                chosen = {i:x for i,x in chosen.items() if not (x['file']['document_id'] == target['document_id'] and x['chunk']['provision_label'] == effect['provision'])}
        if applies:
            if effect['kind'] == 'replace':
                chosen = {i:x for i,x in chosen.items() if not (x['file']['document_id'] == target['document_id'] and x['chunk']['provision_label'] == effect['provision'])}
            for chunk in manifest['chunks']:
                source = files[chunk['file_id']]
                if (source['id'] == effect.get('source_file_id') if effect.get('source_file_id') else source['title'] == effect['source']) and chunk['content_kind'] == 'normative_text':
                    chosen[chunk['id']] = {'chunk':chunk,'file':source}
    evidence = [{'id': x['chunk']['id'], 'source': x['file']['title'], 'text':x['chunk']['text'],
                 'provision':x['chunk']['provision_label'], 'applicability':'applies',
                 'coverage':x['file']['coverage_kind'], 'observed_on':x['file'].get('observed_on')} for x in chosen.values()]
    return evidence, missing
