import json
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

USER_AGENT = "Mozilla/5.0"
TIMEOUT = 20

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "media": "http://search.yahoo.com/mrss/",
}

def fetch_xml(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()

def get_text(node, tag, default=""):
    child = node.find(tag, NS) if node is not None else None
    if child is not None and child.text:
        return child.text.strip()
    return default

def parse_feed(url: str):
    try:
        content = fetch_xml(url)
        root = ET.fromstring(content)

        # RSS
        channel = root.find("channel")
        if channel is not None:
            item = channel.find("item")
            if item is not None:
                title = get_text(item, "title")
                link = get_text(item, "link", url)
                published_at = get_text(item, "pubDate")
                summary = get_text(item, "description")
                return {
                    "title": title,
                    "published_at": published_at,
                    "link": link,
                    "summary": summary[:300]
                }

        # Atom / YouTube
        entry = root.find("atom:entry", NS)
        if entry is not None:
            title = get_text(entry, "atom:title")
            published_at = get_text(entry, "atom:published")
            summary = get_text(entry, "atom:summary")

            link = url
            for link_node in entry.findall("atom:link", NS):
                href = link_node.attrib.get("href")
                rel = link_node.attrib.get("rel", "")
                if href and (rel == "alternate" or rel == ""):
                    link = href
                    break

            return {
                "title": title,
                "published_at": published_at,
                "link": link,
                "summary": summary[:300]
            }

    except Exception as e:
        return {
            "title": "",
            "published_at": "",
            "link": url,
            "summary": f"FETCH_ERROR: {str(e)}"
        }

    return {
        "title": "",
        "published_at": "",
        "link": url,
        "summary": "NO_ITEM_FOUND"
    }

def main():
    with open("sources.json", "r", encoding="utf-8") as f:
        sources = json.load(f)

    items = []

    for source_type in ["websites", "youtube"]:
        for source in sources.get(source_type, []):
            parsed = parse_feed(source["url"])
            items.append({
                "source": source["name"],
                "type": "website" if source_type == "websites" else "youtube",
                "title": parsed["title"],
                "published_at": parsed["published_at"],
                "link": parsed["link"],
                "summary": parsed["summary"]
            })

    output = {
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "items": items
    }

    with open("daily_feed.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    main()
