#!/usr/bin/env python3
import requests

def scrape_hacker_news():
    """Pega os posts da frontpage do Hacker News (API Algolia, sem scraping de HTML)"""
    try:
        url = "http://hn.algolia.com/api/v1/search?tags=front_page"
        response = requests.get(url, timeout=10)
        data = response.json()

        ias = []
        for item in data.get("hits", [])[:10]:
            title = item.get("title")
            if not title:
                continue
            story_url = item.get("url") or f"https://news.ycombinator.com/item?id={item.get('objectID')}"
            ias.append({
                "name": title,
                "description": f"{item.get('points', 0)} pontos, {item.get('num_comments', 0)} comentários",
                "url": story_url,
                "source": "Hacker News"
            })

        print(f"[HN] Encontrado {len(ias)} IAs")
        return ias
    except Exception as e:
        print(f"Erro scraping HN: {e}")
        return []

if __name__ == "__main__":
    for ia in scrape_hacker_news():
        print(ia)
