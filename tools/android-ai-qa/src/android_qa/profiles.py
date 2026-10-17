from contextlib import asynccontextmanager
import json
from .diagnostics import adb
from .models import QAError

@asynccontextmanager
async def profile(settings,report):
    if settings.profile=="baseline":
        yield
        return
    if not settings.device.startswith("emulator-"): raise QAError("safety","Display profiles are restricted to emulators")
    original={"font_scale":await adb(settings,"shell","settings","get","system","font_scale"),"size":await adb(settings,"shell","wm","size"),"theme":await adb(settings,"shell","cmd","uimode","night")}
    journal=report.path/"device-restore.json"
    journal.write_text(json.dumps({"device":settings.device,"original":original,"restored":False},indent=2),encoding="utf-8")
    try:
        if settings.profile=="small": await adb(settings,"shell","wm","size","720x1280")
        elif settings.profile=="large-font": await adb(settings,"shell","settings","put","system","font_scale","1.5")
        elif settings.profile=="dark": await adb(settings,"shell","cmd","uimode","night","yes")
        yield
    finally:
        if settings.profile=="small":
            override=next((line.split(":",1)[1].strip() for line in original["size"].splitlines() if line.startswith("Override")),"reset")
            await adb(settings,"shell","wm","size",override)
        elif settings.profile=="large-font":
            if original["font_scale"]=="null": await adb(settings,"shell","settings","delete","system","font_scale")
            else: await adb(settings,"shell","settings","put","system","font_scale",original["font_scale"])
        elif settings.profile=="dark":
            mode=original["theme"].rsplit(":",1)[-1].strip()
            if mode not in {"yes","no","auto","custom"}: raise QAError("device","Cannot restore original night mode; see device-restore.json")
            await adb(settings,"shell","cmd","uimode","night",mode)
        journal.write_text(json.dumps({"device":settings.device,"original":original,"restored":True},indent=2),encoding="utf-8")
