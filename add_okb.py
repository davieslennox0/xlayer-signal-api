with open("index.html") as f:
    content = f.read()

old = '''    <div class="ticker-item">
      <div class="ticker-symbol">BROKER WALLET</div>'''

new = '''    <div class="ticker-item">
      <div class="ticker-symbol">OKB / USD</div>
      <div class="ticker-price" id="okb-price">—</div>
      <div class="ticker-change" id="okb-conf">loading...</div>
    </div>
    <div class="ticker-item">
      <div class="ticker-symbol">BROKER WALLET</div>'''

content = content.replace(old, new)
with open("index.html", "w") as f:
    f.write(content)
print("Done")
