import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
output = root.parent / "coc_clean_project.zip"

cmd = ["git", "archive", "-o", str(output), "HEAD"]
subprocess.run(cmd, cwd=root, check=True)

size_mb = output.stat().st_size / (1024 * 1024)
print(f"Clean project zip exported to: {output}")
print(f"Total zip size: {size_mb:.2f} MB (Ready for WhatsApp)")
