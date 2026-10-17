import re
from .models import Action, QAError

def selector(element, observation):
    if element.resource_id: return {"id":re.escape(element.resource_id)}
    text = element.description or element.text
    if text:
        matches=[e for e in observation.elements if text in (e.text,e.description)]
        if len(matches)==1: return {"text":re.escape(text)}
        # Use observed spatial context instead of guessing an index among duplicate labels.
        if element.bounds:
            siblings=[e for e in observation.elements if e.parent==element.parent and e.text and e.index!=element.index]
            if len(siblings)==1: return {"text":re.escape(text),"below":{"text":re.escape(siblings[0].text)}}
        raise QAError("safety","Ambiguous text selector; choose task-specific description")
    if element.class_name == "android.widget.EditText":
        children=[e for e in observation.elements if e.parent==element.index and (e.text or e.description)]
        if len(children)==1: return {"text":re.escape(children[0].description or children[0].text)}
    if element.bounds:
        a,b,c,d=element.bounds
        return {"point":f"{(a+c)//2},{(b+d)//2}"}
    raise QAError("safety","Element has no usable selector")

TOOLS=[{"type":"function","function":{"name":"act","description":"Perform ONE action using the current observation. check verifies the current milestone; restart relaunches without clearing data. Only operate on the assigned AIQA task.","parameters":Action.model_json_schema()}}]

class Registry:
    def __init__(self, task, app_id):
        self.task,self.app_id=task,app_id
        self.owned_context=False
        self.editor=False
        self.created=False

    def compile(self, action, observation):
        if action.observation_id!=observation.observation_id: raise QAError("safety","Stale observation")
        if action.kind=="tap":
            if action.element is None or not 0<=action.element<len(observation.elements): raise QAError("safety","Invalid element index")
            e=observation.elements[action.element]
            if e.enabled is False: raise QAError("safety","Disabled element")
            label=e.description or e.text or ""
            if e.resource_id and not e.resource_id.startswith(self.app_id+":") and not e.resource_id.startswith("android:"): raise QAError("safety","System/other app element denied")
            if any(x in label for x in ("Действия с задачей", "Выполнить «", "Отменить выполнение «")):
                if self.task not in label or not self.created: raise QAError("safety","Only tasks created in this run may be modified")
                self.owned_context=True
            if label in {"Удалить","Перенести на дату","Редактировать"} and not self.owned_context: raise QAError("safety","No current-run task context")
            if label=="Добавить задачу":
                if self.created: raise QAError("safety","Task creation already observed; refusing duplicate")
                self.editor=True
            if label in {"Голосом","Настройки","Подвести итоги дня","Начать диктовку"}: raise QAError("safety","Out-of-scope operation")
            # Do not permit tapping unrelated task titles, including old AIQA tasks.
            titles={x.text for x in observation.elements if x.text and any(self._contains(x,b) for b in observation.elements if b.description and b.description.startswith("Действия с задачей"))}
            if label in titles and label!=self.task and label not in {"Удалить","Перенести на дату"}: raise QAError("safety","Unowned task")
            return [{"tapOn":selector(e,observation)}]
        if action.kind=="input":
            if action.text is None: raise QAError("safety","Missing input")
            fields=[e for e in observation.elements if e.class_name=="android.widget.EditText" and e.focused]
            if not fields: raise QAError("safety","No focused text field; tap it first")
            if action.text!=self.task and not (self.owned_context and re.fullmatch(r"[0-9/.\-]{1,12}",action.text)): raise QAError("safety","Only assigned test name or calendar date may be entered")
            if not action.text.isascii(): raise QAError("capability","Maestro inputText on Android does not support Unicode; not checked")
            commands=[]
            existing=fields[0].text
            if existing: commands.append({"eraseText":min(len(existing),2000)})
            commands.append({"inputText":action.text})
            return commands
        if action.kind=="restart":
            self.owned_context=False
            return [{"launchApp":{"appId":self.app_id,"clearState":False,"stopApp":True}},{"extendedWaitUntil":{"visible":"Добавить задачу","timeout":30000}}]
        if action.kind=="scroll":
            if action.direction=="UP":
                return [{"scrollUntilVisible":{"element":{"text":"Сегодня"},"direction":"UP","timeout":10000}}]
            return ["scroll"]
        if action.kind in {"back","hide_keyboard"}:
            return ["back" if action.kind=="back" else "hideKeyboard"]
        if action.kind in {"check","finish"}: return []
        raise QAError("safety","Unknown action")

    @staticmethod
    def _contains(a,b):
        return bool(a.text and b.description and f"«{a.text}»" in b.description)
