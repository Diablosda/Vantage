"""Publish one MP4 after successful encoding, keeping existing files safe on failure."""
import os
from pathlib import Path
import shutil
import tempfile

def file_stamp(path):
    if not path.exists():return None
    stat=path.stat()
    return [stat.st_size,stat.st_mtime_ns]

def video_target(value,overwrite=False,*,suffix='.mp4'):
    if not isinstance(value,str) or not Path(value).is_absolute():raise ValueError('请选择保存位置，或输入完整文件路径')
    path=Path(value).resolve()
    if path.suffix.lower()!=suffix:raise ValueError('文件名必须以 '+suffix+' 结尾')
    if not path.parent.is_dir() or path.is_dir():raise ValueError('保存位置无效，请重新选择')
    stamp=file_stamp(path)
    if stamp is not None and not overwrite:raise ValueError('文件已存在，请在另存为窗口确认覆盖，或更换文件名')
    return path,stamp

def publish_video(source,target,expected,cancel):
    if cancel.is_set():raise ValueError('已取消导出')
    if file_stamp(target)!=expected:raise ValueError('目标文件在导出期间发生变化，请重新选择位置')
    stage=None
    try:
        with tempfile.NamedTemporaryFile(prefix='.vantage-',suffix=target.suffix,dir=target.parent,delete=False) as stream:stage=Path(stream.name)
        shutil.copyfile(source,stage)
        if cancel.is_set():raise ValueError('已取消导出')
        if file_stamp(target)!=expected:raise ValueError('目标文件在导出期间发生变化，请重新选择位置')
        if expected is not None:os.replace(stage,target)
        elif os.name=='nt':os.rename(stage,target)
        else:os.link(stage,target);stage.unlink()
    finally:
        if stage is not None:stage.unlink(missing_ok=True)
