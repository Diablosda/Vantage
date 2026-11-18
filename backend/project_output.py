"""Bound destinations for user-opened files and Vantage project folders."""
import os
from pathlib import Path
import re
import shutil
import uuid

_targets = {}

def stamp(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('原工程已移动或替换，请重新打开或另存为')
    info = path.stat()
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns

def bind_files(files):
    paths = {key: Path(value) for key, value in files.items()}
    token = uuid.uuid4().hex
    _targets[token] = (paths, {key: stamp(path) for key, path in paths.items()})
    return token

def opened_files(path):
    suffix = path.suffix.lower()
    kind = {'.zip':'bundle', '.previs':'project', '.blend':'blend'}[suffix]
    stem = path.name[:-len('.previs.zip')] if path.name.lower().endswith('.previs.zip') else path.stem
    siblings = {key:path.parent/(stem+ext) for key,ext in
                [('project','.previs'), ('bundle','.previs.zip'), ('blend','.blend')]}
    if (path == siblings[kind] and re.fullmatch(re.escape(stem)+r'_\d{8}_\d{6}_[0-9a-f]{6}', path.parent.name)
            and all(p.is_file() and not p.is_symlink() for p in siblings.values())):
        return siblings
    return {kind:path}

def destination(token):
    bound = _targets.get(token)
    if not bound:
        raise ValueError('原保存位置已失效，请重新打开工程或另存为')
    files, stamps = bound
    if any(stamp(path)!=stamps[key] for key,path in files.items()):
        raise ValueError('原工程文件已发生变化，请重新打开或另存为')
    return files

def publish(token, staged):
    files = destination(token)
    backups = {}
    replaced = []
    for key,path in files.items():
        backup = staged[key].with_suffix('.'+key+'.previous')
        try:
            os.link(path,backup)
        except OSError:
            shutil.copy2(path,backup)
        backups[key] = backup
    destination(token)
    try:
        for key,path in files.items():
            os.replace(staged[key],path)
            replaced.append(key)
    except OSError:
        for key in reversed(replaced):
            os.replace(backups[key],files[key])
            _targets[token][1][key]=stamp(files[key])
        raise
    return bind_files(files)
