import requests
from bs4 import BeautifulSoup

HINDU_RSS_URL = "https://www.thehindu.com/news/national/feeder/default.rss"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def extract_article_text(url):
    """Scrape full article text from The Hindu article page."""
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        body = soup.find("div", class_="schemaDiv", itemprop="articleBody")
        if not body:
            print(f"Could not find articleBody in: {url}")
            return None

        paragraphs = [p.get_text(strip=True) for p in body.find_all("p")]
        return "\n".join(paragraphs)

    except Exception as e:
        print(f"Error scraping article page: {e}")
        return None


def scrape_national_top_n(n=10):
    """Scrape RSS feed + article text for top N news items, including image URL."""
    resp = requests.get(HINDU_RSS_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "xml")

    items = soup.find_all("item")[:n]
    results = []

    for item in items:
        title = item.title.get_text(strip=True)
        link = item.link.get_text(strip=True)
        date = item.pubDate.get_text(strip=True) if item.pubDate else None
        category = item.category.get_text(strip=True) if item.category else None

        media_tag = item.find("media:content")
        image_url = media_tag["url"].strip() if media_tag and media_tag.has_attr("url") else None

        print(f"Scraping article: {title}")
        article_text = extract_article_text(link)

        results.append({
            "title": title,
            "link": link,
            "date": date,
            "category": category,
            "article": article_text,
            "image_url": image_url
        })

    return results


if __name__ == "__main__":
    data = scrape_national_top_n()

    for d in data:
        print("\n==============================")
        print("TITLE:", d["title"])
        print("LINK:", d["link"])
        print("DATE:", d["date"])
        print("CATEGORY:", d["category"])
        print("IMAGE:", d["image_url"])
        print("\nARTICLE:\n", d["article"])