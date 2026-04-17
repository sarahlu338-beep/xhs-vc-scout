import json
import re
import html
import urllib.request
import xml.etree.ElementTree as ET
import subprocess
from datetime import datetime, timezone

USER_AGENT = "Mozilla/5.0"
TIMEOUT = 20

NS = {
    "atom": "http://www.w3.org/2005/Atom",
}


def fetch_text(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def fetch_xml(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return resp.read()


def get_text(node, tag, default=""):
    child = node.find(tag, NS) if node is not None else None
    if child is not None and child.text:
        return child.text.strip()
    return default


def clean_text(text: str) -> str:
    text = html.unescape(text or "")
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def extract_meta(html_text: str, key: str) -> str:
    patterns = [
        rf'<meta[^>]+property=["\']{re.escape(key)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+property=["\']{re.escape(key)}["\']',
        rf'<meta[^>]+name=["\']{re.escape(key)}["\'][^>]+content=["\'](.*?)["\']',
        rf'<meta[^>]+content=["\'](.*?)["\'][^>]+name=["\']{re.escape(key)}["\']',
    ]
    for pattern in patterns:
        m = re.search(pattern, html_text, re.IGNORECASE | re.DOTALL)
        if m:
            return clean_text(m.group(1))
    return ""


def enrich_product_hunt_summary(link: str) -> str:
    try:
        html_text = fetch_text(link)
        summary = extract_meta(html_text, "og:description") or extract_meta(html_text, "description")
        return summary[:800]
    except Exception:
        return ""


def parse_yc_launches_page(url: str):
    try:
        html_text = fetch_text(url)
        title = "YC Launches"
        summary = extract_meta(html_text, "og:description") or extract_meta(html_text, "description")
        return {
            "title": title,
            "published_at": "",
            "link": url,
            "summary": summary[:800]
        }
    except Exception as e:
        return {
            "title": "YC Launches",
            "published_at": "",
            "link": url,
            "summary": f"WEBPAGE_ERROR: {str(e)}"
        }


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
                summary = (
                    item.findtext("description", "").strip()
                    or item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded", "").strip()
                )
                return {
                    "title": title,
                    "published_at": published_at,
                    "link": link,
                    "summary": clean_text(summary)[:800]
                }

        entry = root.find("atom:entry", NS)
        if entry is not None:
            title = get_text(entry, "atom:title")
            published_at = get_text(entry, "atom:published")
            summary = get_text(entry, "atom:summary")

            if not summary:
                content_node = entry.find("atom:content", NS)
                if content_node is not None and content_node.text:
                    summary = content_node.text.strip()

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
                "summary": clean_text(summary)[:800]
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
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        data = json.loads(result.stdout)

        entries = data.get("entries", [])
        if not entries:
            return {
                "title": "",
                "published_at": "",
                "link": url,
                "summary": ""
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
        if source.get("name") == "YC Launches":
            parsed = parse_yc_launches_page(source["url"])
        elif source.get("type") == "rss":
            parsed = parse_rss_feed(source["url"])
            if source.get("name") == "Product Hunt" and parsed["link"] and not parsed["summary"]:
                parsed["summary"] = enrich_product_hunt_summary(parsed["link"])
        else:
            parsed = {
                "title": "",
                "published_at": "",
                "link": source["url"],
                "summary": "WEBPAGE_SOURCE_PENDING"
            }

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
