import argparse
from pathlib import Path
from .application import Dispatcher, PublishSnapshot

parser = argparse.ArgumentParser(description='Import and publish a corpus snapshot')
parser.add_argument('archive', type=Path)
parser.add_argument('--catalog', type=Path, required=True)
args = parser.parse_args()
print(Dispatcher().dispatch(PublishSnapshot(args.archive, args.catalog)))
