"""Read-only current CASMI forum delta, including new replies on older topics."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import json
import logging
import os
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/public_review_20261116/forum'
sys.path.insert(0,str(ROOT/'scripts'))
from review_kaggle_discussions import COMPETITION,fetch_topic,write_json


def main():
    OUT.mkdir(parents=True,exist_ok=False)
    from kaggle_first_submission import make_api
    from kagglesdk.competitions.types.competition_api_service import ApiListCompetitionTopicsRequest
    from kagglesdk.discussions.types.discussions_enums import TopicListSortBy
    old=json.loads((ROOT/'reports/discussion_review_20261114/forum/inventory.json').read_text(encoding='utf-8'))
    old_by={x['id']:x for x in old['records']}
    topics={};total=None
    with make_api().build_kaggle_client() as client:
        for page in range(1,16):
            req=ApiListCompetitionTopicsRequest()
            req.competition_name=COMPETITION;req.page=page
            req.sort_by=TopicListSortBy.TOPIC_LIST_SORT_BY_NEW
            res=client.competitions.competition_api_client.list_competition_topics(req)
            write_json(OUT/f'inventory_page_{page}.json',res.to_dict())
            rows=[x.to_dict() for x in res.topics or []]
            before=len(topics);topics.update({x['id']:x for x in rows});total=res.total_count
            if len(topics)>=total or not rows or len(topics)==before:break
    now=datetime.now(timezone.utc).isoformat()
    write_json(OUT/'inventory.json',dict(total_reported=total,unique_fetched=len(topics),records=list(topics.values()),read_only=True,checked_at_utc=now))
    new=[x for k,x in topics.items() if k not in old_by]
    changed=[x for k,x in topics.items() if k in old_by and any(x.get(f)!=old_by[k].get(f) for f in ('title','commentCount','lastCommentPostDate'))]
    # Include complete content of all changed topics, plus active technical anchors.
    anchors=[743254,748524,756504,755089,757307,758541,756893,749217]
    selected=list(dict.fromkeys([x['id'] for x in new+changed]+[i for i in anchors if i in topics]))
    write_json(OUT/'delta.json',dict(checked_at_utc=now,old_count=len(old_by),new_count=len(topics),new_topics=new,changed_topics=changed,removed_ids=sorted(set(old_by)-set(topics)),selected_topic_ids=selected,scope='Inventory comparison with20261114; no external messages or writes'))
    print(json.dumps(dict(stage='inventory_complete',count=len(topics),new_topics=new,changed_topics=changed,selected_topic_ids=selected)),flush=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda i:fetch_topic(i,OUT),selected))
    write_json(OUT/'receipt.json',dict(checked_at_utc=now,inventory_count=len(topics),results=results,read_only=True,external_messages_sent=False,cloud_runs_started=False))
    print(json.dumps(dict(stage='topics_saved',results=results)),flush=True)


if __name__=='__main__':
    for name,rel in [('TEMP','.cache/tmp'),('TMP','.cache/tmp'),('PYTHONPYCACHEPREFIX','.cache/pycache-win')]:
        p=ROOT/rel;p.mkdir(parents=True,exist_ok=True);os.environ[name]=str(p)
    logging.disable(logging.CRITICAL)
    main()
