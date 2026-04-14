import json
from datetime import datetime, timezone

with open("sources.json", "r", encoding="utf-8") as f:
    sources = json.load(f)

items = []

for source_type in ["websites", "youtube"]:
    for source in sources.get(source_type, []):
        items.append({
            "source": source["name"],
            "type": source_type[:-1],
            "title": "",
            "published_at": "",
            "link": source["url"],
            "summary": ""
        })

output = {
    "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "items": items
}

with open("daily_feed.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
