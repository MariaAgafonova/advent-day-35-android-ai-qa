import re
from .models import Check

def matches(element, predicate):
    text=[t for t in (element.text,element.description) if t]
    yes=any(t==predicate.text if predicate.exact else predicate.text in t for t in text)
    return yes and (predicate.checked is None or element.checked==predicate.checked) and (predicate.selected is None or element.selected==predicate.selected)

def full_list(observation):
    counters=[re.search(r"Выполнено (\d+) из (\d+)",e.text or "") for e in observation.elements]
    count=next((int(m[2]) for m in counters if m),None)
    cards=[e for e in observation.elements if (e.description or "").startswith("Действия с задачей «")]
    return count is not None and len(cards)==count

def evaluate(milestone, observation, restarted):
    errors=[]
    if milestone.after_restart and not restarted: errors.append("App restart required after previous checkpoint")
    if milestone.full_list and not full_list(observation): errors.append("Full list not covered: expand completed section and expose all cards")
    for p in milestone.predicates:
        found=[e for e in observation.elements if matches(e,p)]
        if bool(found)!=p.present: errors.append(("Missing " if p.present else "Unexpected ")+p.text)
        if p.present and p.exact and p.text.startswith("AIQA-") and len(found)!=1: errors.append("Expected exactly one owned task, found "+str(len(found)))
    return errors

def result(milestone, observation, status="passed", actual="Predicates verified on fresh UI hierarchy"):
    return Check(name=milestone.name,status=status,expected=milestone.instruction,actual=actual,evidence=[observation.hierarchy,*([observation.screenshot] if observation.screenshot else [])])

def assertions(milestone):
    import re
    commands=[]
    for p in milestone.predicates:
        selector={"text":re.escape(p.text) if p.exact else ".*"+re.escape(p.text)+".*"}
        if p.checked is not None: selector["checked"]=p.checked
        if p.selected is not None: selector["selected"]=p.selected
        commands.append({"assertVisible" if p.present else "assertNotVisible":selector})
        if p.present and p.text.startswith("AIQA-"):
            commands.append({"assertNotVisible":{"text":re.escape(p.text),"index":1}})
    return commands

def geometry(observation):
    # Do not infer occlusion from intersecting parent/child rectangles.
    bad=[e.index for e in observation.elements if e.bounds and (e.bounds[2]<e.bounds[0] or e.bounds[3]<e.bounds[1])]
    return Check(name="hierarchy_geometry",status="not_checked" if bad else "passed",expected="Valid element rectangles",actual="Invalid bounds: "+str(bad) if bad else "No inverted bounds; this does not prove visual correctness",evidence=[observation.hierarchy],category="tool")
