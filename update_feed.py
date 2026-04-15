import json
import urllib.request
import xml.etree.ElementTree as ET
import subprocess
from datetime import datetime, timezone

USER_AGENT = "Mozilla/5.0"
TIMEOUT = 20

NS = {
    "atom": "http://www.w3.org/2005/Atom",
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

def parse_rss_feed(url: str):
    try:
        content = fetch_xml(url)
        root = ET.fromstring(content)

        channel = root.find("channel")
        if channel is not None:
            item = channel.find("item")
            if item is not None:
                title = item.findtext("title", "").strip()
                link = item.findtext("link", url).strip()
                published_at = item.findtext("pubDate", "").strip()
                summary = item.findtext("description", "").strip()
                return {
                    "title": title,
                    "published_at": published_at,
                    "link": link,
                    "summary": summary[:300]
                }

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

def parse_youtube_with_ytdlp(url: str):
    try:
        cmd = [
            "yt-dlp",
            "--flat-playlist",
            "--playlist-end", "1",
            "--dump-single-json",
            url
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        entries = data.get("entries", [])
        if not entries:
            return {
                "title": "",
                "published_at": "",
                "link": url,
                "summary": "NO_VIDEO_FOUND"
            }

        first = entries[0]
        video_id = first.get("id", "")
        title = first.get("title", "")
        upload_date = first.get("upload_date", "")

        published_at = ""
        if upload_date and len(upload_date) == 8:
            published_at = f"{upload_date[:4]}-{upload_date[4:6]}-{upload_date[6:8]}"

        link = f"https://www.youtube.com/watch?v={video_id}" if video_id else url

        return {
            "title": title,
            "published_at": published_at,
            "link": link,
            "summary": ""
        }

    except Exception as e:
        return {
            "title": "",
            "published_at": "",
            "link": url,
            "summary": f"YTDLP_ERROR: {str(e)}"
        }

def main():
    with open("sources.json", "r", encoding="utf-8") as f:
        sources = json.load(f)

    items = []

    for source in sources.get("websites", []):
        parsed = parse_rss_feed(source["url"])
        items.append({
            "source": source["name"],
            "type": "website",
            "title": parsed["title"],
            "published_at": parsed["published_at"],
            "link": parsed["link"],
            "summary": parsed["summary"]
        })

    for source in sources.get("youtube", []):
        if source.get("type") == "youtube_handle":
            parsed = parse_youtube_with_ytdlp(source["url"])
        else:
            parsed = parse_rss_feed(source["url"])

        items.append({
            "source": source["name"],
            "type": "youtube",
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
