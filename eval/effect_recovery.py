"""Run from repository root. No planted values are passed into the estimator."""
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'api'))
from integrations.paytm_pos_sim import PaytmPOSAdapter
from engine.promo_uplift import promo
from app.config import DATA

a=PaytmPOSAdapter()
truth=json.loads((DATA/'ground_truth.json').read_text())
rows=[]
for kind in a.bundle['shops']:
    r=promo(a.merchant(kind)['skus'][0])
    u=r.steps[0]['estimated_uplift']; f=r.steps[0]['estimated_pull_forward']
    assert abs(u-truth['uplift'])<.15, (kind,u)
    assert abs(f-truth['pull_forward'])<.1,(kind,f)
    rows.append({'persona':kind,'true_uplift':truth['uplift'],'estimated_uplift':u,
                 'true_pull_forward':truth['pull_forward'],'estimated_pull_forward':f,'verdict':r.output['verdict']})
# Confounding example: a festival increases baseline by 2×. Matching the festival control removes it.
# This illustrative example is distinct from the unbiased episode recovery above.
naive=2*(1+truth['uplift'])-1
report={'recovery':rows,'chart':[{'name':'Planted','uplift':truth['uplift']},
          {'name':'Matched control','uplift':rows[2]['estimated_uplift']},
          {'name':'Naive pre/post','uplift':naive}],
        'note':'Recovery tolerance: 0.15 uplift and 0.10 pull-forward. Naive example assumes a 2× festival baseline; it is illustrative, not a measured benchmark.'}
Path('web/public/proof.json').write_text(json.dumps(report,indent=2))
Path('eval/effect_recovery.json').write_text(json.dumps(report,indent=2))
# Standalone exact vector chart, no generated imagery.
svg=['<svg xmlns="http://www.w3.org/2000/svg" width="760" height="380" viewBox="0 0 760 380"><rect width="760" height="380" fill="#f3f7fc"/><text x="30" y="42" font-family="sans-serif" font-size="24" fill="#071c36">Synthetic effect recovery</text>']
for i,row in enumerate(report['chart']):
    x=80+i*220; h=row['uplift']*90
    svg.append(f'<rect x="{x}" y="{300-h}" width="130" height="{h}" rx="8" fill="#1762e7"/><text x="{x}" y="{290-h}" font-family="sans-serif" font-size="18">{row["uplift"]:.1%}</text><text x="{x-15}" y="330" font-family="sans-serif" font-size="15">{row["name"]}</text>')
svg.append('</svg>')
Path('demo/effect-recovery.svg').write_text(''.join(svg))
print(json.dumps(report,indent=2))
