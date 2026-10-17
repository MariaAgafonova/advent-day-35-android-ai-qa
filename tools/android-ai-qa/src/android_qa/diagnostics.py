import asyncio
import json
import platform
import shutil
import sys
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
