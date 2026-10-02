"""Independent coordinate-based Gerber/Excellon sample exports with known offsets."""
import json
from pathlib import Path
import sys
import tempfile
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/"src"))
from drill_origin_rescue.cli import run
from drill_origin_rescue.output import zip_bytes

POINTS = [(2, 3), (9, 3), (16, 6), (5, 12), (14, 15), (24, 9), (22, 20)]


def gerber(points):
    lines = ["G04 Synthetic asymmetric board, dimensions in millimeters*", "%FSLAX36Y36*%", "%MOMM*%", "%ADD10C,1.800*%", "%ADD11R,1.800X2.400*%", "%ADD12O,2.200X1.800*%", "%ADD13C,0.400*%", "%LPD*%"]
    for i, (x, y) in enumerate(points):
        lines += [f"D{10+i%3}*", f"X{round(x*1000000):09d}Y{round(y*1000000):09d}D03*"]
    lines += ["D13*", "X011000000Y009000000D03*", "X012000000Y009000000D03*", "M02*"]
    return "\n".join(lines)+"\n"


def drill(points, dx=0, dy=0, extras=True):
    lines = ["M48", ";FILE_FORMAT=3:6", "METRIC", "T01C0.800", "T02C1.500", "G90", "%", "T01"]
    lines += [f"X{x+dx:.6f}Y{y+dy:.6f}" for x, y in points]
    if extras:
        lines += ["T02", f"X{40+dx:.6f}Y{30+dy:.6f}"]
    return "\n".join(lines+["M30"])+"\n"


def generate(folder):
    folder.mkdir(parents=True, exist_ok=True)
    grid = [(x, y) for x in (0, 5, 10) for y in (0, 5, 10)]
    contents = {"copper.gbr": gerber(POINTS), "drill-offset.drl": drill(POINTS, 5, 7), "aligned-drill.drl": drill(POINTS),
                "ambiguous-copper.gbr": gerber(grid), "ambiguous-drill.drl": drill([(0,0),(0,5),(5,0),(5,5)], extras=False),
                "missing-units.drl": drill(POINTS).replace("METRIC\n", ""), "slots.drl": drill(POINTS).replace("M30", "X1.000000Y1.000000G85X3.000000Y1.000000\nM30")}
    for name, value in contents.items():
        (folder/name).write_text(value, encoding="ascii", newline="\n")
    expected = {"synthetic": True, "known_pad_centers_mm": POINTS, "shifted_translation_mm": [-5, -7], "round_hits": 8, "matched_hits": 7, "unmatched_hits": 1, "expected_statuses": {"drill-offset.drl": "recovered", "aligned-drill.drl": "already_aligned", "ambiguous-drill.drl": "review_required", "missing-units.drl": "invalid", "slots.drl": "invalid"}}
    (folder/"expected.json").write_text(json.dumps(expected, indent=2)+"\n", encoding="utf-8", newline="\n")
    output = folder/"example-output"
    output.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        packet = Path(temporary)/"packet"
        run(folder/"copper.gbr", folder/"drill-offset.drl", packet)
        for file in packet.iterdir():
            (output/file.name).write_bytes(file.read_bytes())
    (folder/"sample-inputs.zip").write_bytes(zip_bytes({name:value.encode() for name,value in contents.items()}))
    (folder/"example-review-packet.zip").write_bytes((output/"review-packet.zip").read_bytes())
    return expected


if __name__ == "__main__":
    print(json.dumps(generate(Path(__file__).resolve().parents[1]/"docs"/"samples"), indent=2))
