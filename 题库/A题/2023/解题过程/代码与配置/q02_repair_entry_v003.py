"""Stable Windows argv wrapper: JSON from a local file, no shell JSON escaping."""
from pathlib import Path
import sys,runpy
here=Path(__file__).resolve().parent
phase=sys.argv[1]
if phase=='rate':
 payload=Path(sys.argv[3]).read_text(encoding='utf-8-sig')
 sys.argv=[str(here/'q02_repair_run_v003.py'),'rate',sys.argv[2],payload]
else:sys.argv=[str(here/'q02_repair_run_v003.py'),*sys.argv[1:]]
runpy.run_path(str(here/'q02_repair_run_v003.py'),run_name='__main__')
