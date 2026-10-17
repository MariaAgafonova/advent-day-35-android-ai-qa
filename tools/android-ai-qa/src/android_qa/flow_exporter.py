import re
import yaml
from .models import QAError

ALLOWED = {"launchApp", "stopApp", "tapOn", "inputText", "eraseText", "scroll", "scrollUntilVisible", "back", "hideKeyboard", "assertVisible", "assertNotVisible", "extendedWaitUntil", "waitForAnimationToEnd", "runFlow"}
SELECTOR_KEYS = {"text","id","index","point","checked","enabled","selected","focused","below","above","leftOf","rightOf","childOf","containsChild","retryTapIfNoChange"}

def validate_selector(value):
    if isinstance(value,str): return
    if not isinstance(value,dict) or not value or set(value)-SELECTOR_KEYS: raise QAError("safety","Invalid selector")
    for key,item in value.items():
        if isinstance(item,dict): validate_selector(item)
        elif not isinstance(item,(str,int,bool)): raise QAError("safety","Invalid selector value")

def validate_commands(commands, app_id, depth=0):
    if depth>2: raise QAError("safety","Nested flow depth exceeded")
    if not isinstance(commands,list) or not commands or len(commands)>500: raise QAError("safety","Expected 1–500 Maestro commands")
    for entry in commands:
        if isinstance(entry,str):
            if entry not in {"back","hideKeyboard","scroll","waitForAnimationToEnd"}: raise QAError("safety","Command requires explicit safe arguments")
            continue
        if not isinstance(entry,dict) or len(entry)!=1: raise QAError("safety","Invalid command")
        name,value = next(iter(entry.items()))
        if name not in ALLOWED: raise QAError("safety","Forbidden Maestro command: "+name)
        if name=="runFlow":
            if not isinstance(value,dict) or set(value)!={"when","commands"} or not isinstance(value["when"],dict) or set(value["when"])-{"visible","notVisible"}: raise QAError("safety","Only bounded inline conditional UI flows allowed")
            for condition in value["when"].values(): validate_selector(condition)
            validate_commands(value["commands"],app_id,depth+1)
        elif name in {"tapOn","assertVisible","assertNotVisible"}: validate_selector(value)
        elif name in {"launchApp","stopApp"}:
            if not isinstance(value,dict) or set(value)-{"appId","clearState","stopApp"}: raise QAError("safety","Invalid launch/stop arguments")
            if value.get("appId",app_id)!=app_id or value.get("clearState",False) is not False: raise QAError("safety","Wrong package or data clearing")
        elif name=="inputText":
            if not isinstance(value,str) or len(value)>2000: raise QAError("safety","Input text length/type")
        elif name=="eraseText":
            if not isinstance(value,int) or not 1<=value<=2000: raise QAError("safety","Invalid erase count")
        elif name=="extendedWaitUntil":
            if not isinstance(value,dict) or set(value)-{"visible","notVisible","timeout"} or not 0<value.get("timeout",10000)<=30000: raise QAError("safety","Invalid wait")
            for key in ("visible","notVisible"):
                if key in value: validate_selector(value[key])
        elif name=="scrollUntilVisible":
            if not isinstance(value,dict) or set(value)-{"element","direction","timeout","speed","centerElement"}: raise QAError("safety","Invalid scroll")
            validate_selector(value["element"])
            if value.get("direction","DOWN") not in {"UP","DOWN"} or not 0<value.get("timeout",10000)<=30000: raise QAError("safety","Invalid scroll limit")
        elif name in {"back","hideKeyboard","scroll","waitForAnimationToEnd"}:
            if value is not None: raise QAError("safety","Unexpected command arguments")
    return commands

def dump_flow(app_id, commands):
    validate_commands(commands,app_id)
    return yaml.safe_dump({"appId":app_id},allow_unicode=True,sort_keys=False)+"---\n"+yaml.safe_dump(commands,allow_unicode=True,sort_keys=False)

def load_flow(text, params):
    # Only simple known variable interpolation. Maestro JS expressions are forbidden.
    variables=re.findall(r"\$\{([^}]+)\}",text)
    if any(v not in params for v in variables): raise QAError("safety","Unknown variable or expression")
    documents=list(yaml.safe_load_all(text))
    if len(documents)!=2 or not isinstance(documents[0],dict) or set(documents[0])!={"appId"}: raise QAError("safety","Flow header must contain only appId")
    def replace(value):
        if isinstance(value,str):
            return re.sub(r"\$\{([A-Z_]+)\}",lambda m: params[m[1]],value)
        if isinstance(value,list): return [replace(v) for v in value]
        if isinstance(value,dict): return {k:replace(v) for k,v in value.items()}
        return value
    header,commands=replace(documents)
    if header["appId"]!=params["APP_ID"]: raise QAError("safety","Unexpected applicationId")
    validate_commands(commands,header["appId"])
    return commands

