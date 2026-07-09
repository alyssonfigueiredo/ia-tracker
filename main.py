#!/usr/bin/env python3
import os
import sqlite3
import requests
from datetime import datetime
from bs4 import BeautifulSoup
import google.generativeai as genai
import json
import time
from scraper_hn import scrape_hacker_news

# Config
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = "ia_tracker.db"

genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-2.5-flash")

# ============= BD =============
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS ias (
            id INTEGER PRIMARY KEY,
            name TEXT UNIQUE,
            description TEXT,
            url TEXT,
            source TEXT,
            funcionalidade TEXT,
            aplicabilidade TEXT,
            score REAL,
            confianca REAL,
            data_coleta TIMESTAMP,
            categoria TEXT
        )
    """)
    cols = [r[1] for r in c.execute("PRAGMA table_info(ias)").fetchall()]
    if "categoria" not in cols:
        c.execute("ALTER TABLE ias ADD COLUMN categoria TEXT")
    conn.commit()
    conn.close()

def save_ia(name, desc, url, source, funcionalidade, aplicabilidade, score, confianca, categoria):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute("""
            INSERT OR REPLACE INTO ias
            (name, description, url, source, funcionalidade, aplicabilidade, score, confianca, data_coleta, categoria)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, desc, url, source, funcionalidade, aplicabilidade, score, confianca, datetime.now(), categoria))
        conn.commit()
    except Exception as e:
        print(f"Erro ao salvar {name}: {e}")
    conn.close()

# ============= SCRAPING =============
def scrape_product_hunt():
    """Scrapa IAs trending do Product Hunt"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://www.producthunt.com/products/trending"
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        ias = []
        for item in soup.find_all("a", {"data-test": "product-item"})[:10]:
            try:
                name = item.find("h2")
                desc = item.find("p")
                href = item.get("href", "")
                
                if name and desc:
                    ias.append({
                        "name": name.text.strip(),
                        "description": desc.text.strip(),
                        "url": f"https://producthunt.com{href}" if href else "",
                        "source": "Product Hunt"
                    })
            except:
                continue
        
        print(f"[PH] Encontrado {len(ias)} IAs")
        return ias
    except Exception as e:
        print(f"Erro scraping PH: {e}")
        return []

def scrape_github_trending():
    """Scrapa repositórios trending de IA no GitHub"""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        url = "https://github.com/trending"
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, "html.parser")
        
        ias = []
        for item in soup.find_all("article", class_="Box-row")[:10]:
            try:
                name_elem = item.find("h2")
                desc_elem = item.find("p", class_="col-9")
                link_elem = name_elem.find("a") if name_elem else None

                if name_elem and link_elem:
                    href = link_elem.get("href", "").strip("/")
                    name = href.replace("/", " / ")
                    desc = desc_elem.text.strip() if desc_elem else "Sem descrição"
                    url = f"https://github.com/{href}"
                    
                    ias.append({
                        "name": name,
                        "description": desc,
                        "url": url,
                        "source": "GitHub Trending"
                    })
            except:
                continue
        
        print(f"[GH] Encontrado {len(ias)} IAs")
        return ias
    except Exception as e:
        print(f"Erro scraping GH: {e}")
        return []

# ============= ANÁLISE GEMINI =============
def analyze_with_gemini(name, description):
    """Analisa IA com Gemini"""
    prompt = f"""Analise esta IA e responda APENAS em JSON (sem markdown):

Nome: {name}
Descrição: {description}

JSON:
{{"funcionalidade": "resumo 1-2 frases", "aplicabilidade": "casos de uso separados por vírgula", "categoria": "uma categoria curta, ex: Ferramentas de dev, Produtividade, Automação, Segurança, Dados, Mídia, Educação", "score": número 0-10, "confianca": número 0-100}}"""

    try:
        response = model.generate_content(prompt)
        text = response.text.strip()

        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]

        data = json.loads(text)
        return data
    except Exception as e:
        print(f"Erro Gemini {name}: {e}")
        return {"funcionalidade": "Erro", "aplicabilidade": "N/A", "categoria": "N/A", "score": 0, "confianca": 0}

# ============= MAIN =============
def main():
    print("🤖 IA Tracker - Fase 2\n")
    
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY não definida!")
        return
    
    init_db()
    
    print("📡 Scraping...\n")
    ias_ph = scrape_product_hunt()
    ias_gh = scrape_github_trending()
    ias_hn = scrape_hacker_news()

    todas_ias = ias_ph + ias_gh + ias_hn
    print(f"\n✅ Total: {len(todas_ias)} IAs\n")
    
    print("🔍 Analisando...\n")
    for ia in todas_ias:
        print(f"  → {ia['name']}")
        analysis = analyze_with_gemini(ia['name'], ia['description'])
        
        save_ia(
            name=ia['name'],
            desc=ia['description'],
            url=ia['url'],
            source=ia['source'],
            funcionalidade=analysis.get('funcionalidade', 'N/A'),
            aplicabilidade=analysis.get('aplicabilidade', 'N/A'),
            score=analysis.get('score', 0),
            confianca=analysis.get('confianca', 0),
            categoria=analysis.get('categoria', 'Geral')
        )
        time.sleep(13)  # ponytail: free tier do gemini-2.5-flash é 5 req/min; subir se trocar de plano

    print("\n✅ Salvo em ia_tracker.db")

if __name__ == "__main__":
    main()
