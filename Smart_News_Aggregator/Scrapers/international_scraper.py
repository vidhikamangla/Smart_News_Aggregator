import requests
from bs4 import BeautifulSoup

UN_RSS_URL = "https://news.un.org/feed/subscribe/en/news/region/global/feed/rss.xml"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def extract_un_article(url):
    """Scrape full article text from UN News page."""
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        container = soup.find(
            "div",
            class_="clearfix text-formatted field field--name-field-text-column field--type-text-long field--label-hidden field__item"
        )
        if not container:
            print(f"Could not find article content in: {url}")
            return None

        paragraphs = [p.get_text(strip=True) for p in container.find_all("p")]
        return "\n".join(paragraphs)

    except Exception as e:
        print(f"Error scraping UN News article: {e}")
        return None


def scrape_international_top_n(n=10):
    """Scrape UN RSS feed + full article text for top N items (with image URL)."""
    resp = requests.get(UN_RSS_URL, headers=headers, timeout=10)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "xml")

    items = soup.find_all("item")[:n]
    results = []

    for item in items:
        title = item.title.get_text(strip=True)
        link = item.guid.get_text(strip=True)
        date = item.pubDate.get_text(strip=True) if item.pubDate else None
        desc = item.description.get_text(strip=True) if item.description else None

        enclosure = item.find("enclosure")
        image_url = enclosure["url"].strip() if enclosure and enclosure.has_attr("url") else None

        print(f"Scraping UN article: {title}")
        article_text = extract_un_article(link)

        results.append({
            "title": title,
            "link": link,
            "date": date,
            "description": desc,
            "article": article_text,
            "image_url": image_url
        })

    return results


if __name__ == "__main__":
    data = scrape_international_top_n()

    for d in data:
        print("\n==============================")
        print("TITLE:", d["title"])
        print("LINK:", d["link"])
        print("DATE:", d["date"])
        print("IMAGE:", d["image_url"])
        print("\nARTICLE:\n", d["article"])