import httpx
import pytest
from android_qa.config import Settings,load
from android_qa.models import Action,Element,Observation,Predicate,Milestone,QAError
from android_qa.observations import parse_tree
from android_qa.tool_registry import Registry
from android_qa.checks import evaluate
from android_qa.deepseek_client import DeepSeek
from android_qa.file_tools import Files
from android_qa.flow_exporter import dump_flow,load_flow,validate_commands
from android_qa.reports import redact

def obs(elements):
    return Observation(observation_id="o1",device="emulator-1",package="p",elements=elements,hierarchy="tree.json",fingerprint="hash")

def test_config_precedence(tmp_path,monkeypatch):
    p=tmp_path/"c.yaml";p.write_text("model: file-model\nmax_steps: 40\n")
    e=tmp_path/".env";e.write_text("DEEPSEEK_MODEL=dotenv-model\n")
    monkeypatch.setenv("DEEPSEEK_MODEL","env-model")
    assert load(p,e).model=="env-model"
    assert load(p,e,model="cli-model").model=="cli-model"
    assert load(p,e).max_steps==40

def test_compact_schema_declared_defaults_only():
    nodes=parse_tree({"ui_schema":{"abbreviations":{"txt":"text","c":"children","b":"bounds"},"defaults":{"checked":False}},"elements":[{"txt":"Task","b":"[1,2][3,4]","c":[{"checked":True}]}]})
    node=next(e for e in nodes if e.text=="Task")
    assert node.bounds==[1,2,3,4] and node.checked is False and node.enabled is None
    assert nodes[-1].checked is True

def test_missing_fields_unknown():
    assert parse_tree({"text":"x"})[0].checked is None

def test_stale_action():
    with pytest.raises(QAError,match="Stale"):
        Registry("AIQA-test","p").compile(Action(kind="back",observation_id="old"),obs([]))

def test_unowned_delete():
    with pytest.raises(QAError,match="context"):
        Registry("AIQA-test","p").compile(Action(kind="tap",element=0,observation_id="o1"),obs([Element(index=0,text="Удалить")]))

def test_old_task_not_owned():
    r=Registry("AIQA-new","p");r.created=True
    with pytest.raises(QAError): r.compile(Action(kind="tap",element=0,observation_id="o1"),obs([Element(index=0,description="Действия с задачей «AIQA-old»")]))

def test_input_requires_focus():
    with pytest.raises(QAError,match="focused"):
        Registry("AIQA-test","p").compile(Action(kind="input",text="AIQA-test",observation_id="o1"),obs([]))

def test_action_is_not_verification():
    m=Milestone(name="p",instruction="Persist",predicates=[Predicate(text="task")],after_restart=True)
    assert len(evaluate(m,obs([]),False))==2
    assert evaluate(m,obs([Element(index=0,text="task")]),False)

def test_duplicate_is_not_passed():
    m=Milestone(name="p",instruction="One task",predicates=[Predicate(text="AIQA-task")])
    errors=evaluate(m,obs([Element(index=0,text="AIQA-task"),Element(index=1,text="AIQA-task")]),True)
    assert any("exactly one" in x for x in errors)

@pytest.mark.parametrize("command",[{"clearState":True},{"runScript":"evil.js"},{"runFlow":"other.yaml"},{"launchApp":{"clearState":True}},{"launchApp":{"appId":"other"}},{"evalScript":"1"},{"openLink":"https://example.com"}])
def test_unsafe_yaml(command):
    with pytest.raises(QAError): validate_commands([command],"p")

def test_interpolation_not_yaml_injection():
    flow="appId: ${APP_ID}\n---\n- inputText: ${TASK_NAME}\n"
    commands=load_flow(flow,{"APP_ID":"p","TASK_NAME":"name\n- clearState: true"})
    assert len(commands)==1 and commands[0]["inputText"].startswith("name\n")

def test_no_javascript():
    with pytest.raises(QAError): load_flow("appId: ${APP_ID}\n---\n- inputText: ${Date.now()}\n",{"APP_ID":"p"})

def test_flow_roundtrip():
    cmds=[{"launchApp":{"clearState":False}},{"assertVisible":{"text":"AIQA-1"}}]
    assert load_flow(dump_flow("p",cmds),{"APP_ID":"p"})==cmds

@pytest.mark.parametrize("path",["../outside.md","D:/outside.md",".env","docs/secrets.md","build/test.md","qa/../x.md"])
def test_paths(tmp_path,path):
    with pytest.raises(QAError): Files(tmp_path).checked(path)

def test_hash_conflict(tmp_path):
    (tmp_path/"qa").mkdir();p=tmp_path/"qa/spec.md";p.write_text("old")
    f=Files(tmp_path);f.stage("qa/spec.md","new",tmp_path/"proposal")
    p.write_text("user changes")
    with pytest.raises(QAError,match="changed"): f.apply(tmp_path/"proposal")
    assert p.read_text()=="user changes"

def test_redaction():
    assert redact({"api_key":"secret","x":"sk-123456789abcdefgh","reasoning_content":"private"})=={"x":"[REDACTED]"}

@pytest.mark.asyncio
async def test_401_no_retry():
    requests=[]
    def handler(r): requests.append(r);return httpx.Response(401)
    c=DeepSeek(Settings(api_key="test"),httpx.MockTransport(handler))
    try:
        with pytest.raises(QAError,match="401"): await c.complete([{"role":"user","content":"x"}])
        assert len(requests)==1
    finally: await c.close()

@pytest.mark.asyncio
async def test_retry_usage_no_reasoning():
    requests=[]
    def handler(r):
        requests.append(r)
        if len(requests)==1: return httpx.Response(503)
        return httpx.Response(200,json={"usage":{"total_tokens":20},"choices":[{"finish_reason":"stop","message":{"content":"OK","reasoning_content":"private"}}]})
    c=DeepSeek(Settings(api_key="test"),httpx.MockTransport(handler))
    try:
        result=await c.complete([{"role":"user","content":"x"}])
        assert c.calls==2 and c.tokens==20 and "reasoning_content" not in result
    finally: await c.close()

@pytest.mark.asyncio
async def test_budget_before_request():
    c=DeepSeek(Settings(api_key="test",max_tokens=100),httpx.MockTransport(lambda r:pytest.fail("Network called")))
    try:
        with pytest.raises(QAError,match="budget"): await c.complete([{"role":"user","content":"x"}])
    finally: await c.close()
