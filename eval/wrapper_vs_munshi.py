"""Baseline slot deliberately refuses to fabricate a plain-LLM response."""
import json
from pathlib import Path
p=Path('demo/cached_responses/plain_llm.json')
if not p.exists():
    print('NOT DONE: no verified live baseline or genuine cached recording. No comparison claim made.')
else:
    data=json.loads(p.read_text())
    assert all(k in data for k in ['provider','model','prompt','response','recorded_at'])
    print(json.dumps(data,indent=2))
