"""Create a fictitious, shareable corpus for the stack integration test."""
from pathlib import Path
from zipfile import ZipFile

path = Path('.local/knowledge-base.zip')
path.parent.mkdir(exist_ok=True)
with ZipFile(path, 'w') as archive:
    archive.writestr('test-law.txt', 'Статья 1. Оплата аренды составляет 100 рублей.\n')

    archive.writestr('Договор поставки ПТ-05-2023 synthetic.txt', 'Статья 1. Гарантийный срок устанавливается производителем.\n')
