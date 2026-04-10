with open("index.html") as f:
    content = f.read()

old = "// Init\nfetchPreview('BTC','btc-price','btc-conf');"
new = """async function fetchActivity() {
  try {
    const r = await fetch(`${API}/activity`);
    const d = await r.json();
    const items = d.activity || [];
    if (!items.length) return;
    const feed = document.getElementById('trade-feed');
    feed.innerHTML = items.reverse().map(t => {
      const time = new Date(t.timestamp * 1000).toLocaleTimeString();
      const statusClass = t.status === 'success' ? 'trade-status-ok' : 'trade-status-wait';
      return `<div class="trade-item">
        <span class="trade-asset">${t.asset}</span>
        <span class="trade-size">${t.agent_id}</span>
        <span class="${statusClass}">${t.status}</span>
        <span class="trade-time">${time}</span>
      </div>`;
    }).join('');
  } catch(e) {}
}

// Init
fetchPreview('BTC','btc-price','btc-conf');"""

content = content.replace(old, new)

# Add fetchActivity to the interval
content = content.replace(
    "setInterval(()=>{\n  fetchPreview('BTC','btc-price','btc-conf');",
    "fetchActivity();\nsetInterval(()=>{\n  fetchPreview('BTC','btc-price','btc-conf');\n  fetchActivity();"
)

with open("index.html", "w") as f:
    f.write(content)
print("Done")
