import sys
from .cli import app
if hasattr(sys.stdout,"reconfigure"): sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr,"reconfigure"): sys.stderr.reconfigure(encoding="utf-8")
app()
