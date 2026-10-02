"""Passive overlays and review reports, without user-controlled active markup."""
import csv
import html
import io
import json
import zipfile


def json_bytes(value):
    return (json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n").encode("utf-8")


def overlay(pads, holes, translation=(0, 0)):
    points = pads+holes
    if not points:
        return '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 40"><text x="5" y="20">No geometry available</text></svg>'
    xs = [p["x"] for p in points]+[h["x"]+translation[0] for h in holes]
    ys = [p["y"] for p in points]+[h["y"]+translation[1] for h in holes]
    x0, y0, w, h = min(xs)-3, min(ys)-3, max(xs)-min(xs)+6, max(ys)-min(ys)+6
    result = [f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Copper and drill overlay" viewBox="{x0} {-y0-h} {w} {h}"><rect x="{x0}" y="{-y0-h}" width="{w}" height="{h}" fill="#f4f8fc"/><g transform="scale(1,-1)">']
    for p in pads:
        if p["shape"] == "circle":
            result.append(f'<circle cx="{p["x"]}" cy="{p["y"]}" r="{p["width"]/2}" fill="#b66a20" opacity=".6"/>')
        else:
            result.append(f'<rect x="{p["x"]-p["width"]/2}" y="{p["y"]-p["height"]/2}" width="{p["width"]}" height="{p["height"]}" rx="{min(p["width"],p["height"])/2 if p["shape"]=="obround" else 0}" fill="#b66a20" opacity=".6"/>')
    for hole in holes:
        result.append(f'<circle cx="{hole["x"]}" cy="{hole["y"]}" r="{hole["diameter"]/2}" fill="none" stroke="#c04c5a" stroke-width=".12"/>')
        if translation != (0, 0) and translation != [0, 0]:
            result.append(f'<circle cx="{hole["x"]+translation[0]}" cy="{hole["y"]+translation[1]}" r="{hole["diameter"]/2}" fill="none" stroke="#067b88" stroke-width=".12"/>')
    return "".join(result)+"</g></svg>"


def report_files(report, pads, holes):
    rows = io.StringIO(newline="")
    writer = csv.writer(rows, lineterminator="\n")
    writer.writerow(["hole_index", "outcome", "x_mm", "y_mm", "diameter_mm", "pad_index", "residual_mm"])
    matches = {r["hole_index"]: r for r in report.get("matches", [])}
    for i, hole in enumerate(holes):
        row = matches.get(i, {})
        writer.writerow([i, "matched" if row else "unmatched_review", hole["x"], hole["y"], hole["diameter"], row.get("pad_index", ""), row.get("residual_mm", "")])
    after = overlay(pads, holes, report.get("translation_mm") or (0, 0))
    esc = lambda text: html.escape(str(text), quote=True)
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"><title>Drill Origin Rescue review</title><style>body{{font:16px system-ui;color:#183451;background:#f4f8fc;margin:32px}}img{{width:100%;max-height:550px}}.notice{{background:#fff0ce;padding:20px}}</style><h1>Drill Origin Rescue</h1><p class="notice">{esc(report['notice'])}</p><h2>{esc(report['status'].replace('_',' '))}</h2><p>{esc(report['reason'])}</p><p>Translation: {esc(report.get('translation_mm'))} mm. Matched: {len(report.get('matches',[]))}. Unmatched holes need review.</p><img src="after.svg" alt="Copper, original red drills and translated teal drills"><p>Load the corrected COPY alongside every original fabrication layer. Verify NPTH, tooling holes, board outline, slots and manufacturing requirements. The report does not certify manufacturing readiness.</p><a href="mailto:tianchaodaxing@gmail.com">Contact PANDAO</a></html>'''
    return {"review.json": json_bytes(report), "review.csv": rows.getvalue().encode(), "review.html": page.encode(), "before.svg": overlay(pads, holes).encode(), "after.svg": after.encode()}


def zip_bytes(files):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for name, raw in sorted(files.items()):
            info = zipfile.ZipInfo(name, (2020, 1, 1, 0, 0, 0)); info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, raw)
    return buf.getvalue()
