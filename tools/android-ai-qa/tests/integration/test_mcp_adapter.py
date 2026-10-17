"""Adapter tests use explicit mocks, NOT an Android pass claim."""
import asyncio
from types import SimpleNamespace
import pytest
from android_qa.maestro_client import Maestro
from android_qa.config import Settings
from android_qa.models import QAError

def schemas():
    return {n:{"inputSchema":{"type":"object","properties":p,"required":list(p)}} for n,p in {"list_devices":{},"inspect_screen":{"device_id":{"type":"string"}},"take_screenshot":{"device_id":{"type":"string"}},"run":{"device_id":{"type":"string"},"yaml":{"type":"string"}}}.items()}

class Session:
    def __init__(self,delay=0,error=False):self.delay=delay;self.error=error;self.calls=[]
    async def call_tool(self,name,args):
        self.calls.append((name,args))
        await asyncio.sleep(self.delay)
        return SimpleNamespace(is_error=False,content=[SimpleNamespace(type="text",text='{"success":false,"error":"fixture failure"}' if self.error else '{"success":true}')],structured_content=None)

@pytest.mark.asyncio
async def test_discovered_schema_and_selected_device():
    session=Session();m=Maestro(session,schemas(),Settings(device="emulator-test"))
    await m.run("- back")
    assert session.calls==[("run",{"device_id":"emulator-test","yaml":"- back"})]
    with pytest.raises(QAError,match="Unsupported"):await m.call("run_on_cloud")

@pytest.mark.asyncio
async def test_timeout_never_retries_ui_action():
    session=Session(delay=.05);m=Maestro(session,schemas(),Settings(device="test",tool_timeout=.01))
    with pytest.raises(QAError,match="outcome unknown"): await m.run("- back")
    assert len(session.calls)==1

@pytest.mark.asyncio
async def test_success_false_is_tool_failure():
    m=Maestro(Session(error=True),schemas(),Settings(device="test"))
    with pytest.raises(QAError,match="flow failed"):await m.run("- back")

def test_missing_capability_blocks():
    with pytest.raises(QAError,match="missing"): Maestro(Session(),{},Settings())
