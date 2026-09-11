import re
from pathlib import Path
import requests

data_dir = Path("C:/COC/data")
data_dir.mkdir(parents=True, exist_ok=True)

instances = ["A-n32-k5", "A-n33-k5", "B-n31-k5"]

# First check PyVRP repository
for name in list(instances):
    url = f"https://raw.githubusercontent.com/PyVRP/vrplib/main/tests/data/{name}.vrp"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200 and "NODE_COORD_SECTION" in r.text:
            out_file = data_dir / f"{name}.vrp"
            out_file.write_text(r.text, encoding="utf-8")
            print(f"Downloaded {name} from {url} ({len(r.text)} bytes)")
            instances.remove(name)
    except Exception as e:
        print(f"Failed {url}: {e}")

if not instances:
    print("All instances downloaded successfully!")
    exit(0)

print(f"Remaining instances to fetch: {instances}")

# Search common GitHub repos containing CVRPLIB instances
known_urls = [
    "http://vrp.atd-lab.inf.puc-rio.br/media/com_vrp/instances/A/A-n33-k5.vrp",
    "http://vrp.galgos.inf.puc-rio.br/media/com_vrp/instances/A/A-n33-k5.vrp",
    "https://raw.githubusercontent.com/PyVRP/PyVRP/main/tests/data/A-n33-k5.vrp",
    "https://raw.githubusercontent.com/chkwon/CVRPLIB.jl/master/data/Augerat_1995/A-n33-k5.vrp",
    "https://raw.githubusercontent.com/alberto-santini/cvrplib/master/cvrplib/data/A/A-n33-k5.vrp",
    "https://raw.githubusercontent.com/tum-ens/cvrp-instances/master/A/A-n33-k5.vrp",
    "https://raw.githubusercontent.com/bcamath-ds/bip_benchmarks/master/cvrp/data/A-n33-k5.vrp",
    "https://raw.githubusercontent.com/coin-or/SYMPHONY/master/SYMPHONY/Datasets/VRP/A-n33-k5.vrp",
]

for url in known_urls:
    try:
        r = requests.get(url, timeout=10)
        print(f"{url} -> status {r.status_code}")
        if r.status_code == 200 and "NODE_COORD_SECTION" in r.text:
            out_file = data_dir / "A-n33-k5.vrp"
            out_file.write_text(r.text, encoding="utf-8")
            print(f"Downloaded A-n33-k5.vrp from {url} ({len(r.text)} bytes)")
            instances.remove("A-n33-k5")
            break
    except Exception as e:
        print(f"Error checking {url}: {e}")

# Check CVRPLIB page links
url_main = "http://vrp.atd-lab.inf.puc-rio.br/index.php/en/"
try:
    resp = requests.get(url_main, timeout=15)
    print("Fetched CVRPLIB homepage, size:", len(resp.text))
    # Find any links mentioning A-n
    for link in re.findall(r'href=["\']([^"\']+)["\']', resp.text):
        if "A-n" in link or "Augerat" in link or "vrp" in link:
            if "n33" in link or "Set A" in link or "set-a" in link.lower():
                print("Matched link:", link)
except Exception as e:
    print("Error:", e)
