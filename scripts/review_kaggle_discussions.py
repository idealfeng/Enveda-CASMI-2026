"""Snapshot public competition discussions using read-only official SDK calls."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import html
import json
import logging
import os
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
COMPETITION = "enveda-CASMI26-molecule-id-mass-spectra"
DEFAULT_TOPICS = [756741, 756504, 755965, 755039, 755089, 753724,
                  753400, 753363, 752356, 751300, 750241, 749412,
                  748524, 748068, 745468, 745148, 744343, 744011,
                  743974, 743254, 741597]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n",
                    encoding="utf-8")


def plain(value):
    value = re.sub(r"<(?:br\s*/?|/p|/li|/h[1-6])>", "\n", value, flags=re.I)
    return html.unescape(re.sub(r"<[^>]+>", "", value)).strip()


def fetch_topic(topic_id, destination):
    from kaggle_first_submission import make_api
    from kagglesdk.discussions.types.discussions_api_service import (
        ApiGetTopicRequest, ApiListCommentsRequest)

    record = {"id": topic_id, "read_only": True,
              "checked_at_utc": datetime.now(timezone.utc).isoformat()}
    try:
        with make_api().build_kaggle_client() as client:
            service = client.discussions.discussion_api_client
            request = ApiGetTopicRequest()
            request.id = topic_id
            topic = service.get_topic(request).topic.to_dict()
            if f"/{COMPETITION}/discussion/" not in topic.get("url", ""):
                raise ValueError("Unexpected competition topic")
            comments, token = [], ""
            for _ in range(4):
                request = ApiListCommentsRequest()
                request.topic_id, request.page_size = topic_id, 100
                if token:
                    request.page_token = token
                response = service.list_comments(request)
                comments.extend(x.to_dict() for x in response.comments or [])
                token = response.next_page_token
                if not token:
                    break
            payload = dict(record, topic=topic, comments=comments,
                           comments_truncated=bool(token))
            write_json(destination / f"{topic_id}.json", payload)
            text = [topic.get("title", ""), "https://www.kaggle.com" + topic["url"],
                    "Author: " + topic.get("authorName", ""),
                    "Posted: " + str(topic.get("postDate", "")),
                    plain(topic.get("content", ""))]

            def add_comment(comment, depth=0):
                text.extend(["\n" + "  " * depth + "Comment: " + comment.get("authorName", ""),
                             plain(comment.get("content", ""))])
                for reply in comment.get("replies", []):
                    add_comment(reply, depth + 1)

            for comment in comments:
                add_comment(comment)
            raw = "\n\n".join(text).encode("utf-8")
            (destination / f"{topic_id}.txt").write_bytes(raw)
            record.update(status="saved", title=topic.get("title"),
                          comments=len(comments), comments_truncated=bool(token),
                          text_sha256=hashlib.sha256(raw).hexdigest())
    except Exception as error:
        record.update(status="failed", error_type=type(error).__name__)
        write_json(destination / f"{topic_id}.error.json", record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", required=True)
    parser.add_argument("--topics", type=int, nargs="+", default=DEFAULT_TOPICS)
    args = parser.parse_args()
    destination = (ROOT / args.out).resolve()
    if not destination.is_relative_to(ROOT):
        raise ValueError("All new artifacts must remain in the workspace on D:")
    destination.mkdir(parents=True, exist_ok=False)
    for name in ("TEMP", "TMP", "PYTHONPYCACHEPREFIX"):
        os.environ[name] = str(ROOT / ".cache" / ("pycache-win" if "PYCACHE" in name else "tmp"))
    logging.disable(logging.CRITICAL)
    from kaggle_first_submission import make_api
    from kagglesdk.competitions.types.competition_api_service import ApiListCompetitionTopicsRequest
    from kagglesdk.discussions.types.discussions_enums import TopicListSortBy

    topics, total = {}, None
    with make_api().build_kaggle_client() as client:
        for page in range(1, 11):
            request = ApiListCompetitionTopicsRequest()
            request.competition_name, request.page = COMPETITION, page
            request.sort_by = TopicListSortBy.TOPIC_LIST_SORT_BY_NEW
            response = client.competitions.competition_api_client.list_competition_topics(request)
            rows = [x.to_dict() for x in response.topics or []]
            write_json(destination / f"inventory_page_{page}.json", response.to_dict())
            previous = len(topics)
            topics.update({x["id"]: x for x in rows})
            total = response.total_count
            if len(topics) >= total or not rows or len(topics) == previous:
                break
    write_json(destination / "inventory.json", dict(total_reported=total,
               unique_fetched=len(topics), records=list(topics.values()), read_only=True,
               checked_at_utc=datetime.now(timezone.utc).isoformat()))
    with ThreadPoolExecutor(max_workers=3) as pool:
        records = list(pool.map(lambda x: fetch_topic(x, destination), dict.fromkeys(args.topics)))
    write_json(destination / "receipt.json", dict(inventory_count=len(topics), results=records,
               read_only=True, external_messages_sent=False, cloud_runs_started=False))
    print(json.dumps(dict(inventory_count=len(topics), results=records), ensure_ascii=True))


if __name__ == "__main__":
    main()
