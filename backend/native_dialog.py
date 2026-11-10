"""STA Windows dialogs with a foreground owner, independent of browser restrictions."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import threading

_lock=threading.Lock()

def choose_path(root,kind='video',name='Vantage.mp4',directory=''):
    helper=Path(root)/'Vantage.Dialogs.exe'
    if not helper.is_file():raise ValueError('缺少保存窗口程序，请使用完整的最新版 Vantage')
    if not _lock.acquire(blocking=False):raise ValueError('保存窗口已经打开，请先完成或取消该窗口')
    try:
        with tempfile.TemporaryDirectory(prefix='vantage-dialog-') as work:
            result=Path(work)/'result.json'
            process=subprocess.run([str(helper),'--kind',kind,'--result',str(result),'--name',str(name),'--directory',str(directory)],capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
            if not result.is_file():raise ValueError('保存窗口未能打开，请重试或直接输入完整路径')
            answer=json.loads(result.read_text(encoding='utf-8-sig'))
            if process.returncode or answer.get('error'):raise ValueError('保存窗口失败：'+answer.get('error','请重试'))
            return answer
    except subprocess.TimeoutExpired:raise ValueError('保存窗口等待超时，请重新选择') from None
    finally:_lock.release()
