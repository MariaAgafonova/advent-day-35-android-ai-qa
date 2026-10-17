import hashlib
import json
import re
from .models import Element, Observation, QAError

def parse_tree(value):
    if isinstance(value, str):
        start = min([i for i in (value.find("{"), value.find("[")) if i >= 0], default=-1)
        if start < 0: raise QAError("tool", "Hierarchy response is not JSON")
        try: value = json.JSONDecoder().raw_decode(value[start:])[0]
        except ValueError as exc: raise QAError("tool", "Invalid hierarchy JSON") from exc
    schema = value.get("ui_schema", {}) if isinstance(value,dict) else {}
    abbreviations = schema.get("abbreviations", {})
    defaults = {abbreviations.get(k,k):v for k,v in schema.get("defaults",{}).items()}
    elements = []
    def visit(node, parent=None):
        if isinstance(node, list):
            for child in node: visit(child, parent)
            return
        if not isinstance(node, dict): return
        attrs = {**defaults, **{abbreviations.get(k,k):v for k,v in node.items()}, **node.get("attributes", {})}
        def get(*keys): return next((attrs[k] for k in keys if k in attrs), None)
        def flag(*keys):
            val = get(*keys)
            if isinstance(val, bool): return val
            if val in ("true", "false"): return val == "true"
            return None
        bounds = get("bounds")
        if isinstance(bounds, str): bounds = [int(x) for x in re.findall(r"-?\d+", bounds)]
        if isinstance(bounds, dict):
            if all(k in bounds for k in ("x", "y", "width", "height")): bounds = [bounds["x"], bounds["y"], bounds["x"]+bounds["width"], bounds["y"]+bounds["height"]]
            elif all(k in bounds for k in ("left", "top", "right", "bottom")): bounds = [bounds[k] for k in ("left", "top", "right", "bottom")]
        if not isinstance(bounds, list) or len(bounds) != 4: bounds = None
        element = Element(index=len(elements), parent=parent, resource_id=get("resource-id", "resourceId", "id"), text=get("text"), description=get("content-desc", "contentDescription", "contentDesc", "accessibilityText"), bounds=bounds, checked=flag("checked"), enabled=flag("enabled"), clickable=flag("clickable"), focused=flag("focused"), scrollable=flag("scrollable"), selected=flag("selected"), class_name=get("class", "className"))
        elements.append(element)
        for key in ("children", "c", "nodes", "elements", "hierarchy", "root"):
            if key in node: visit(node[key], element.index)
    visit(value)
    return elements

async def observe(maestro, report, number):
    result = await maestro.call("tree")
    raw = result["structured"] if result["structured"] is not None else result["text"]
    elements = parse_tree(raw)
    oid = f"obs-{number:04d}"
    hierarchy = f"hierarchy/{oid}.json"
    report.json(hierarchy, raw)
    screenshot = f"screenshots/{oid}.png"
    if not await maestro.screenshot(report.path / screenshot): screenshot = None
    fingerprint = hashlib.sha256(json.dumps([e.model_dump(exclude_none=True) for e in elements], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    obs = Observation(observation_id=oid, device=maestro.s.device, package=maestro.s.app_id, elements=elements, screenshot=screenshot, hierarchy=hierarchy, fingerprint=fingerprint)
    report.json(f"hierarchy/{oid}-normalized.json", obs.model_dump())
    report.event("observation", observation_id=oid, fingerprint=fingerprint, screenshot=screenshot, hierarchy=hierarchy)
    return obs
