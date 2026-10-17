import asyncio
import json
import os
import platform
import shutil
import subprocess
import sys
import time
from pathlib import Path
from .models import QAError

async def command(args, timeout=30, cwd=None):
    proc = await asyncio.create_subprocess_exec(*map(str,args), cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout)
    except BaseException:
        proc.kill()
        await proc.communicate()
        raise
    return proc.returncode, out.decode("utf-8", errors="replace").strip(), err.decode("utf-8", errors="replace").strip()

async def adb(settings, *args, timeout=30):
    code, out, err = await command([settings.adb, *(["-s", settings.device] if settings.device else []), *args], timeout)
    if code: raise QAError("device", "adb: " + (err or out)[:500])
    return out

async def select_device(settings):
    lines = (await adb(settings, "devices", "-l")).splitlines()[1:]
    devices = [line.split() for line in lines if line.strip()]
    if settings.device:
        found = next((d for d in devices if d[0] == settings.device), None)
        if not found or found[1] != "device": raise QAError("device", "Selected device unavailable or unauthorized")
    else:
        if len(devices) != 1: raise QAError("device", "Select --device explicitly; connected devices: " + str([d[0] for d in devices]))
        if not devices[0][0].startswith("emulator-"): raise QAError("device", "Physical devices require explicit --device")
        if devices[0][1] != "device": raise QAError("device", "Device is not ready")
        settings.device = devices[0][0]
    return devices

def ensure_web_device(settings, on_status=None):
    """Ensure the explicitly selected emulator is online and fully booted.

    A stopped emulator can only be started when its AVD is explicit or when
    exactly one AVD is installed. Physical devices are never launched.
    """
    def status(message):
        if on_status:
            on_status(message)

    if not settings.device:
        raise QAError("device", "Select --device explicitly before starting a scenario")
    if not settings.device.startswith("emulator-"):
        states = _sync_device_states(settings)
        if states.get(settings.device) != "device":
            raise QAError("device", "Selected device unavailable or unauthorized")
        status("Waiting for Android device to finish booting")
        _sync_wait_for_boot(settings, timeout=30)
        return

    _sync_command([settings.adb, "start-server"], timeout=15)
    devices = _sync_device_states(settings)
    state = devices.get(settings.device)
    if state == "device":
        status("Waiting for Android emulator to finish booting")
        _sync_wait_for_boot(settings, timeout=180)
        return
    if state == "offline":
        status("Emulator is connecting; waiting for ADB authorization and boot")
        _sync_wait_for_boot(settings, timeout=180)
        return
    if state is not None:
        raise QAError("device", f"Selected emulator {settings.device} is not usable (ADB state: {state})")

    adb_path = Path(settings.adb).resolve()
    sdk_root = adb_path.parent.parent
    emulator = sdk_root / "emulator" / ("emulator.exe" if os.name == "nt" else "emulator")
    if not emulator.is_file():
        raise QAError("device", f"Emulator executable not found next to ADB: {emulator}")
    env = {**os.environ, "ANDROID_HOME": str(sdk_root), "ANDROID_SDK_ROOT": str(sdk_root)}
    code, listed, error = _sync_command([emulator, "-list-avds"], timeout=20, env=env)
    if code:
        raise QAError("device", "Cannot list Android emulators: " + error[:400])
    avds = [line.strip() for line in listed.splitlines() if line.strip()]
    selected = settings.avd_name
    if selected and selected not in avds:
        raise QAError("device", f"Configured AVD '{selected}' is unavailable. Installed AVDs: {avds}")
    if not selected:
        if len(avds) != 1:
            raise QAError("device", "Selected emulator is stopped. Specify its AVD with --avd (installed: " + ", ".join(avds) + ")")
        selected = avds[0]
    suffix = settings.device.removeprefix("emulator-")
    try:
        port = int(suffix)
    except ValueError as exc:
        raise QAError("device", "Invalid emulator serial: " + settings.device) from exc
    if not 1 <= port <= 65534 or port % 2:
        raise QAError("device", "Emulator serial must contain an even port between 1 and 65534")
    status(f"Starting Android emulator {selected} on {settings.device}")
    try:
        process = subprocess.Popen([str(emulator), "-avd", selected, "-port", str(port)], env=env)
    except OSError as exc:
        raise QAError("device", "Could not start Android emulator: " + str(exc)) from exc
    try:
        exit_code = process.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass  # The visible emulator process is expected to keep running.
    else:
        if exit_code:
            raise QAError("device", f"Emulator exited during startup (code {exit_code}); check the AVD image and SDK path")
    status("Waiting for Android emulator boot")
    _sync_wait_for_boot(settings, timeout=240)

def _sync_command(args, timeout=30, env=None):
    try:
        result = subprocess.run(
            list(map(str, args)), capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout, env=env,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise QAError("device", f"Could not run {Path(str(args[0])).name}: {exc}") from exc
    return result.returncode, result.stdout.strip(), result.stderr.strip()

def _sync_device_states(settings):
    code, out, err = _sync_command([settings.adb, "devices", "-l"], timeout=15)
    if code:
        raise QAError("device", "adb devices failed: " + (err or out)[:400])
    states = {}
    for line in out.splitlines()[1:]:
        fields = line.split()
        if len(fields) >= 2:
            states[fields[0]] = fields[1]
    return states

def _sync_wait_for_boot(settings, timeout):
    deadline = time.monotonic() + timeout
    last_state = None
    while time.monotonic() < deadline:
        states = _sync_device_states(settings)
        last_state = states.get(settings.device)
        if last_state == "device":
            code, out, _ = _sync_command(
                [settings.adb, "-s", settings.device, "shell", "getprop", "sys.boot_completed"], timeout=10
            )
            if code == 0 and out.strip() == "1":
                return
        time.sleep(2)
    raise QAError("device", f"Selected device {settings.device} did not finish booting (ADB state: {last_state or 'absent'})")

async def metadata(settings):
    fields = {}
    for name,args in {"android_api": ["getprop","ro.build.version.sdk"], "locale":["getprop","persist.sys.locale"], "timezone":["getprop","persist.sys.timezone"], "date":["date","+%Y-%m-%d"], "font_scale":["settings","get","system","font_scale"], "screen":["wm","size"], "density":["wm","density"]}.items():
        fields[name] = await adb(settings,"shell",*args)
    package = await adb(settings,"shell","dumpsys","package",settings.app_id)
    fields["apk"] = [line.strip() for line in package.splitlines() if any(k in line for k in ("versionCode=","versionName=","pkgFlags=","lastUpdateTime="))]
    fields["debuggable"] = "DEBUGGABLE" in package
    if settings.repo:
        for name,args in {"commit":["rev-parse","HEAD"],"dirty":["status","--porcelain=v1"]}.items():
            _,out,_ = await command(["git","-C",settings.repo,*args])
            fields[name] = out
    return fields

async def basics(settings):
    result = {"python": sys.version.split()[0], "os": platform.platform(), "api_key_present": bool(settings.api_key.get_secret_value()), "maestro_path": settings.maestro}
    for name,args in {"java":[shutil.which("java") or "java","-version"],"adb":[settings.adb,"version"]}.items():
        try:
            code,out,err = await command(args)
            result[name] = {"ok": code == 0, "version": out or err}
        except OSError: result[name] = {"ok": False, "reason": "not found"}
    try:
        result["devices"] = await select_device(settings)
        result["app_installed"] = bool(await adb(settings,"shell","pm","path",settings.app_id))
    except QAError as exc: result["device_error"] = str(exc)
    return result
