with open("index.html") as f:
    content = f.read()

# Replace API constant - empty string means relative, but we need absolute
# Use meta tag approach to allow mixed content - won't work
# Instead fetch activity from CryptoCompare won't work either
# Real fix: change API to use window.location aware URL
old = 'const API = "";'
new = 'const API = "http://108.61.91.153";'

content = content.replace(old, new)

# Add mixed content meta tag at top of head
old = '<meta charset="UTF-8">'
new = '<meta charset="UTF-8">\n<meta http-equiv="Content-Security-Policy" content="upgrade-insecure-requests">'

content = content.replace(old, new)

with open("index.html", "w") as f:
    f.write(content)
print("Done")
