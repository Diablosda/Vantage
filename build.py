"""Package the product source and Windows launcher, excluding user projects and media."""
from pathlib import Path
import re
from zipfile import ZIP_DEFLATED, ZipFile

root=Path(__file__).resolve().parent
version=re.search(r"APP_VERSION='([^']+)'",(root/'server.py').read_text(encoding='utf-8')).group(1)
files=[]
for folder in ('ai_previs','backend','web','launcher'):
    files.extend(p for p in (root/folder).rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix not in ('.pyc','.pyo') and p.name!='fetch_vendor.py')
files.extend(root/name for name in ('server.py','启动预演工作台.exe','产品说明.md','README.md','.gitignore','build.py'))
output=root/'dist'/('Camera_Control-'+version+'-source.zip')
output.parent.mkdir(exist_ok=True)
temporary=output.with_suffix('.tmp')
try:
    with ZipFile(temporary,'w',ZIP_DEFLATED) as archive:
        for source in sorted(files):archive.write(source,'Camera_Control/'+source.relative_to(root).as_posix())
    with ZipFile(temporary) as archive:
        if archive.testzip() is not None:raise ValueError('发布包校验失败')
    temporary.replace(output)
finally:
    temporary.unlink(missing_ok=True)
print(output)
