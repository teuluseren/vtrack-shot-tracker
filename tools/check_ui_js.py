from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
viewer = (ROOT / "review" / "shot_review.py").read_text(encoding="utf-8")
tree = ast.parse(viewer)
html = None
for node in tree.body:
    if isinstance(node, ast.Assign) and any(
        isinstance(target, ast.Name) and target.id == "HTML" for target in node.targets
    ):
        html = ast.literal_eval(node.value)
        break
if not isinstance(html, str):
    raise SystemExit("Could not locate embedded HTML")
js = html.split("<script>", 1)[1].split("</script>", 1)[0]
out = ROOT / "build" / ".ui-check.js"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(js, encoding="utf-8")
print(out)
