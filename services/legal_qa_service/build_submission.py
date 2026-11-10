"""Create a self-contained submission archive without corpus or test cases."""
from pathlib import Path
import sys
import zipfile

root = Path(__file__).resolve().parent
target = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'submission.zip'
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as z:
    z.writestr('solution.py', (root / 'solution.py').read_text().replace('from legal_qa.', 'from jurion_'))
    z.writestr('requirements.txt', '')
    for file in sorted((root / 'legal_qa').glob('*.py')):
        if file.name.startswith('__'):
            continue
        source = file.read_text()
        import re
        source = re.sub(r'from \.([a-z_]+) import', r'from jurion_\1 import', source)
        source = re.sub(r'from \. import ([a-z_]+)', r'import jurion_\1 as \1', source)
        z.writestr('jurion_' + file.name, source)
print(target)
