"""Finite translation voting followed by strict one-to-one geometric checks."""
import math


class InputError(ValueError):
    """Unsupported input or invalid recovery thresholds."""


def compatible(hole, pad):
    size = min(pad["width"], pad["height"])
    return hole["diameter"] + 0.1 <= size + 1e-9 and size <= hole["diameter"]*3 and max(pad["width"], pad["height"])/size <= 2


def solve(pads, holes, minimum=4, coverage=0.8, tolerance=0.02):
    if not isinstance(minimum, int) or minimum < 3 or not 0.5 <= coverage <= 1 or not 0.000001 <= tolerance <= 0.1:
        raise InputError("Use minimum matches >=3, coverage 0.5..1, tolerance 0.000001..0.1 mm.")
    if len(pads) > 4000 or len(holes) > 2000:
        raise InputError("Limit exceeded: 4000 flash pads and 2000 round drill hits.")
    for point in pads + holes:
        if any(not isinstance(point.get(k), (float, int)) or not math.isfinite(point[k]) or abs(point[k]) > 1000000 for k in ("x", "y")):
            raise InputError("Invalid or out-of-range coordinates.")
    for p in pads:
        if not all(isinstance(p.get(k), (float, int)) and math.isfinite(p[k]) and 0 < p[k] <= 1000 for k in ("width", "height")):
            raise InputError("Invalid pad dimensions.")
    for h in holes:
        if not isinstance(h.get("diameter"), (float, int)) or not math.isfinite(h["diameter"]) or not 0 < h["diameter"] <= 1000:
            raise InputError("Invalid hole diameter.")
    if len({(h["x"], h["y"]) for h in holes}) != len(holes):
        raise InputError("Duplicate drill hit coordinates require manual review.")
    base = {"format": "drill-origin-rescue-report/1", "status": "review_required", "translation_mm": None,
            "pad_count": len(pads), "hole_count": len(holes), "matches": [], "unmatched_holes": list(range(len(holes))),
            "thresholds": {"minimum_matches": minimum, "minimum_coverage": coverage, "maximum_residual_mm": tolerance},
            "notice": "Review draft. Verify all fabrication layers and original fabrication requirements before use."}
    def review(reason):
        return dict(base, reason=reason)
    if len(holes) < minimum:
        return review("Not enough drill hits for the required evidence.")
    if len(pads)*len(holes) > 300000:
        return review("Candidate pair limit exceeded (300000). Analyze a smaller exported layer or review manually.")
    q = tolerance
    bins = {}
    quantize = lambda value: math.floor(value/q + 0.5)
    for h in holes:
        for p in pads:
            if compatible(h, p):
                dx, dy = p["x"]-h["x"], p["y"]-h["y"]
                key = (quantize(dx), quantize(dy))
                item = bins.setdefault(key, [0, 0.0, 0.0])
                item[0] += 1; item[1] += dx; item[2] += dy
                if len(bins) > 300000:
                    return review("Offset-bin limit exceeded; the geometry does not give a bounded reliable match.")
    candidates = []
    required_votes = max(minimum, math.ceil(coverage*len(holes))-max(1, math.ceil(len(holes)*0.1)))
    for (x, y) in sorted(bins):
        adjacent = [bins.get((x+a, y+b), [0, 0, 0]) for a in (-1, 0, 1) for b in (-1, 0, 1)]
        count = sum(v[0] for v in adjacent)
        if count >= required_votes:
            candidates.append((sum(v[1] for v in adjacent)/count, sum(v[2] for v in adjacent)/count))
    if len(candidates) > 500:
        return review("More than 500 supported offset candidates; repeated geometry requires manual review.")
    grid = {}
    cell = tolerance * 2
    for index, p in enumerate(pads):
        grid.setdefault((math.floor(p["x"]/cell), math.floor(p["y"]/cell)), []).append(index)
    def evaluate(dx, dy, radius):
        edges, incoming = {}, {}
        for hi, h in enumerate(holes):
            x, y = h["x"]+dx, h["y"]+dy
            cx, cy = math.floor(x/cell), math.floor(y/cell)
            neighbors = []
            for a in (-1, 0, 1):
                for b in (-1, 0, 1):
                    for pi in grid.get((cx+a, cy+b), []):
                        p = pads[pi]
                        if compatible(h, p) and math.hypot(p["x"]-x, p["y"]-y) <= radius + 1e-12:
                            neighbors.append(pi); incoming[pi] = incoming.get(pi, 0) + 1
            edges[hi] = neighbors
        return [(hi, values[0]) for hi, values in edges.items() if len(values) == 1 and incoming[values[0]] == 1]
    solutions = {}
    for dx, dy in candidates:
        pairs = evaluate(dx, dy, tolerance * 2)
        if len(pairs) < minimum:
            continue
        dx = sum(pads[p]["x"]-holes[h]["x"] for h, p in pairs)/len(pairs)
        dy = sum(pads[p]["y"]-holes[h]["y"] for h, p in pairs)/len(pairs)
        pairs = evaluate(dx, dy, tolerance)
        if len(pairs) < minimum:
            continue
        rows = [{"hole_index": h, "pad_index": p, "residual_mm": math.hypot(holes[h]["x"]+dx-pads[p]["x"], holes[h]["y"]+dy-pads[p]["y"])} for h, p in pairs]
        solutions[tuple(pairs)] = {"dx": dx, "dy": dy, "matches": rows, "coverage": len(pairs)/len(holes)}
    ranked = sorted(solutions.values(), key=lambda s: (-len(s["matches"]), s["dx"], s["dy"]))
    if not ranked or ranked[0]["coverage"] + 1e-12 < coverage:
        return review("No translation satisfies the minimum unique matches and coverage.")
    winner = ranked[0]
    near_count = len(winner["matches"]) - max(1, math.ceil(len(holes)*0.1))
    rivals = [s for s in ranked[1:] if len(s["matches"]) >= max(minimum, near_count)]
    if rivals:
        return dict(base, reason="Competing translations fit this repeated or symmetrical geometry. No corrected file was created.",
                    competing_offsets_mm=[[s["dx"], s["dy"]] for s in [winner]+rivals])
    matched = {r["hole_index"] for r in winner["matches"]}
    return dict(base, status="already_aligned" if math.hypot(winner["dx"], winner["dy"]) <= tolerance else "recovered",
                reason="One distinct translation satisfies the evidence thresholds. Inspect the overlay and unmatched holes.",
                translation_mm=[winner["dx"], winner["dy"]], matches=winner["matches"], match_coverage=winner["coverage"],
                maximum_residual_mm=max(r["residual_mm"] for r in winner["matches"]), unmatched_holes=[i for i in range(len(holes)) if i not in matched])
