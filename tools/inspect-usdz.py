"""Read-only USDZ archive audit: python tools/inspect-usdz.py char5.usdz.
Does not rewrite, recompress or change animation. Uses Pillow if installed.
"""
import sys, zipfile, struct, io, json
from pathlib import Path
try:
 from PIL import Image
except ImportError:
 Image = None
for name in sys.argv[1:]:
 p=Path(name)
 if not p.exists():
  print(json.dumps({'file':str(p),'missing':True}));continue
 with p.open('rb') as raw,zipfile.ZipFile(p) as archive:
  rows=[]
  for item in archive.infolist():
   raw.seek(item.header_offset+26);n,e=struct.unpack('<HH',raw.read(4));offset=item.header_offset+30+n+e
   row={'name':item.filename,'bytes':item.file_size,'stored':item.compress_type==zipfile.ZIP_STORED,'aligned64':offset%64==0}
   if Image and Path(item.filename).suffix.lower() in ('.png','.jpg','.jpeg'):
    with Image.open(io.BytesIO(archive.read(item))) as image:row.update(width=image.width,height=image.height,mode=image.mode)
   rows.append(row)
  print(json.dumps({'file':str(p),'bytes':p.stat().st_size,'members':sorted(rows,key=lambda r:r['bytes'],reverse=True)},indent=2))
