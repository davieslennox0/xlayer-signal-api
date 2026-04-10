with open("index.html") as f:
    content = f.read()
content = content.replace('http://108.61.91.153', 'https://alphaloop.duckdns.org')
with open("index.html", "w") as f:
    f.write(content)
print("Done")
