with open("index.html") as f:
    content = f.read()

old = """async function fetchPreview(asset, priceId, confId) {
  try {
    const r = await fetch(`${API}/preview/${asset}`);
    const d = await r.json();
    if (d.price) {
      document.getElementById(priceId).textContent = `$${d.price.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
      const conf = d.confidence || 0;
      const el = document.getElementById(confId);
      el.textContent = `Confidence: ${conf.toFixed(1)}%`;
      el.className = `ticker-change ${conf>55?'up':conf<45?'down':''}`;
    }
  } catch(e) {}
}"""

new = """async function fetchPreview(asset, priceId, confId) {
  try {
    const r = await fetch(`https://min-api.cryptocompare.com/data/price?fsym=${asset}&tsyms=USD`);
    const d = await r.json();
    if (d.USD) {
      document.getElementById(priceId).textContent = `$${d.USD.toLocaleString('en-US',{minimumFractionDigits:2,maximumFractionDigits:2})}`;
      document.getElementById(confId).textContent = `Live price`;
      document.getElementById(confId).className = 'ticker-change up';
    }
  } catch(e) {}
}"""

content = content.replace(old, new)
with open("index.html", "w") as f:
    f.write(content)
print("Done")
