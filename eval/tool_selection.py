import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
from ai.tools import route
from ai.llm_adapter import LLMAdapter
from ai.number_guard import check
from integrations.paytm_pos_sim import PaytmPOSAdapter
from engine.promo_uplift import promo
rows=[json.loads(r) for r in Path('eval/hinglish_questions.jsonl').read_text().splitlines()]
matched=sum(route(r['question'])==r['expected_tool'] for r in rows)
r=promo(PaytmPOSAdapter().merchant('electronics')['skus'][0])
violations=sum(not check(LLMAdapter().explain('promo',r,l),r.model_dump()) for l in ['en','hi','mr'])
report={'correct':matched,'total':len(rows),'accuracy':matched/len(rows),'template_number_violations':violations,
        'limitation':'Hand-authored keyword suite, not held-out general language understanding. Numeric guard evaluated on templates, not live LLM output.'}
Path('eval/tool_selection.json').write_text(json.dumps(report,indent=2));print(report)
assert matched==len(rows) and violations==0
