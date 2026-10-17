from pathlib import Path
import subprocess

import pytest

from android_qa import diagnostics
from android_qa.config import Settings
from android_qa.models import QAError


def test_stopped_selected_emulator_starts_explicit_avd(monkeypatch):
    sdk = Path("D:/AndroidSDK")
    adb = sdk / "platform-tools" / "adb.exe"
    emulator = sdk / "emulator" / "emulator.exe"
    monkeypatch.setattr(Path, "is_file", lambda _path: True)
    settings = Settings(adb=str(adb), device="emulator-5554", avd_name="Pixel_7")
    commands = []

    def command(args, timeout=30, env=None):
        commands.append((list(map(str, args)), env))
        if "-list-avds" in args:
            return 0, "Pixel_7\nOther_AVD", ""
        return 0, "", ""

    monkeypatch.setattr(diagnostics, "_sync_command", command)
    monkeypatch.setattr(diagnostics, "_sync_device_states", lambda _settings: {})
    boot_waits = []
    monkeypatch.setattr(diagnostics, "_sync_wait_for_boot", lambda _settings, timeout: boot_waits.append(timeout))

    calls = []

    class RunningEmulator:
        def wait(self, timeout):
            calls.append(("wait", timeout))
            raise subprocess.TimeoutExpired("emulator", timeout)

    def start(args, env=None):
        calls.append((list(args), env))
        return RunningEmulator()

    monkeypatch.setattr(diagnostics.subprocess, "Popen", start)
    stages = []

    diagnostics.ensure_web_device(settings, on_status=stages.append)

    assert commands[0][0] == [str(adb), "start-server"]
    assert commands[1][0] == [str(emulator), "-list-avds"]
    assert commands[1][1]["ANDROID_SDK_ROOT"] == str(sdk)
    assert calls[0][0] == [str(emulator), "-avd", "Pixel_7", "-port", "5554"]
    assert calls[0][1]["ANDROID_HOME"] == str(sdk)
    assert calls[1] == ("wait", 2)
    assert boot_waits == [240]
    assert stages == ["Starting Android emulator Pixel_7 on emulator-5554", "Waiting for Android emulator boot"]


def test_stopped_emulator_with_multiple_avds_requires_selection(monkeypatch):
    adb = Path("D:/AndroidSDK/platform-tools/adb.exe")
    monkeypatch.setattr(Path, "is_file", lambda _path: True)
    settings = Settings(adb=str(adb), device="emulator-5554")

    def command(args, timeout=30, env=None):
        if "-list-avds" in args:
            return 0, "Pixel_7\nOther_AVD", ""
        return 0, "", ""

    monkeypatch.setattr(diagnostics, "_sync_command", command)
    monkeypatch.setattr(diagnostics, "_sync_device_states", lambda _settings: {})

    with pytest.raises(QAError, match="Specify its AVD with --avd"):
        diagnostics.ensure_web_device(settings)


def test_active_emulator_is_waited_for_without_starting_another(monkeypatch):
    settings = Settings(device="emulator-5554")
    monkeypatch.setattr(diagnostics, "_sync_command", lambda *_args, **_kwargs: (0, "", ""))
    monkeypatch.setattr(diagnostics, "_sync_device_states", lambda _settings: {"emulator-5554": "device"})
    waits = []
    monkeypatch.setattr(diagnostics, "_sync_wait_for_boot", lambda _settings, timeout: waits.append(timeout))
    monkeypatch.setattr(diagnostics.subprocess, "Popen", lambda *_args, **_kwargs: pytest.fail("unexpected emulator start"))

    diagnostics.ensure_web_device(settings)
    assert waits == [180]


def test_unauthorized_emulator_is_not_relaunched(monkeypatch):
    settings = Settings(device="emulator-5554")
    monkeypatch.setattr(diagnostics, "_sync_command", lambda *_args, **_kwargs: (0, "", ""))
    monkeypatch.setattr(diagnostics, "_sync_device_states", lambda _settings: {"emulator-5554": "unauthorized"})

    with pytest.raises(QAError, match="ADB state: unauthorized"):
        diagnostics.ensure_web_device(settings)
