import re
from pathlib import Path
import requests

resp = requests.get("http://vrp.atd-lab.inf.puc-rio.br/index.php/en/", timeout=15)
text = resp.text

# Find all links
links = re.findall(r'href=["\']([^"\']+)["\']', text)
vrp_links = [l for l in links if "vrp" in l.lower() or "download" in l.lower() or "instance" in l.lower() or "augerat" in l.lower()]
Path("C:/COC/data/scraped_links.txt").write_text("\n".join(vrp_links), encoding="utf-8")
print(f"Total links: {len(links)}, filtered: {len(vrp_links)}")

# Search for A-n33 anywhere in text
pos = text.find("A-n33")
if pos != -1:
    print("Found A-n33 in text around:", repr(text[pos-100:pos+200]))
else:
    print("A-n33 NOT in text directly")
