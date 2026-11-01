"""Static package verification; does not start Home Assistant or write caches."""
import ast
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
D=ROOT/'custom_components/u1_companion'
manifest=json.loads((D/'manifest.json').read_text(encoding='utf-8'))
assert manifest['domain']=='u1_companion'
assert manifest['version']=='0.6.0' and manifest['config_flow'] is True
assert manifest['requirements']==[] and manifest['iot_class']=='local_polling'
assert all((D/(name+'.py')).exists() for name in ['__init__','config_flow','coordinator','api','model','sensor','binary_sensor','diagnostics'])
def structure(value):
 if isinstance(value,dict): return {k:structure(v) for k,v in value.items()}
 return None
english=json.loads((D/'strings.json').read_text(encoding='utf-8'))
for language in ['fr','en']:
 translated=json.loads((D/f'translations/{language}.json').read_text(encoding='utf-8'))
 assert structure(english)==structure(translated),language
for file in ROOT.rglob('*.py'):
 ast.parse(file.read_text(encoding='utf-8'),filename=str(file))
catalog=json.loads((D/'catalog.json').read_text(encoding='utf-8'))
assert len(catalog['tasks'])==7 and all(t['intervalHours'] is None for t in catalog['tasks'])
assert catalog['version']=='2026.10.15.1'
assert not (D/'data').exists() and not (D/'.storage').exists()
print('Package 0.6.0: syntax, manifest, FR/EN forms, seven sourced tasks, no bundled user data: OK')
print('Catalogue SHA256:',hashlib.sha256((D/'catalog.json').read_bytes()).hexdigest())
