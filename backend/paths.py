"""Application files are read-only; user assets and caches live outside installation."""
import os
from pathlib import Path
APP_ROOT=Path(__file__).resolve().parents[1]

def data_root():
    value=os.environ.get('VANTAGE_DATA_DIR')
    if value:return Path(value).expanduser().resolve()
    base=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData'/'Local')
    return base/'Vantage'/'Data'

def cache_root():
    value=os.environ.get('VANTAGE_CACHE_DIR')
    if value:return Path(value).expanduser().resolve()
    base=Path(os.environ.get('LOCALAPPDATA') or Path.home()/'AppData'/'Local')
    return base/'Vantage'/'Cache'

def asset_file(folder,name,data=None,legacy=None):
    base=Path(data) if data is not None else data_root()
    target=(base/folder/name).resolve()
    if target.parent!=(base/folder).resolve():raise ValueError('资源路径无效')
    if target.is_file():return target
    old=((Path(legacy) if legacy is not None else APP_ROOT)/folder/name).resolve()
    if old.parent==((Path(legacy) if legacy is not None else APP_ROOT)/folder).resolve() and old.is_file():return old
    return target

def blender_path():
    if os.environ.get('PREVIS_BLENDER'):return Path(os.environ['PREVIS_BLENDER']).resolve()
    bundled=APP_ROOT/'runtime'/'blender'/'blender.exe'
    return bundled if bundled.is_file() else APP_ROOT.parent/'blender'/'blender-5.2.2-windows-x64'/'blender.exe'

def ffmpeg_path():
    if os.environ.get('PREVIS_FFMPEG'):return Path(os.environ['PREVIS_FFMPEG']).resolve()
    bundled=APP_ROOT/'runtime'/'ffmpeg'/'ffmpeg.exe'
    return bundled if bundled.is_file() else APP_ROOT.parent/'blender'/'tools'/'ffmpeg'/'ffmpeg.exe'

def blender_environment(data=None):
    env=dict(os.environ)
    for key in ('PYTHONHOME','PYTHONPATH'):env.pop(key,None)
    env['PYTHONDONTWRITEBYTECODE']='1';env['PYTHONNOUSERSITE']='1'
    env['BLENDER_USER_CONFIG']=str(cache_root()/'BlenderConfig')
    env['BLENDER_USER_SCRIPTS']=str((Path(data) if data is not None else data_root())/'BlenderScripts')
    return env
