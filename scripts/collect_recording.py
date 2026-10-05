from pathlib import Path
import shutil
videos=list(Path('demo/recordings').glob('*/video.webm'))
if len(videos)!=1:
    raise SystemExit('Expected one successful demo recording; inspect Playwright output before packaging.')
shutil.copyfile(videos[0],Path('demo/munshi-demo.webm'))
print('Saved demo/munshi-demo.webm')
