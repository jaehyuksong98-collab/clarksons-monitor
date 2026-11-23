import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from .sources import LISTING, fetch, listing, extract, news
from .model import compare, write_model
from .report import report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--model',default='models/scenario-original.xlsx')
    p.add_argument('--output',default='outputs')
    p.add_argument('--state',default='state.json')
    p.add_argument('--replay-h1',action='store_true',help='Reproduce H1 ingestion; never score H2 forecasts')
    a=p.parse_args()
    out=Path(a.output); out.mkdir(parents=True,exist_ok=True)
    result=dict(started=datetime.now(timezone.utc).isoformat(),status='running',notes=[],news=[],errors=[])
    statepath=Path(a.state)
    state=json.loads(statepath.read_text()) if statepath.exists() else {'seen':{}}
    staged_state=json.loads(json.dumps(state))
    eligible=False
    try:
        items=listing(fetch(LISTING))
        latest=next((i for i in items if i['period']=='H1 2026'),None) if a.replay_h1 else next((i for i in items if i['period']=='FY 2026'),None)
        result['listed_announcements']=items
        if not latest:
            result['status']='no_new_result'
            result['notes'].append('No FY2026 announcement listed. Model not opened or saved.')
        else:
            content=fetch(latest['url'])
            digest=hashlib.sha256(content).hexdigest()
            eligible=a.replay_h1 or state['seen'].get(latest['period'])!=digest
            if not eligible:
                result['status']='no_change'
                result['notes'].append('Announcement content unchanged. Model not opened or saved.')
            else:
                (out/('announcement-'+digest[:12]+'.pdf')).write_bytes(content)
                disclosure=extract(content,latest)
                result['disclosure']=disclosure
                result['comparisons']=compare(a.model,disclosure)
                result['status']='replay_h1' if a.replay_h1 else 'new_result'
                # Publish workbook only after all source/model validation succeeds.
                result['workbook']=write_model(a.model,out/'scenario-with-actuals.xlsx',disclosure,result['comparisons'])
                result['notes'].append('Original workbook preserved. New actuals, comparison and change-log sheets added to output copy.')
                if not a.replay_h1: staged_state['seen'][latest['period']]=digest
    except Exception as e:
        result['status']='failed'; result['errors'].append(type(e).__name__+': '+str(e))
    try:
        result['news']=news()
    except Exception as e:
        result['errors'].append('News: '+type(e).__name__+': '+str(e))
        if result['status']!='failed': result['status']='partial'
    # Report succeeds before advancing durable state; replay never advances production state.
    report(out/'review.docx',result)
    (out/'run.json').write_text(json.dumps(result,indent=2))
    if result['status'] not in ('failed','partial') and not a.replay_h1:
        statepath.parent.mkdir(parents=True,exist_ok=True)
        temp=statepath.with_suffix('.tmp'); temp.write_text(json.dumps(staged_state,indent=2)); temp.replace(statepath)
    print(json.dumps({k:result[k] for k in ('status','errors','notes')},indent=2))
    return 1 if result['errors'] else 0


if __name__=='__main__': sys.exit(main())
