"""Gerbonara parsing with explicit unit/format and conservative extraction gates."""
import re
import warnings
from gerbonara import GerberFile, ExcellonFile
from gerbonara.graphic_objects import Flash
from gerbonara.apertures import CircleAperture, RectangleAperture, ObroundAperture
from gerbonara.utils import MM
from .solver import InputError


def text_input(path):
    raw = path.read_bytes()
    if len(raw) > 5*1024*1024:
        raise InputError("Input file exceeds the 5 MiB limit.")
    try:
        return raw, raw.decode("ascii")
    except UnicodeError as error:
        raise InputError("Use ASCII fabrication exports.") from error


def load(copper_path, drill_path):
    copper_raw, copper_text = text_input(copper_path)
    drill_raw, drill_text = text_input(drill_path)
    if len(re.findall(r"%FS[LT]AX\d\dY\d\d\*%", copper_text)) != 1 or len(re.findall(r"%MO(?:MM|IN)\*%", copper_text)) != 1:
        raise InputError("Gerber needs one explicit absolute FS format and one MO unit declaration.")
    if re.search(r"%(?:LPC|IPNEG|SR|LM|LR|LS|AB|AM|IF)", copper_text) or re.search(r"G(?:9[12]|70|71)\*", copper_text):
        raise InputError("Clear polarity, repeats, transforms, macros, includes and incremental Gerber are unsupported.")
    declarations = re.findall(r"^(METRIC|INCH)(?:,[LT]Z)?\s*$", drill_text, re.M)
    if len(declarations) != 1 or not re.search(r"^M48\s*$", drill_text, re.M) or not re.search(r"^M30\s*$", drill_text, re.M):
        raise InputError("Excellon needs M48/M30 and one explicit METRIC or INCH declaration.")
    if re.search(r"G(?:0?[0123]|85|91)\b|M15|M16|^R\d", drill_text, re.M):
        raise InputError("Slots, routing, repeats and incremental drilling are refused. No corrected file was created.")
    coords = re.findall(r"[XY]([+-]?\d+(?:\.\d+)?)", re.sub(r";[^\n]*", "", drill_text))
    for definition in re.findall(r"^T\d+C[^\n]*", drill_text, re.M):
        if not re.fullmatch(r"T\d+C\d+(?:\.\d+)?\s*", definition):
            raise InputError("Tool feed/speed and extended tool parameters require manual review; they are not silently discarded.")
    if not coords or any("." not in value for value in coords) and not re.search(r";FILE_FORMAT=\d:\d", drill_text):
        raise InputError("Integer drill coordinates need an explicit FILE_FORMAT declaration; units and formats are never guessed.")
    try:
        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            copper = GerberFile.open(copper_path, enable_includes=False)
            drill = ExcellonFile.open(drill_path)
        def harmless(warning):
            message = str(warning.message)
            return message.endswith("G90 header statement found after end of header") or (
                all("." in value for value in coords) and
                'Using implicit number format from bare "INCH" statement. This is normal for Fritzing, Diptrace, Geda and pcb-rnd.' in message)
        relevant = [w for w in captured if not harmless(w)]
        if relevant:
            messages = [str(w.message).replace(str(copper_path), "copper input").replace(str(drill_path), "drill input") for w in relevant]
            raise InputError("Parser warning requires manual review: " + "; ".join(messages))
    except (ValueError, KeyError, IndexError, SyntaxError) as error:
        raise InputError(f"Fabrication parsing failed: {error}") from error
    pads = []
    for obj in copper.objects:
        if not obj.polarity_dark:
            raise InputError("Mixed/clear polarity geometry is unsupported.")
        if not isinstance(obj, Flash):
            continue
        ap = obj.aperture
        if not isinstance(ap, (CircleAperture, RectangleAperture, ObroundAperture)) or getattr(ap, "hole_dia", None):
            raise InputError("Flashed apertures must be solid circle, rectangle or obround candidates.")
        bounds = ap.bounding_box(MM)
        pads.append({"x": obj.unit.convert_to(MM, obj.x), "y": obj.unit.convert_to(MM, obj.y),
                     "width": bounds[1][0]-bounds[0][0], "height": bounds[1][1]-bounds[0][1],
                     "shape": "circle" if isinstance(ap, CircleAperture) else "obround" if isinstance(ap, ObroundAperture) else "rectangle"})
    holes = []
    for obj in drill.objects:
        if not isinstance(obj, Flash):
            raise InputError("Slots and routed geometry are refused; the original file remains intact.")
        holes.append({"x": obj.unit.convert_to(MM, obj.x), "y": obj.unit.convert_to(MM, obj.y),
                      "diameter": obj.tool.unit.convert_to(MM, obj.tool.diameter), "plated": obj.plated})
    if len(pads) > 4000 or len(holes) > 2000:
        raise InputError("Limit exceeded: 4000 flash pads and 2000 round drill hits.")
    return copper_raw, drill_raw, pads, holes, drill
