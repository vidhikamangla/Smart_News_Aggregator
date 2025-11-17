import requests
from bs4 import BeautifulSoup

IE_RSS_URL = "https://indianexpress.com/section/sports/feed/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def extract_ie_article(url):
    """Extract full article text from Indian Express page."""
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        container = soup.find("div", id="pcl-full-content", class_="story_details")
        if not container:
            print(f"Could not find full article div in: {url}")
            return None

        paragraphs = [p.get_text(strip=True) for p in container.find_all("p")]
        return "\n".join(paragraphs)

    except Exception as e:
        print(f"Error scraping Indian Express article: {e}")
        return None


def scrape_sports_top_n(n=10):
    """Scrape RSS feed + full article text for top N sports stories (with image URL)."""
    resp = requests.get(IE_RSS_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "xml")

    items = soup.find_all("item")[:n]
    results = []

    for item in items:
        title = item.title.get_text(strip=True)
        link = item.link.get_text(strip=True)
        date = item.pubDate.get_text(strip=True) if item.pubDate else None
        author = item.find("dc:creator").get_text(strip=True) if item.find("dc:creator") else None

        media_tag = item.find("media:content")
        image_url = media_tag["url"].strip() if media_tag and media_tag.has_attr("url") else None

        print(f"Scraping IE article: {title}")
        article_text = extract_ie_article(link)

        results.append({
            "title": title,
            "link": link,
            "date": date,
            "author": author,
            "article": article_text,
            "image_url": image_url
        })

    return results


if __name__ == "__main__":
    data = scrape_sports_top_n()

    for d in data:
        print("\n==============================")
        print("TITLE:", d["title"])
        print("AUTHOR:", d["author"])
        print("LINK:", d["link"])
        print("DATE:", d["date"])
        print("IMAGE:", d["image_url"])
        print("\nARTICLE:\n", d["article"])