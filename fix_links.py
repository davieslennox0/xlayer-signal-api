with open("/var/www/alphaloop/index.html") as f:
    content = f.read()

old = '''      const time = new Date(t.timestamp * 1000).toLocaleTimeString();
      const statusClass = t.status === 'success' ? 'trade-status-ok' : 'trade-status-wait';
      return `<div class="trade-item">
        <span class="trade-asset">${t.asset}</span>
        <span class="trade-size">${t.agent_id}</span>
        <span class="${statusClass}">${t.status}</span>
        <span class="trade-time">${time}</span>
      </div>`;'''

new = '''      const time = new Date(t.timestamp * 1000).toLocaleTimeString();
      const statusClass = t.status === 'success' ? 'trade-status-ok' : 'trade-status-wait';
      const explorer = t.tx_hash ? `<a href="https://www.oklink.com/xlayer/tx/${t.tx_hash}" target="_blank" style="color:var(--amber);font-family:var(--mono);font-size:0.65rem;text-decoration:none">↗ tx</a>` : '';
      return `<div class="trade-item">
        <span class="trade-asset">${t.asset}</span>
        <span class="trade-size">${t.agent_id}</span>
        <span class="${statusClass}">${t.status}</span>
        ${explorer}
        <span class="trade-time">${time}</span>
      </div>`;'''

content = content.replace(old, new)
with open("/var/www/alphaloop/index.html", "w") as f:
    f.write(content)

# Update source too
with open("/root/xlayer/index.html", "w") as f:
    f.write(content)
print("Done")
