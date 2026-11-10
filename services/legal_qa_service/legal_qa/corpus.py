"""Immutable, content-addressed corpus snapshots."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tempfile
import unicodedata
import zipfile

MAX_FILE = 2 * 1024 * 1024
MAX_TOTAL = 32 * 1024 * 1024
SCHEMA = 2
# Rules are valid only for these independently reviewed source bytes.
REVIEWED = {
    'Договор аренды А-08-2024 Северный Склад': 'ea312cfd0c2727eb321a8a764512ec977725e93e08131048fb77af6bd9700b29',
    'Договор поставки П-17-2024 Альфа-Трейд': 'b5df5ca3e2b746cbbaa1757e77697f28ad87d015c66d44fade45a10aae754e25',
    'Договор поставки ПТ-05-2023 Альфа-Трейдинг': '8c2171e4c1bfe5a915a5d3cd7fdfb64ead0866858bf7914f8b84c67be618530d',
    'Доп соглашение 1 к договору П-17-2024': 'f37f50f7bcb0900854230903be263bebdea60b3cae4be93ee9ed7ec02e4a380a',
    'Письмо комплаенс-службы К-12 от 15.04.2025': '9d256e900a22e14c01f341d4172dc2923aa8696b0639f5ab8eed5a6ff5884449',
    'Регламент согласования договоров ред 2023 (утратил силу)': '27dcb53da4f654f50bdf233aa00b3e006075a85086f10dac57800473e499575d',
    'Регламент согласования договоров ред 2025': '6b899e69657be2b5357d37619cbe31e151bf8ab02f838603a4d55b4257f00e44',
    'Служебная записка об архиве договоров': 'a90d426b390e892ba490fde5c5bb85367ed71232a48442728a8e1363232a27ee',
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def stable(*parts: object) -> str:
    return digest(json.dumps(parts, ensure_ascii=False, separators=(',', ':')).encode())[:32]


def _safe_name(name: str) -> bool:
    p = PurePosixPath(name)
    return bool(name and not p.is_absolute() and len(p.parts) == 1 and p.name == name
                and name not in ('.', '..') and '\\' not in name and '\x00' not in name
                and not any(ord(c) < 32 for c in name))


def build_snapshot(archive: Path) -> tuple[dict, dict[str, bytes]]:
    files, chunks, originals = [], [], {}
    seen, total = set(), 0
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            if info.is_dir() or info.filename.startswith('__MACOSX/'):
                continue
            name = info.filename
            if not _safe_name(name) or not name.lower().endswith('.txt'):
                raise ValueError(f'Unsafe or unsupported archive member: {name!r}')
            canonical_name = unicodedata.normalize('NFC', name).casefold()
            if canonical_name in seen:
                raise ValueError('Duplicate or ambiguous source name')
            seen.add(canonical_name)
            total += info.file_size
            if info.file_size > MAX_FILE or total > MAX_TOTAL:
                raise ValueError('Corpus size limit exceeded')
            raw = z.read(info)
            text = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
            source_hash = digest(raw)
            file_id = stable('file', name, source_hash)
            company = name.startswith('документы компании__')
            title = name.split('__', 1)[-1][:-4]
            reviewed = company and REVIEWED.get(title) == source_hash
            if company and not reviewed:
                raise ValueError(f'Corporate source requires metadata review: {name}')
            doc_id = stable('document', 'регламент' if title.startswith('Регламент согласования') else title)
            label = '2023' if 'ред 2023' in title else '2025' if 'ред 2025' in title else None
            files.append({'id': file_id, 'name': name, 'sha256': source_hash, 'title': title,
                          'document_id': doc_id, 'version_id': stable('version', file_id),
                          'version_label': label, 'media_type': 'text/plain; charset=utf-8',
                          'coverage_kind': 'company_revision' if company else 'statute_excerpt',
                          'validity_status': 'confirmed' if label else 'unresolved' if company else 'observed_only',
                          'effective_from': '2023-01-10' if label == '2023' else '2025-03-01' if label == '2025' else None,
                          'effective_to': '2025-03-01' if label == '2023' else None,
                          'observed_on': None if company else '2026-10-10'})
            originals[file_id] = raw
            # Line-based spans preserve exact Python offsets and original line numbers.
            offset = 0
            in_article = company
            for line_no, line in enumerate(text.splitlines(keepends=True), 1):
                content = line.rstrip('\n')
                if not company and re.match(r'^Статья\s+\d', content):
                    in_article = True
                kind = 'normative_text' if in_article else 'editorial_note'
                if 'ВНИМАНИЕ ДЛЯ ИИ-АССИСТЕНТА' in content:
                    kind = 'editorial_note'
                if not company and re.search(r'^Федеральн.{0,15}закон|^Информация об изменениях|^См\. |^ГАРАНТ|^.*утратил.{0,3}сил|^.* - Федеральный закон|^.*изменен|^.*изменён', content, re.I):
                    kind = 'future_notice' if re.search(r'2027|2028|будущ', content) else 'editorial_note'
                provision = re.match(r'^\s*(\d+\.\d+)\.', content)
                for pos in range(0, len(content), 1500):
                    end = min(pos + 1500, len(content))
                    start_abs, end_abs = offset + pos, offset + end
                    chunks.append({'id': stable('chunk', file_id, start_abs, end_abs), 'file_id': file_id,
                                   'version_id': stable('version', file_id), 'start': start_abs, 'end': end_abs,
                                   'line_start': line_no, 'line_end': line_no, 'text': content[pos:end],
                                   'provision_label': provision.group(1) if provision else None,
                                   'content_kind': kind})
                offset += len(line)
    if not files:
        raise ValueError('Empty corpus')
    files.sort(key=lambda x: x['name'])
    chunks.sort(key=lambda x: (x['file_id'], x['start']))
    effects = [
        {'source': 'Доп соглашение 1 к договору П-17-2024', 'target': 'Договор поставки П-17-2024 Альфа-Трейд',
         'provision': '3.2', 'kind': 'replace', 'effective_from': '2024-09-03',
         'conditions': [{'fact_key': 'specification_date', 'operator': 'gt', 'value': '2024-10-01'}], 'resolution_status': 'reviewed'},
        {'source': 'Письмо комплаенс-службы К-12 от 15.04.2025', 'target': 'Регламент согласования договоров ред 2025',
         'provision': '5.4', 'kind': 'supplement', 'effective_from': '2025-04-21',
         'conditions': [{'fact_key': 'foreign_counterparty', 'operator': 'eq', 'value': True}], 'resolution_status': 'reviewed'},
    ]
    titles = {f['title'] for f in files}
    effects = [e for e in effects if e['source'] in titles and e['target'] in titles]
    for effect in effects:
        source = next(f for f in files if f['title'] == effect['source'])
        target = next(f for f in files if f['title'] == effect['target'])
        effect['source_file_id'] = source['id']
        effect['target_document_id'] = target['document_id']
        effect['target_provision_ids'] = [c['id'] for c in chunks if c['file_id'] == target['id'] and c['provision_label'] == effect['provision']]
        effect['source_chunk_ids'] = [c['id'] for c in chunks if c['file_id'] == source['id'] and c['content_kind'] == 'normative_text']
    manifest = {'schema_version': SCHEMA, 'files': files, 'chunks': chunks, 'effects': effects}
    validate(manifest, originals)
    return manifest, originals


def validate(manifest: dict, originals: dict[str, bytes]) -> None:
    files = {f['id']: f for f in manifest['files']}
    if len(files) != len(manifest['files']) or len({c['id'] for c in manifest['chunks']}) != len(manifest['chunks']):
        raise ValueError('Duplicate ID')
    chunk_ids = {c['id'] for c in manifest['chunks']}
    if manifest.get('schema_version', 1) >= 2:
        document_ids = {f['document_id'] for f in files.values()}
        for effect in manifest['effects']:
            if effect['source_file_id'] not in files or effect['target_document_id'] not in document_ids or not set(effect['source_chunk_ids'] + effect['target_provision_ids']) <= chunk_ids:
                raise ValueError('Invalid effect references')
    texts = {}
    for fid, f in files.items():
        raw = originals[fid]
        if digest(raw) != f['sha256']:
            raise ValueError('Source hash mismatch')
        texts[fid] = raw.decode('utf-8-sig').replace('\r\n', '\n').replace('\r', '\n')
    for c in manifest['chunks']:
        text = texts[c['file_id']]
        if not (0 <= c['start'] < c['end'] <= len(text)) or text[c['start']:c['end']] != c['text']:
            raise ValueError('Invalid chunk coordinates')
        if c['line_start'] != text.count('\n', 0, c['start']) + 1 or c['line_end'] != text.count('\n', 0, c['end'] - 1) + 1:
            raise ValueError('Invalid line coordinates')


def publish(archive: Path, root: Path) -> str:
    manifest, originals = build_snapshot(archive)
    data = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()
    snapshot_id = digest(data)
    snapshots = root / 'snapshots'
    snapshots.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.staging-', dir=snapshots))
    try:
        (staging / 'files').mkdir()
        for fid, raw in originals.items():
            (staging / 'files' / fid).write_bytes(raw)
        (staging / 'manifest.json').write_bytes(data)
        target = snapshots / snapshot_id
        if target.exists():
            load_snapshot(root, snapshot_id)
        else:
            os.rename(staging, target)
        fd, name = tempfile.mkstemp(prefix='.active-', dir=root)
        with os.fdopen(fd, 'w', encoding='ascii') as f:
            f.write(snapshot_id)
        os.replace(name, root / 'active')
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return snapshot_id


def load_snapshot(root: Path, snapshot_id: str | None = None) -> tuple[dict, dict[str, bytes]]:
    sid = snapshot_id if snapshot_id is not None else (root / 'active').read_text(encoding='ascii').strip()
    if not re.fullmatch(r'[0-9a-f]{64}', sid):
        raise ValueError('Invalid snapshot ID')
    directory = root / 'snapshots' / sid
    data = (directory / 'manifest.json').read_bytes()
    if digest(data) != sid:
        raise ValueError('Snapshot manifest hash mismatch')
    manifest = json.loads(data)
    if manifest['schema_version'] not in (1, SCHEMA):
        raise ValueError('Unsupported snapshot schema')
    if any(not re.fullmatch(r'[0-9a-f]{32}', f['id']) for f in manifest['files']):
        raise ValueError('Invalid source ID')
    originals = {f['id']: (directory / 'files' / f['id']).read_bytes() for f in manifest['files']}
    validate(manifest, originals)
    return manifest, originals
