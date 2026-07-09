#!/usr/bin/env python3
import sqlite3
import json
import os
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler

DB_PATH = "ia_tracker.db"

SRC_META = {
    "GitHub Trending": {"label": "GitHub", "cls": "src-github", "initials": "GI"},
    "Hacker News": {"label": "HN", "cls": "src-hn", "initials": "HN"},
    "Product Hunt": {"label": "PH", "cls": "src-ph", "initials": "PH"},
}
SOURCE_ORDER = ["GitHub Trending", "Hacker News", "Product Hunt"]


def relative_age(ts_str):
    try:
        dt = datetime.strptime(ts_str.split(".")[0], "%Y-%m-%d %H:%M:%S")
    except (ValueError, AttributeError):
        return ""
    hours = (datetime.now() - dt).total_seconds() / 3600
    if hours < 1:
        return "agora"
    if hours < 24:
        return f"há {int(hours)}h"
    return f"há {int(hours // 24)}d"


def get_ias():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM ias ORDER BY score DESC, data_coleta DESC")
    rows = c.fetchall()
    conn.close()

    ias = []
    for row in rows:
        # colunas: id, name, description, url, source, funcionalidade, aplicabilidade, score, confianca, data_coleta
        ias.append({
            "name": row[1],
            "desc": row[5] or row[2] or "",
            "url": row[3],
            "source": row[4],
            "apply": row[6] or "",
            "score": row[7] or 0,
            "conf": row[8] or 0,
            "age": relative_age(str(row[9])),
        })
    return ias


PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<title>IA Tracker</title>
<style>
  :root {
    --bg: #efe9da; --text: #241f18; --text-dim: #6b6152; --border: #e5dcc3;
    --accent: #c98f1d;
    --mono: ui-monospace, "SF Mono", "Roboto Mono", Menlo, Consolas, monospace;
    --sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    --rounded: ui-rounded, "SF Pro Rounded", var(--sans);
  }
  * { box-sizing: border-box; }
  body { margin: 0; background: var(--bg); color: var(--text); font-family: var(--sans); padding: 28px 20px 64px; }
  .wrap { max-width: 1100px; margin: 0 auto; background: linear-gradient(135deg, #d9d7e2 0%, #f2ecdd 55%, #f6dfa0 100%);
    border-radius: 28px; padding: 28px; }

  .intro h1 { font-size: 1.6rem; margin: 0 0 6px; font-family: var(--rounded); }
  .intro p { margin: 0 0 20px; color: var(--text-dim); font-size: 0.9rem; }

  .controls { display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 22px; }
  .search { flex: 1; min-width: 180px; font-family: var(--sans); font-size: 0.86rem; background: #fff;
    border: 1px solid var(--border); border-radius: 20px; padding: 8px 14px; color: var(--text); outline: none; }
  .search:focus { border-color: var(--accent); }
  .search::placeholder { color: var(--text-dim); }
  .pills { display: flex; gap: 6px; flex-wrap: wrap; }
  .pill-btn { font-family: var(--sans); font-size: 0.78rem; font-weight: 600; cursor: pointer; background: #fff;
    border: 1px solid var(--border); color: var(--text-dim); border-radius: 20px; padding: 6px 12px;
    display: flex; align-items: center; gap: 6px; }
  .pill-btn.active { background: var(--accent); color: var(--text); border-color: var(--accent); }
  .pill-btn .n { font-family: var(--mono); opacity: 0.75; }

  .group { margin-bottom: 26px; }
  .group-head { display: flex; align-items: baseline; gap: 8px; margin-bottom: 10px; border-bottom: 1px dotted var(--text-dim); padding-bottom: 8px; }
  .group-title { font-size: 0.8rem; font-weight: 700; text-transform: uppercase; letter-spacing: 0.05em; }
  .group-count { font-family: var(--mono); font-size: 0.74rem; color: var(--text-dim); }

  .cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr)); gap: 16px; align-items: start; }

  /* .card é só um wrapper "neutro" no grid — precisa ficar livre de transform/filter/backdrop-filter,
     senão vira containing block e quebra o position:fixed do .tile-detail (isso já me mordeu uma vez aqui) */
  .card { position: relative; text-decoration: none; color: inherit; cursor: default; }

  .tile-face-bg { position: relative; background: rgba(255,255,255,0.55); border: 1px solid var(--border); border-radius: 28px;
    padding: 22px 18px; display: flex; flex-direction: column; align-items: center; text-align: center;
    backdrop-filter: blur(14px); -webkit-backdrop-filter: blur(14px);
    box-shadow: 0 4px 18px rgba(150,120,40,0.1);
    transition: box-shadow .3s, border-color .2s; }
  .card:hover .tile-face-bg, .card:focus-within .tile-face-bg { box-shadow: 0 10px 24px rgba(150,110,30,0.18); border-color: var(--accent); }
  .card.top .tile-face-bg { box-shadow: 0 0 0 1.5px var(--accent) inset; }

  /* fundo escurecido atrás do card em foco, só aparece durante o hover */
  .card::before {
    content: ""; position: fixed; inset: 0; background: rgba(30,24,10,0.28); backdrop-filter: blur(3px);
    opacity: 0; pointer-events: none; transition: opacity .3s; z-index: 40;
  }
  .card:hover::before, .card:focus-within::before { opacity: 1; }

  .top-flag { position: absolute; top: -1px; right: 20px; background: var(--accent); color: #241f18; font-family: var(--mono);
    font-size: 0.62rem; font-weight: 700; letter-spacing: 0.04em; padding: 2px 7px; border-radius: 0 0 10px 10px; text-transform: uppercase; }

  .avatar { width: 56px; height: 56px; border-radius: 50%; display: flex; align-items: center; justify-content: center;
    background: color-mix(in srgb, var(--accent) 22%, transparent); color: var(--accent); font-family: var(--rounded);
    font-weight: 700; font-size: 1rem; flex-shrink: 0; }

  .tile-face { display: flex; flex-direction: column; align-items: center; gap: 10px; transition: opacity .25s; }
  .card:hover .tile-face, .card:focus-within .tile-face { opacity: 0.3; }
  .card-name { font-family: var(--rounded); font-weight: 700; font-size: 1rem; margin: 0; line-height: 1.3;
    display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

  .score-chip { font-family: var(--mono); font-weight: 700; font-size: 0.76rem; padding: 3px 10px; border-radius: 999px;
    background: color-mix(in srgb, var(--accent) 16%, transparent); color: var(--accent); }

  /* detalhe voa pro centro da tela e amplia — texto ganha espaço em vez de ficar espremido na coluna */
  .tile-detail {
    position: fixed; top: 50%; left: 50%; width: min(460px, 88vw); max-height: 78vh; overflow-y: auto;
    background: rgba(255,255,255,0.92); backdrop-filter: blur(18px); -webkit-backdrop-filter: blur(18px);
    border: 1px solid var(--border); border-radius: 28px; padding: 26px; text-align: left;
    box-shadow: 0 30px 60px rgba(60,45,10,0.28);
    transform: translate(-50%, -50%) scale(0.82); opacity: 0; pointer-events: none; z-index: 50;
    transition: transform .4s cubic-bezier(.16,1,.3,1), opacity .3s;
  }
  .card:hover .tile-detail, .card:focus-within .tile-detail { transform: translate(-50%, -50%) scale(1); opacity: 1; pointer-events: auto; }

  .detail-head { display: flex; align-items: center; gap: 12px; margin-bottom: 14px; }
  .detail-head .avatar { width: 44px; height: 44px; font-size: 0.85rem; }
  .detail-head-text { flex: 1; min-width: 0; }
  .detail-name { font-family: var(--rounded); font-weight: 700; font-size: 1.1rem; margin: 0 0 6px; line-height: 1.3; }

  .src-badge { font-family: var(--mono); font-size: 0.64rem; padding: 2px 9px; border-radius: 20px; text-transform: uppercase;
    letter-spacing: 0.03em; }
  .src-github { background: color-mix(in srgb, var(--accent) 14%, transparent); color: var(--accent); }
  .src-hn { background: color-mix(in srgb, #b3503f 16%, transparent); color: #b3503f; }
  .src-ph { background: color-mix(in srgb, #5c8a55 16%, transparent); color: #5c8a55; }

  .card-desc { font-size: 0.88rem; color: var(--text-dim); line-height: 1.6; margin: 0 0 12px; }
  .apply { font-size: 0.82rem; line-height: 1.55; margin: 0; }
  .apply b { color: var(--text-dim); font-weight: 600; font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.04em; display: block; margin-bottom: 3px; }

  .card-foot { display: flex; align-items: center; justify-content: space-between; gap: 10px; padding-top: 14px; margin-top: 14px; border-top: 1px dotted var(--border); }
  .conf { font-family: var(--mono); font-size: 0.74rem; color: var(--text-dim); }
  .open-link { font-family: var(--sans); font-size: 0.82rem; font-weight: 600; color: var(--accent); text-decoration: none; white-space: nowrap; }
  .open-link:hover { text-decoration: underline; }

  .empty { text-align: center; padding: 40px 20px; color: var(--text-dim); font-size: 0.86rem; display: none; }
</style>
</head>
<body>
<div class="wrap">
  <div class="intro">
    <h1>IA Tracker</h1>
    <p>__TOTAL__ sinais coletados · GitHub Trending, Hacker News e Product Hunt.</p>
  </div>

  <div class="controls">
    <input class="search" id="search" type="text" placeholder="Buscar por nome...">
    <div class="pills" id="pills">
      <button class="pill-btn active" data-src="all">Todos <span class="n">__TOTAL__</span></button>
      __SOURCE_PILLS__
    </div>
  </div>

  <div id="groups"></div>
  <div class="empty" id="empty">Nenhum resultado — tenta outra busca ou fonte.</div>
</div>

<script>
  const DATA = __DATA_JSON__;
  const SRC_META = __SRC_META_JSON__;
  const SOURCE_ORDER = __SOURCE_ORDER_JSON__;

  const search = document.getElementById('search');
  const pills = document.querySelectorAll('.pill-btn');
  const groupsEl = document.getElementById('groups');
  const empty = document.getElementById('empty');
  let activeSrc = 'all';

  function esc(s) {
    return String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }

  function cardHTML(it) {
    const meta = SRC_META[it.source] || { label: it.source, cls: 'src-github', initials: it.source.slice(0, 2).toUpperCase() };
    const isTop = it.score >= 9;
    return `
      <div class="card ${isTop ? 'top' : ''}" tabindex="0">
        <div class="tile-face-bg">
          ${isTop ? '<span class="top-flag">Top</span>' : ''}
          <div class="tile-face">
            <div class="avatar">${esc(meta.initials)}</div>
            <p class="card-name">${esc(it.name)}</p>
            <span class="score-chip">${it.score.toFixed(1)}</span>
          </div>
        </div>
        <div class="tile-detail">
          <div class="detail-head">
            <div class="avatar">${esc(meta.initials)}</div>
            <div class="detail-head-text">
              <p class="detail-name">${esc(it.name)}</p>
              <span class="src-badge ${meta.cls}">${esc(meta.label)}</span>
            </div>
            <span class="score-chip">${it.score.toFixed(1)}</span>
          </div>
          <p class="card-desc">${esc(it.desc)}</p>
          <p class="apply"><b>Aplicável em</b>${esc(it.apply)}</p>
          <div class="card-foot">
            <span class="conf">confiança ${it.conf}% · ${esc(it.age)}</span>
            <a class="open-link" href="${esc(it.url)}" target="_blank" rel="noopener">Abrir ↗</a>
          </div>
        </div>
      </div>`;
  }

  function render() {
    const q = search.value.trim().toLowerCase();
    const filtered = DATA.filter(it =>
      (activeSrc === 'all' || it.source === activeSrc) &&
      (!q || it.name.toLowerCase().includes(q))
    );

    empty.style.display = filtered.length === 0 ? 'block' : 'none';

    const groupsMap = {};
    filtered.forEach(it => { (groupsMap[it.source] = groupsMap[it.source] || []).push(it); });
    const groupKeys = Object.keys(groupsMap).sort((a, b) => SOURCE_ORDER.indexOf(a) - SOURCE_ORDER.indexOf(b));

    groupsEl.innerHTML = groupKeys.map(k => `
      <div class="group">
        <div class="group-head"><span class="group-title">${esc(k)}</span><span class="group-count">${groupsMap[k].length}</span></div>
        <div class="cards">${groupsMap[k].map(cardHTML).join('')}</div>
      </div>
    `).join('');
  }

  search.addEventListener('input', render);
  pills.forEach(p => p.addEventListener('click', () => {
    pills.forEach(x => x.classList.remove('active'));
    p.classList.add('active');
    activeSrc = p.dataset.src;
    render();
  }));

  render();
</script>
</body>
</html>
"""


def generate_html():
    ias = get_ias()
    counts = {}
    for it in ias:
        counts[it["source"]] = counts.get(it["source"], 0) + 1

    source_pills = "\n      ".join(
        f'<button class="pill-btn" data-src="{src}">{SRC_META[src]["label"]} <span class="n">{counts.get(src, 0)}</span></button>'
        for src in SOURCE_ORDER if counts.get(src, 0) > 0
    )

    data_json = json.dumps(ias, ensure_ascii=False).replace("</script", "<\\/script")

    html = PAGE_TEMPLATE
    html = html.replace("__TOTAL__", str(len(ias)))
    html = html.replace("__SOURCE_PILLS__", source_pills)
    html = html.replace("__DATA_JSON__", data_json)
    html = html.replace("__SRC_META_JSON__", json.dumps(SRC_META, ensure_ascii=False))
    html = html.replace("__SOURCE_ORDER_JSON__", json.dumps(SOURCE_ORDER, ensure_ascii=False))
    return html


if __name__ == "__main__":
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(generate_html())

    print("✅ Dashboard: http://localhost:8000")
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    server = HTTPServer(("localhost", 8000), SimpleHTTPRequestHandler)
    print("Pressione Ctrl+C para parar")
    server.serve_forever()
