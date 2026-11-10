"""Portable project archive: bundle referenced models and motions without modifying old projects."""
import hashlib
import io
import json
from pathlib import Path
from zipfile import ZipFile, ZIP_STORED, BadZipFile

MAX_ARCHIVE = 512 * 1024 * 1024

def _name(value):
    if not isinstance(value, str) or not value or value in ('.','..') or '/' in value or '\\' in value or ':' in value:
        raise ValueError('资源文件名无效')
    return value

def references(project):
    models, motions, scenes = set(), set(), set()
    for obj in project.get('objects', []):
        source = obj.get('modelSource')
        if source: models.add(_name(source['name']))
        if obj.get('sceneSource'): scenes.add(_name(obj['sceneSource']['asset']))
        for seg in obj.get('segments', []):
            if seg.get('motion'): motions.add(_name(seg['motion']['name']))
    return models, motions, scenes

def create_bundle(project, destination, root, legacy_root=None):
    models, motions, scenes = references(project)
    project_data=json.dumps(project, ensure_ascii=False, separators=(',',':')).encode('utf-8')
    if len(project_data)>128*1024*1024:raise ValueError('工程配置超过 128 MB')
    if 1+len(models)+len(motions)+len(scenes)>300:raise ValueError('工程资源数量超过 299')
    assets=[];total=len(project_data)
    for names, src, prefix in ((models, root/'model', 'Assets/Models/'), (motions, root/'动作', 'Assets/Motions/'), (scenes, root/'场景', 'Assets/Scenes/')):
        for name in sorted(names):
            path=(src/name).resolve()
            if not path.is_file() and legacy_root is not None:
                old=(Path(legacy_root)/src.name/name).resolve()
                if old.parent==(Path(legacy_root)/src.name).resolve() and old.is_file():path=old
            if path.parent not in {src.resolve(),(Path(legacy_root)/src.name).resolve() if legacy_root is not None else src.resolve()} or not path.is_file():raise ValueError('找不到资源：'+name)
            size=path.stat().st_size
            if size>128*1024*1024:raise ValueError('单个资源超过 128 MB：'+name)
            total+=size
            if total>MAX_ARCHIVE:raise ValueError('工程包超过 512 MB，请减少资源后重试')
            if prefix in ('Assets/Motions/','Assets/Scenes/'):
                digest=hashlib.sha256()
                with path.open('rb') as stream:
                    for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
                suffix='.glb' if prefix=='Assets/Motions/' else '.blend'
                if name!=digest.hexdigest()+suffix:raise ValueError('工程资源校验失败：'+name)
            assets.append((path,prefix+name))
    with ZipFile(destination, 'w', ZIP_STORED, allowZip64=True) as z:
        z.writestr('project.previs',project_data)
        for path,name in assets:z.write(path,name)
    if Path(destination).stat().st_size>MAX_ARCHIVE:
        Path(destination).unlink();raise ValueError('工程包超过 512 MB，请减少资源后重试')

def read_bundle(data, root):
    try:
        with ZipFile(io.BytesIO(data)) as z:
            infos=z.infolist(); names=[x.filename for x in infos]
            if len(infos)>300 or len(set(names))!=len(names) or sum(x.file_size for x in infos)>MAX_ARCHIVE:raise ValueError('工程包过大或内容重复')
            if 'project.previs' not in names or z.getinfo('project.previs').file_size>128*1024*1024:raise ValueError('工程包缺少有效工程')
            project=json.loads(z.read('project.previs').decode('utf-8')); models,motions,scenes=references(project)
            expected={'project.previs'}|{'Assets/Models/'+n for n in models}|{'Assets/Motions/'+n for n in motions}|{'Assets/Scenes/'+n for n in scenes}
            if set(names)!=expected:raise ValueError('工程包资源不完整或包含未知文件')
            staged=[];renames={}
            for group,prefix,dirname in ((models,'Assets/Models/','model'),(motions,'Assets/Motions/','动作'),(scenes,'Assets/Scenes/','场景')):
                for name in group:
                    info=z.getinfo(prefix+name)
                    if info.file_size>128*1024*1024:raise ValueError('单个资源超过 128 MB')
                    content=z.read(info);digest=hashlib.sha256(content).hexdigest()
                    if dirname=='动作' and name!=digest+'.glb':raise ValueError('动作资源校验失败')
                    if dirname=='场景' and name!=digest+'.blend':raise ValueError('场景资源校验失败')
                    folder=root/dirname;target=folder/name
                    if target.resolve().parent!=folder.resolve():raise ValueError('资源目录存在无效链接')
                    if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=digest:
                        if dirname in ('动作','场景'):raise ValueError('工程资源冲突')
                        new=digest+'.glb';renames[name]=new;target=folder/new
                        if target.resolve().parent!=folder.resolve():raise ValueError('资源目录存在无效链接')
                        if target.exists() and hashlib.sha256(target.read_bytes()).hexdigest()!=digest:raise ValueError('模型资源冲突')
                    staged.append((target,content))
            for obj in project.get('objects',[]):
                source=obj.get('modelSource')
                if source and source['name'] in renames:source['name']=renames[source['name']]
            for target,content in staged:
                target.parent.mkdir(parents=True,exist_ok=True)
                if not target.exists():target.write_bytes(content)
            return project
    except (BadZipFile, KeyError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('无法读取工程包或资源不完整') from exc