def export(report, app_id, commands, task_name, scenario, date_values=None):
    # Recorded commands include assertions; observation calls and rejected/exploratory no-ops are not included.
    cleaned=[]
    for cmd in commands:
        if cleaned and cmd==cleaned[-1] and cmd in ("hideKeyboard","back"): continue
        # Tomorrow can cross a month/year. Normalize calendar exploration into a
        # bounded branch; never bake the observed weekday into the reusable flow.
        value=cmd.get("tapOn",{}) if isinstance(cmd,dict) else {}
        text=value.get("text","") if isinstance(value,dict) else ""
        target=(date_values or {}).get("TARGET_CALENDAR_DATE")
        if text.startswith(re.escape("Выполненные")):
            ending="показать" if "показать" in text else "скрыть"
            cleaned.append({"tapOn":{"text":"Выполненные.*"+ending}})
            continue
        if text==re.escape("Перейти к следующему месяцу"): continue
        if target and re.escape(target) in text:
            calendar_selector={"text":".*${TARGET_CALENDAR_DATE}.*"}
            cleaned.append({"runFlow":{"when":{"notVisible":calendar_selector},"commands":[{"tapOn":{"text":re.escape("Перейти к следующему месяцу")}}]}})
            cleaned.append({"tapOn":calendar_selector})
            continue
        cleaned.append(cmd)
    text=dump_flow(app_id,cleaned)
    text=text.replace(app_id,"${APP_ID}").replace(re.escape(task_name),"${TASK_NAME}").replace(task_name,"${TASK_NAME}")
    for name,value in (date_values or {}).items():
        text=text.replace(re.escape(value),"${"+name+"}").replace(value,"${"+name+"}")
    path=report.path/"generated-flows"/(scenario+".yaml")
    path.write_text(text,encoding="utf-8")
    report.metadata["flow"]={"path":str(path),"status":"unverified","reason":"Replay has not completed"}
    report.save()
    return path

def validate_replay_ownership(commands,task):
    """Replay must create fresh data before mutating a task; deny unrelated selectors."""
    created=False;entered=False;owned=False;assert_count=0
    safe={"Добавить задачу","Что нужно сделать?","Сохранить","Сегодня","Предыдущий день","Следующий день","Отмена","Удалить","Перенести на дату","Редактировать","Отменить","Перейти к следующему месяцу","Перейти к предыдущему месяцу"}
    for cmd in commands:
        if not isinstance(cmd,dict): continue
        name,value=next(iter(cmd.items()))
        if name=="runFlow":
            # Exporter's only conditional is calendar navigation. No conditional
            # task mutations can bypass the ownership state machine.
            for nested in value["commands"]:
                if not isinstance(nested,dict) or set(nested)!={"tapOn"} or nested["tapOn"]!={"text":re.escape("Перейти к следующему месяцу")}:
                    raise QAError("safety","Conditional replay limited to next-month navigation")
            continue
        if name=="inputText":
            if value==task: entered=True
            elif not (owned and re.fullmatch(r"[0-9/.-]{1,12}",value)): raise QAError("safety","Replay input is not owned test data")
        if name in {"assertVisible","assertNotVisible"}:
            assert_count+=1
            text=value.get("text","") if isinstance(value,dict) else value
            if name=="assertVisible" and text in {task,re.escape(task)} and entered: created=True
        if name=="tapOn":
            if not isinstance(value,dict) or "point" in value or "id" in value: raise QAError("safety","Replay requires auditable task-specific text selectors")
            text=value.get("text","")
            literal=re.sub(r"\\(.)",r"\1",text)
            if task in literal:
                if not created: raise QAError("safety","Task not yet created and asserted")
                owned=True
            elif literal in {"Удалить","Перенести на дату","Редактировать"}:
                if not owned: raise QAError("safety","Replay has no owned task context")
            elif literal in safe: pass
            elif literal.startswith("Выполненные") or "Выбрать дату" in literal: pass
            elif re.search(r"\d",literal) and not re.search(r"AIQA-",literal):
                # Calendar labels only: month/day/year, not arbitrary task names containing a digit.
                if not (re.search(r"январ|феврал|март|апрел|ма[йя]|июн|июл|август|сентябр|октябр|ноябр|декабр",literal,re.I) or re.fullmatch(r"\d{1,2}",literal)):
                    raise QAError("safety","Unrecognized calendar selector")
            else: raise QAError("safety","Replay targets unrelated UI")
    if not entered or assert_count<3: raise QAError("safety","Replay requires independent task creation and functional assertions")
