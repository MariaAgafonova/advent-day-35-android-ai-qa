import json
from unittest.mock import AsyncMock
import pytest
from android_qa.agent import Agent
from android_qa.config import Settings
from android_qa.models import Observation,QAError
from android_qa.reports import Report

class Model:
    async def complete(self,messages,tools):
        return {"role":"assistant","content":None,"tool_calls":[{"id":"call-test","type":"function","function":{"name":"act","arguments":json.dumps({"kind":"back","observation_id":"same"})}}]}

@pytest.mark.asyncio
async def test_repeated_unchanged_state_stops_without_extra_action(tmp_path,monkeypatch):
    settings=Settings(repo=None,artifacts=tmp_path,device="fixture",max_steps=20)
    report=Report(tmp_path,"fixture",settings)
    maestro=AsyncMock()
    agent=Agent(settings,report,maestro,Model(),"create","fixture",{"date":"2026-10-17"})
    saved=json.loads((report.path/"run.json").read_text(encoding="utf-8"))
    assert [step["name"] for step in saved["checkpoints"]]==["created","create_persisted"]
    observation=Observation(observation_id="same",device="fixture",package="p",elements=[],hierarchy="fixture.json",fingerprint="unchanged")
    agent.observation=AsyncMock(return_value=observation)
    monkeypatch.setattr("android_qa.agent.adb",AsyncMock(return_value="2026-10-17"))
    with pytest.raises(QAError,match="Repeated action"):
        await agent.run()
    assert maestro.run.await_count==4  # initial launch + three back calls
    assert report.checks==[]  # no fake passed check
