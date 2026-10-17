from unittest.mock import AsyncMock
import json
from types import SimpleNamespace
import pytest
from android_qa.config import Settings
from android_qa.profiles import profile
from android_qa.models import QAError

@pytest.mark.asyncio
async def test_restore_display_after_failure(tmp_path,monkeypatch):
    adb=AsyncMock(side_effect=["1.2","Physical size: 1080x2400\nOverride size: 840x1600","Night mode: no","",""])
    monkeypatch.setattr("android_qa.profiles.adb",adb)
    with pytest.raises(RuntimeError):
        async with profile(Settings(device="emulator-test",profile="small"),SimpleNamespace(path=tmp_path)):
            raise RuntimeError("fixture failure")
    assert adb.await_args.args[-1]=="840x1600"
    assert json.loads((tmp_path/"device-restore.json").read_text())["restored"] is True

@pytest.mark.asyncio
async def test_display_changes_not_allowed_on_phone(tmp_path):
    with pytest.raises(QAError,match="emulators"):
        async with profile(Settings(device="physical-phone",profile="dark"),SimpleNamespace(path=tmp_path)):pass
