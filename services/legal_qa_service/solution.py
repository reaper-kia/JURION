"""Standalone organizer entry point, using the same legal_qa core as the service."""
from concurrent.futures import ThreadPoolExecutor
import csv
import os
from pathlib import Path
import re
import time

from legal_qa.answer import answer, ProxyGenerator
from legal_qa.application import Dispatcher, ImportCorpus, AnswerQuery


def history(text):
    parts = re.split(r'(?m)^\s*(Пользователь|Ассистент):\s*', text)
    if len(parts) == 1:
        return [('user', text)]
    messages = []
    for i in range(1, len(parts) - 1, 2):
        messages.append(('user' if parts[i] == 'Пользователь' else 'assistant', parts[i + 1].strip()))
    return messages


def main():
    data_dir = Path(os.getenv('DATA_DIR', 'data'))
    with (data_dir / 'questions.csv').open(encoding='utf-8-sig', newline='') as f:
        rows = list(csv.DictReader(f))
    deadline = time.monotonic() + 19 * 60
    try:
        manifest, _ = Dispatcher().dispatch(ImportCorpus(data_dir / 'knowledge-base.zip'))
        failure = None
    except Exception:
        manifest, failure = None, 'Техническая ошибка загрузки базы знаний.'

    def run(row):
        if failure:
            return failure
        try:
            result = Dispatcher().dispatch(AnswerQuery(manifest, history(row.get('question', '')), ProxyGenerator.from_env(), None, deadline))
            return result.text or 'Техническая ошибка: пустой ответ.'
        except Exception:
            return 'Техническая ошибка при обработке вопроса; повторите запрос позднее.'

    try:
        workers = min(8, max(1, int(os.getenv('MAX_WORKERS', '4'))))
    except ValueError:
        workers = 4
    with ThreadPoolExecutor(max_workers=workers) as executor:
        results = list(executor.map(run, rows))
    with open('submission.csv', 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['id', 'answer'])
        for row, result in zip(rows, results):
            writer.writerow([row['id'], result])


if __name__ == '__main__':
    main()
