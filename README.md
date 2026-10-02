# Drill Origin Rescue

Diagnose Gerber/Excellon origin mismatches and recover **only a distinct, well-supported uniform XY translation**. Review the actual copper/drill overlay, inspect unmatched holes, and take a corrected copy into your fabrication viewer.

[Browser workspace](https://tianchaodaxing-beep.github.io/pandao-drill-origin-rescue/) · [Source](https://github.com/tianchaodaxing-beep/pandao-drill-origin-rescue) · [Contact](mailto:tianchaodaxing@gmail.com)

The original files remain untouched. An ambiguous pattern, incompatible geometry or unsupported file produces a review report, with no corrected drill file. The tool does not rotate, mirror, scale, guess units, infer geometry from tracks/regions, or certify manufacturing readiness.

## Quick start

Use Python **3.12 or later**. Download and extract the project source, then install in a virtual environment:

```sh
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate
python -m pip install .
```

The CLI uses the official Gerbonara 1.6.3 parser. Run real Gerber and Excellon exports in one command:

```sh
drill-origin-rescue copper.gbr drill.drl --out review-draft
# Equivalent module command:
python -m drill_origin_rescue copper.gbr drill.drl --out review-draft
```

The output directory must be new. Check `review.html` and `review.json`. A corrected `corrected-copy.drl` appears **only for `recovered` results**. The directory also contains `before.svg`, `after.svg`, `review.csv` and a complete `review-packet.zip`.

| Status | Meaning | Corrected file |
| --- | --- | --- |
| `already_aligned` | A distinct matching translation is within the tolerance of zero | None; keep the original |
| `recovered` | One distinct nonzero translation satisfies the evidence thresholds | A copy for review |
| `review_required` | Insufficient support, excessive unmatched hits, competing offsets or bounded processing limits | None |
| `invalid` | Invalid/unsupported file, unit/format problem, slots/routing, duplicate hits or invalid thresholds | None |

Exit `0` means a report was produced, including `review_required`. Exit `2` indicates invalid input or an input/output error. Exit `130` indicates cancellation. A filesystem failure or cancellation can leave an incomplete newly created directory; use another output directory before retrying. Existing directories and original bytes are protected.

## Evidence thresholds

Defaults are **4 unique matches**, **80% drill-hit coverage**, and **0.02 mm maximum residual**:

```sh
drill-origin-rescue copper.gbr drill.drl --out review-draft \
  --min-matches 4 --min-coverage 0.8 --tolerance-mm 0.02
```

Minimum matches must be an integer at least 3. Coverage is configurable from 0.5 to 1, and residual tolerance from 0.000001 to 0.1 mm. Lower coverage admits more unsupported holes; the recommended 0.8 default permits at most 20% unmatched round hits. NPTH/mechanical holes without copper remain unmatched and need individual inspection. The inferred translation applies to **all** round hits, including unmatched ones, because an origin shift affects the whole drill export. This does not prove that an unmatched hole is correctly positioned.

Candidate pads come only from dark, solid circle, rectangle and obround flashes. A pad's smaller dimension must exceed the hole diameter by at least 0.1 mm, must not exceed 3 times the hole diameter, and its aspect ratio must not exceed 2. Small SMD pads and incompatible flash sizes are excluded. These size gates do not prove that a candidate is plated through-hole copper; suitable SMD geometry can still resemble a drill pad.

The solver votes on compatible pad/hole offsets, evaluates nearby hypotheses, then requires one-to-one unique matches and strict residuals. A hole with multiple nearby candidate pads, or a pad claimed by multiple holes, does not count as a match. Exact duplicate drill locations are refused. An average translation is refined from the evidence; no per-hole adjustment occurs.

Competing translations with sufficient support near the best match count block recovery, even when one candidate has a higher count. Repeated grids, symmetrical arrangements and periodic patterns can therefore produce manual-review results. This is deliberate: the tool does not silently choose an origin based on file ordering or the smallest shift.

## Supported CLI profile

- ASCII Gerber and Excellon files, up to **5 MiB each**.
- Gerber declares one explicit absolute `FS` format (`L` or `T` suppression) and one explicit `MO` MM/IN unit. Dark tracks/regions may be parsed but are ignored for candidate matching. Only solid C/R/O flash apertures become candidates.
- Clear/image-negative polarity, step-and-repeat, aperture blocks/macros, includes, transforms, incremental coordinates and legacy unit switches are refused. Holed flash apertures are refused.
- Excellon declares `M48`, `M30` and one explicit `METRIC` or `INCH` unit. Absolute round hits may use explicit decimal coordinates. Integer coordinates require an explicit `;FILE_FORMAT=i:d` declaration; units and formats are not guessed.
- Slots, milling/routing, repeats and incremental drilling are refused. **No corrected file is produced for a file containing slots**, even if some round holes could be aligned.
- Extended feed/speed tool parameters are refused rather than discarded. Diameters and plating metadata are checked by reparsing the output. Complete decimal XY inputs are rewritten in place within a copy, preserving original unit declarations, tool identifiers, tool definitions and comments. Other supported coordinate forms are reserialized by Gerbonara and verified; their whitespace and tool numbering may change.
- Unknown parser warnings block recovery. The known absolute `G90` placement warning is harmless and accepted. The known bare `INCH` implicit-integer-format warning is accepted **only when every actual coordinate is explicitly decimal**; that integer format cannot affect those coordinates.
- At most **4000 candidate flashes**, **2000 round hits**, **300000 candidate pairs/bins**, and **500 supported offset hypotheses**. Limits produce explicit review/invalid outcomes. Memory is bounded; large layers should be inspected manually or exported as a smaller relevant layer.

The translation and all reporting coordinates use millimetres, after explicitly declared source units are normalized. Input/output SHA-256 fingerprints are stored in JSON. No accounts, uploads, external includes or remote parsing services are used.

## Browser profile

The browser actually parses uploaded fabrication files and runs its own matching solver locally. Its strict profile is narrower than the CLI:

| Input | Accepted syntax |
| --- | --- |
| Gerber | `G04` comments; one `FSLAXidYid` absolute leading-zero format with matching X/Y digits; one `MOMM`/`MOIN`; solid `ADDnC,d`, `ADDnR,wXh`, `ADDnO,wXh`; optional `LPD`; standalone aperture selections; complete absolute `X...Y...D03` flashes or `D02` moves; final `M02` |
| Excellon | `M48`; comments; one `METRIC`/`INCH` with optional `LZ`/`TZ`; decimal `TnCd` tool definitions; `G90`/`G05`; `%` header terminator; standalone tool selections; complete **decimal** `X...Y...` round hits; final `M30` |

Everything else is rejected with an actionable message. The browser does not infer coordinates from tracks, regions or omitted XY values. Integer Excellon coordinates, slots, routing and unsupported parameters are refused. Units/format declarations must appear before coordinate use. Use the CLI for its broader explicitly supported profile.

The buttons invoke real file selection, not an upload service. The Before/After controls show the actual accepted geometry and the inferred offset vector. The downloaded corrected copy preserves browser-profile tool definitions and comments; it is reparsed before download. A packet contains the corrected copy when available, both SVG overlays and HTML/CSV/JSON reports. The table shows up to 200 filtered rows; reports contain every hole.

Serve the static site over localhost HTTP or HTTPS for local use:

```sh
python -m http.server 8080 --directory docs
```

Open `http://localhost:8080`. The sample buttons load only bundled synthetic files from the site's origin. Uploaded files never leave the browser. Hashing requires a secure context such as HTTPS or localhost.

## Review before fabrication

Open the corrected **copy** with every original copper layer, mask, board outline and mechanical layer in your normal fabrication viewer. Inspect unmatched holes, NPTH/tooling holes, drill sizes, plating, pad annuli, connectivity and manufacturing requirements. A pad-center match does not validate these other layers or design intent.

Gerber dark flashes can be SMD or other geometry. Geometry alone cannot prove the correct drilling purpose. Recovered means the stated translation evidence passed, not that a board is safe to manufacture. No commercial CAD application certification or market-size/adoption claim is made.

## Samples and tests

All public samples are synthetic coordinate-based exports generated by `scripts/generate_samples.py`, independently of either parser. `docs/samples/expected.json` records their known pad coordinates, offset and outcomes:

- `copper.gbr` + `drill-offset.drl`: 7 asymmetric drill/pad pairs, 1 unmatched mechanical hole, extra small SMD flashes, known translation `(-5, -7)` mm.
- `aligned-drill.drl`: the same geometry already aligned.
- `ambiguous-copper.gbr` + `ambiguous-drill.drl`: repeated grid with competing offsets; review required.
- `missing-units.drl`: invalid without guessed units.
- `slots.drl`: refused without a corrected output.
- `sample-inputs.zip` and `example-review-packet.zip`: downloadable real sample inputs and output artifacts.

Tests cover actual parsing, corrected output reparse, unchanged inputs, tool definitions, diameters, plating checks, existing-output protection, known benign warnings, unknown/unsupported syntax, offsets, rotation/mirroring/scaling rejection, insufficient coverage, SMD rejection, ambiguity, one-to-one matching, finite limits, deterministic artifacts, SVG XML and LF-only packets. Python/browser solver equivalence is checked over 50 independently generated noisy asymmetric boards.

```sh
python -m pip install pytest==8.4.2
python -m pytest -q
node tests/test_core.cjs
python scripts/generate_samples.py
python -m pip wheel . --no-deps --wheel-dir dist
```

CI workflow `Test` targets Windows/Linux with Python 3.12/3.14 and Node 22. See the repository's Actions page for actual remote-run status. This project does not claim tests inside commercial CAD tools.

## License and dependencies

Own application implementation is **MIT** licensed. The CLI pins **Gerbonara 1.6.3**, Apache-2.0 licensed, as a separately installed dependency. No Gerbonara binary/source is bundled. The browser parser, solver and bounded ZIP writer are original project code and require no third-party browser library. See [THIRD_PARTY.md](THIRD_PARTY.md).

## Contact

For project-specific export rules, batch integration or supervised fabrication review, contact PANDAO at [tianchaodaxing@gmail.com](mailto:tianchaodaxing@gmail.com).
