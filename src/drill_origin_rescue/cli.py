"""Actual fabrication files to a protected review draft packet."""
import argparse
import hashlib
import sys
import re
import warnings
from pathlib import Path
from gerbonara import ExcellonFile
from gerbonara.cam import FileSettings
from gerbonara.utils import MM
from .parser import load
from .solver import solve, InputError
from .output import report_files, zip_bytes


def run(copper, drill, out, minimum=4, coverage=0.8, tolerance=0.02):
    out = Path(out)
    if out.exists():
        raise InputError("Output directory already exists. Choose a new directory.")
    report, pads, holes, files = None, [], [], {}
    inputs = {}
    for label, path in (("copper", Path(copper)), ("drill", Path(drill))):
        if not path.is_file() or path.stat().st_size > 5*1024*1024:
            raise InputError("Input is missing or exceeds the 5 MiB limit.")
        inputs[label] = {"name": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
    try:
        _, drill_raw, pads, holes, parsed = load(Path(copper), Path(drill))
        report = solve(pads, holes, minimum, coverage, tolerance)
        if report["status"] == "recovered":
            parsed.offset(*report["translation_mm"], unit=MM)
            corrected = parsed.write_to_bytes(settings=FileSettings(unit=MM, zeros=None, number_format=(3, 6)), drop_comments=False).replace(b"\r\n", b"\n")
            original_lines = drill_raw.decode("ascii").replace("\r\n", "\n").replace("\r", "\n").split("\n")
            full_hits = [(i, re.fullmatch(r"\s*X([+-]?\d+\.\d+)Y([+-]?\d+\.\d+)(\s*(?:;.*)?)", line)) for i,line in enumerate(original_lines)]
            full_hits = [(i,m) for i,m in full_hits if m]
            if len(full_hits) == len(holes):
                unit_scale = 25.4 if re.search(r"^INCH(?:,[LT]Z)?\s*$", drill_raw.decode("ascii"), re.M) else 1.0
                for (line_index, match), hole in zip(full_hits, holes):
                    original_lines[line_index] = f"X{(hole['x']+report['translation_mm'][0])/unit_scale:.9f}Y{(hole['y']+report['translation_mm'][1])/unit_scale:.9f}" + match.group(3)
                corrected = ("\n".join(original_lines).rstrip("\n")+"\n").encode("ascii")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                check = ExcellonFile.from_string(corrected.decode("ascii"))
            if any(not str(w.message).endswith("G90 header statement found after end of header") and 'Using implicit number format from bare "INCH" statement.' not in str(w.message) for w in caught):
                raise InputError("Corrected file reparse produced an unsupported interpretation warning.")
            original_tools = [(h["diameter"], h.get("plated")) for h in holes]
            new_tools = [(obj.tool.unit.convert_to(MM, obj.tool.diameter), obj.plated) for obj in check.objects]
            if len(check.objects) != len(holes) or any(abs(a[0]-b[0]) > 1e-6 or a[1] != b[1] for a,b in zip(original_tools,new_tools)):
                raise InputError("Corrected file reparse did not preserve drill count, diameters and plating metadata.")
            for before, after in zip(holes, check.objects):
                if abs(after.unit.convert_to(MM, after.x)-before["x"]-report["translation_mm"][0]) > 1e-6 or abs(after.unit.convert_to(MM, after.y)-before["y"]-report["translation_mm"][1]) > 1e-6:
                    raise InputError("Corrected file reparse did not preserve the uniform translation.")
            files["corrected-copy.drl"] = corrected
    except InputError as error:
        report = {"format": "drill-origin-rescue-report/1", "status": "invalid", "reason": str(error), "translation_mm": None, "matches": [], "notice": "Invalid or unsupported input. No corrected file was created."}
    report["inputs"] = inputs
    report["output_drill_sha256"] = hashlib.sha256(files["corrected-copy.drl"]).hexdigest() if "corrected-copy.drl" in files else None
    files.update(report_files(report, pads, holes))
    packet = zip_bytes(files)
    files["review-packet.zip"] = packet
    out.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        with (out/name).open("xb") as handle:
            handle.write(raw)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Infer only a well-supported uniform drill translation and produce a review draft.")
    parser.add_argument("--version", action="version", version="0.1.0")
    parser.add_argument("copper"); parser.add_argument("drill"); parser.add_argument("--out", required=True)
    parser.add_argument("--min-matches", type=int, default=4); parser.add_argument("--min-coverage", type=float, default=0.8); parser.add_argument("--tolerance-mm", type=float, default=0.02)
    args = parser.parse_args(argv)
    try:
        report = run(args.copper, args.drill, args.out, args.min_matches, args.min_coverage, args.tolerance_mm)
        print(f"{report['status']}: {report['reason']}")
        return 2 if report["status"] == "invalid" else 0
    except (InputError, OSError) as error:
        print(f"Input/output error: {error}", file=sys.stderr); return 2
    except KeyboardInterrupt:
        print("Cancelled. Discard an incomplete new output folder before retrying.", file=sys.stderr); return 130


if __name__ == "__main__":
    raise SystemExit(main())
