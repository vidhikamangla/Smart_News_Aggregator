import requests
from bs4 import BeautifulSoup

TOI_RSS_URL = "https://timesofindia.indiatimes.com/rss.cms"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def extract_toi_article(url):
    """Scrape full article text from a TOI news page."""
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        container = soup.find("div", class_="_s30J clearfix")
        if not container:
            print(f"Could not find article body in: {url}")
            return None

        article_text = container.get_text(separator="\n", strip=True)
        return article_text

    except Exception as e:
        print(f"Error scraping article page: {e}")
        return None


def scrape_states_top_n(state_id, n=10):
    """Scrape RSS for a specific TOI region + extract full article content and image."""
    try:
        resp = requests.get(TOI_RSS_URL, headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        state_link = soup.find(id=state_id)
        if not state_link:
            print(f"No link found with ID '{state_id}'")
            return []

        rss_url = state_link.get("href")
        print(f"Fetching RSS feed: {rss_url}")

        resp = requests.get(rss_url, headers=headers, timeout=10)
        resp.raise_for_status()
        feed = BeautifulSoup(resp.text, "xml")

        items = feed.find_all("item")[:n]
        results = []

        for item in items:
            title = item.title.get_text(strip=True)
            link = item.link.get_text(strip=True)
            date = item.pubDate.get_text(strip=True) if item.pubDate else None

            enclosure = item.find("enclosure")
            image_url = enclosure["url"].strip() if enclosure and enclosure.has_attr("url") else None

            print(f"Scraping TOI article: {title}")
            article_text = extract_toi_article(link)

            results.append({
                "title": title,
                "link": link,
                "date": date,
                "article": article_text,
                "image_url": image_url
            })

        return results

    except Exception as e:
        print(f"Error in scrape_states_top_n: {e}")
        return []


if __name__ == "__main__":
    data = scrape_states_top_n("delhi")

    for d in data:
        print("\n==============================")
        print("TITLE:", d["title"])
        print("LINK:", d["link"])
        print("DATE:", d["date"])
        print("IMAGE:", d["image_url"])
        print("\nARTICLE:\n", d["article"])