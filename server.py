"""Loopback-only local application. No cloud, accounts, build step, or Blender window."""
import argparse
import hashlib
import struct
import json
import mimetypes
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs,unquote,quote
import urllib.request
import uuid
import webbrowser
from backend.paths import data_root,cache_root,asset_file,blender_path,ffmpeg_path,blender_environment
from backend.native_dialog import choose_path
from backend.video_output import video_target,publish_video
from backend.export_plan import export_times
from backend.model import validate
from backend.portable import create_bundle, read_bundle, MAX_ARCHIVE

ROOT=Path(__file__).resolve().parent
WEB=ROOT/'web';DATA=data_root();PROJECTS=DATA/'Projects';RUNTIME=cache_root()/'Jobs'
BLENDER=blender_path()
TOKEN=secrets.token_urlsafe(32);JOBS={};GATE=threading.Semaphore(1);APP_VERSION='2.1.2'
MAX_BODY=128*1024**2

# Capture one frontend release per running process, so updating files cannot mix
# new JavaScript with a previously loaded Python backend.
WEB_FILES={p.relative_to(WEB).as_posix():p.read_bytes() for p in WEB.rglob('*') if p.is_file()}
def source_build(root=ROOT,web_files=None):
    digest=hashlib.sha256(str(root.resolve()).encode())
    for folder in ('backend','ai_previs'):
        for path in sorted((root/folder).glob('*.py')):
            digest.update(path.relative_to(root).as_posix().encode());digest.update(path.read_bytes())
    digest.update((root/'server.py').read_bytes())
    for path in sorted((root/'launcher').glob('*.cs')):digest.update(path.read_bytes())
    if (root/'Vantage.Dialogs.exe').is_file():digest.update((root/'Vantage.Dialogs.exe').read_bytes())
    for name,data in sorted((web_files if web_files is not None else {p.relative_to(root/'web').as_posix():p.read_bytes() for p in (root/'web').rglob('*') if p.is_file()}).items()):
        digest.update(name.encode());digest.update(data)
    return digest.hexdigest()
INSTALL_ID=hashlib.sha256(str(ROOT.resolve()).encode()).hexdigest()
BUILD_ID=source_build(web_files=WEB_FILES)
CAPABILITIES=['native-save','video-only','save-directory','project-bundle','render-video','native-directory','preview-export','shot-export']

def run_job(job,payload,source=None):
    with GATE:
        if job['cancel'].is_set():job.update(state='cancelled',message='已取消');return
        job.update(state='running',message='正在读取场景' if payload['mode']=='import' else '正在准备工程',progress=3)
        try:
            if not BLENDER.is_file():raise ValueError('找不到本地渲染引擎，请检查项目内的 Blender 安装')
            RUNTIME.mkdir(parents=True,exist_ok=True)
            with tempfile.TemporaryDirectory(prefix='job-',dir=RUNTIME) as work:
                work=Path(work)
                if source is not None:
                    path=work/('source.zip' if payload['mode']=='convert' else 'source.blend');path.write_bytes(source);payload['source']=str(path)
                    if payload['mode']=='convert':payload['output']=str(work/'converted.glb')
                    elif payload['mode']=='import':payload['packedSource']=str(work/'packed.blend')
                if payload['mode']=='render' and payload.get('times'):payload['frameFolder']=str(work/'frames')
                payload['dataRoot']=str(DATA)
                task=work/'task.json';task.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
                flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
                process=subprocess.Popen([str(BLENDER),'--background','--factory-startup','--disable-autoexec','--python-use-system-env','--python-exit-code','1','--python',str(ROOT/'backend'/'blender_worker.py'),'--',str(task)],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',creationflags=flags,cwd=work,env=blender_environment(DATA))
                job['process']=process;tail=[]
                for line in process.stdout:
                    tail=(tail+[line.rstrip()])[-20:]
                    match=re.search(r'(?:Video append frame|Append frame)\s+(\d+)',line)
                    if match:
                        frame=int(match[1]);frames=job.get('frames',1)
                        job.update(progress=min(98,10+int(frame/frames*88)),message=f'正在渲染 {frame} / {frames} 帧')
                    if job['cancel'].is_set() and process.poll() is None:process.terminate()
                process.stdout.close();code=process.wait();job.pop('process',None)
                if job['cancel'].is_set():job.update(state='cancelled',message='已取消');return
                result_path=work/'result.json'
                result=json.loads(result_path.read_text(encoding='utf-8')) if result_path.exists() else {}
                if code or result.get('error'):raise ValueError(result.get('error') or '本地引擎未完成：'+'\n'.join(tail[-6:]))
                if payload['mode']=='convert':
                    data=Path(payload['output']).read_bytes();name=hashlib.sha256(data).hexdigest()+'.glb';folder=DATA/'model';folder.mkdir(parents=True,exist_ok=True)
                    target=folder/name
                    if not target.exists():target.write_bytes(data)
                    result['name']=name
                if payload['mode']=='import' and source is not None and not result.get('project') and not result.get('needsSnapshot'):
                    packed=Path(payload['packedSource']).read_bytes()
                    if len(packed)>MAX_BODY:raise ValueError('打包场景超过 128 MB')
                    asset=hashlib.sha256(packed).hexdigest()+'.blend';folder=DATA/'场景';folder.mkdir(parents=True,exist_ok=True)
                    target=folder/asset
                    if not target.exists():target.write_bytes(packed)
                    for obj in result.get('objects',[]):
                        if obj.get('sceneSource'):obj['sceneSource']['asset']=asset
                if payload.get('video'):
                    ffmpeg=ffmpeg_path()
                    if not ffmpeg.is_file():
                        found=shutil.which('ffmpeg')
                        if not found:raise ValueError('找不到首尾帧提取工具，请配置 PREVIS_FFMPEG 或将 FFmpeg 加入 PATH')
                        ffmpeg=Path(found)
                    if payload.get('frameFolder'):
                        command=[str(ffmpeg),'-v','error','-framerate',str(payload['project']['settings']['fps']),'-i',str(Path(payload['frameFolder'])/'%06d.png'),'-frames:v',str(job['frames']),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-y',payload['video']]
                        encoded=subprocess.run(command,capture_output=True,creationflags=flags)
                        if encoded.returncode:raise ValueError('视频编码失败')
                    for index,key in ((0,'firstFrame'),(job['frames']-1,'lastFrame')):
                        path=Path(job['directory'])/(key+'.png')
                        proc=subprocess.run([str(ffmpeg),'-v','error','-i',payload['video'],'-vf',rf'select=eq(n\,{index})','-frames:v','1','-y',str(path)],capture_output=True,creationflags=flags)
                        if proc.returncode or not path.is_file():raise ValueError('提取首尾帧失败')
                job.update(state='done',progress=100,message='已完成',result=result)
                if payload.get('blend'):
                    backup=Path(payload['blend']+'1')
                    if backup.exists():backup.unlink()
        except Exception as exc:job.update(state='error',message=str(exc),progress=0)
        finally:
            job.pop('process',None)
            cache=job.pop('_temp',None)
            if cache:cache.cleanup()
            job.pop('_payload',None)
            if job['state']!='done' and payload.get('video'):
                partial=Path(payload['video'])
                if partial.exists():partial.unlink()

def submit_video(payload):
    p=payload['project'];errors=validate(p,True,asset_root=DATA)
    if errors:raise ValueError('\n'.join(errors))
    browser_save=payload.pop('browserSave',False)
    if not browser_save:
        target,stamp=video_target(payload.pop('outputFile',None),payload.pop('overwrite',False))
        if shutil.disk_usage(target.parent).free<128*1024**2:raise ValueError('输出磁盘空间不足')
    ident=uuid.uuid4().hex;cache=tempfile.TemporaryDirectory(prefix='vantage-video-');work=Path(cache.name)
    if browser_save:target,stamp=work/'result.mp4',None
    payload.update(video=str(work/'encoded.mp4'),blend=str(work/'scene.blend'),frameFolder=str(work/'frames'))
    Path(payload['frameFolder']).mkdir()
    job={'id':ident,'state':'uploading' if payload['mode']=='preview' else 'queued','progress':0,'message':'正在准备视频','cancel':threading.Event(),'frames':len(payload['times']),'directory':str(target.parent),'outputFile':str(target),'files':{'video':str(target)},'downloads':{'video':'/api/downloads/'+ident+'/video/'+quote(target.name,safe='')},'_temp':cache,'_received':0,'_payload':payload,'_targetStamp':stamp,'_videoOnly':True,'_browserSave':browser_save}
    JOBS[ident]=job
    if payload['mode']=='render':threading.Thread(target=run_video_job,args=(job,payload),daemon=True).start()
    return ident

def run_video_job(job,payload):
    try:
        with GATE:
            if job['cancel'].is_set():job['state']='cancelled';return
            job.update(state='running',message='正在渲染视频' if payload['mode']=='render' else '正在编码视频',progress=80)
            work=Path(job['_temp'].name);flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
            if payload['mode']=='render':
                if not BLENDER.is_file():raise ValueError('找不到 Blender 引擎')
                payload['dataRoot']=str(DATA)
                task=work/'task.json';task.write_text(json.dumps(payload,ensure_ascii=False),encoding='utf-8')
                process=subprocess.Popen([str(BLENDER),'--background','--factory-startup','--disable-autoexec','--python-use-system-env','--python-exit-code','1','--python',str(ROOT/'backend'/'blender_worker.py'),'--',str(task)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags,cwd=work,env=blender_environment(DATA))
                job['process']=process;code=process.wait();job.pop('process',None)
                result_path=work/'result.json';answer=json.loads(result_path.read_text(encoding='utf-8')) if result_path.is_file() else {}
                if not job['cancel'].is_set() and (code or answer.get('error')):raise ValueError(answer.get('error','光影渲染失败'))
            if job['cancel'].is_set():job['state']='cancelled';return
            ffmpeg=ffmpeg_path()
            if not ffmpeg.is_file():ffmpeg=shutil.which('ffmpeg')
            if not ffmpeg:raise ValueError('找不到 FFmpeg 编码工具')
            command=[str(ffmpeg),'-v','error','-framerate',str(payload['project']['settings']['fps']),'-i',str(Path(payload['frameFolder'])/'%06d.png'),'-frames:v',str(job['frames']),'-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-y',payload['video']]
            process=subprocess.Popen(command,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=flags);job['process']=process;code=process.wait();job.pop('process',None)
            if job['cancel'].is_set():job['state']='cancelled';return
            if code or not Path(payload['video']).is_file():raise ValueError('视频编码失败')
            publish_video(payload['video'],Path(job['outputFile']),job['_targetStamp'],job['cancel'])
            job.update(state='done',progress=100,message='视频已保存')
    except Exception as exc:job.update(state='cancelled' if job['cancel'].is_set() else 'error',message=str(exc),progress=0)
    finally:
        job.pop('process',None);job.pop('_payload',None)
        if job.get('_browserSave') and job['state']=='done':
            timer=threading.Timer(1800,release_video,args=(job,));timer.daemon=True;timer.start()
        else:release_video(job)

def release_video(job):
    cache=job.pop('_temp',None)
    if cache:cache.cleanup()
    if job.get('_browserSave'):job['files']={}

def submit(payload,source=None):
    ident=uuid.uuid4().hex
    job={'id':ident,'state':'queued','progress':0,'message':'等待本地引擎','cancel':threading.Event(),'downloads':{}}
    if payload['mode'] not in ('import','convert'):
        p=payload['project'];errors=validate(p,payload['mode'] in ('render','preview'),asset_root=DATA)
        if errors:raise ValueError('\n'.join(errors))
        destination=payload.pop('outputDirectory',None)
        if destination:
            if not isinstance(destination,str) or not Path(destination).is_absolute():raise ValueError('保存目录必须是本机绝对路径')
            parent=Path(destination).resolve()
            if not parent.is_dir():raise ValueError('保存目录不存在，请重新选择')
        else:
            PROJECTS.mkdir(parents=True,exist_ok=True);parent=PROJECTS.resolve()
        if shutil.disk_usage(parent).free<max(128*1024**2,p['settings']['duration']*4*1024**2):raise ValueError('输出磁盘空间不足')
        name=re.sub(r'[^\w\-\u4e00-\u9fff]','_',str(p.get('name','未命名工程')))[:60] or '未命名工程'
        folder=parent/(name+'_'+time.strftime('%Y%m%d_%H%M%S')+'_'+ident[:6]);folder.mkdir()
        model=folder/(name+'.previs');model.write_text(json.dumps(p,ensure_ascii=False),encoding='utf-8')
        payload['blend']=str(folder/(name+'.blend'))
        if payload['mode'] in ('render','preview'):payload['video']=str(folder/(name+'.mp4'))
        bundle=folder/(name+'.previs.zip');create_bundle(p,bundle,DATA,legacy_root=ROOT)
        files={'project':model,'bundle':bundle,'blend':Path(payload['blend'])}
        if payload.get('video'):
            files['video']=Path(payload['video']);files['firstFrame']=folder/'firstFrame.png';files['lastFrame']=folder/'lastFrame.png'
        job['files']={k:str(v) for k,v in files.items()}
        job['downloads']={k:'/api/downloads/'+ident+'/'+k+'/'+quote(v.name,safe='') for k,v in files.items()}
        job['directory']=str(folder);job['frames']=len(payload['times']) if payload.get('times') else max(1,round(p['settings']['fps']*p['settings']['duration']))
    JOBS[ident]=job
    if payload['mode']=='preview':
        cache=tempfile.TemporaryDirectory(prefix='vantage-frames-');job['_temp']=cache;payload['frameFolder']=cache.name;job['_payload']=payload;job['_received']=0;job['state']='uploading'
    else:threading.Thread(target=run_job,args=(job,payload,source),daemon=True).start()
    return ident

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def valid_host(self):return self.headers.get('Host','') in {f'127.0.0.1:{self.server.server_port}',f'localhost:{self.server.server_port}'}
    def headers_out(self,status,mime,length,extra=None):
        self.send_response(status);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(length))
        self.send_header('X-Content-Type-Options','nosniff');self.send_header('Cache-Control','no-store')
        self.send_header('Content-Security-Policy',"default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src 'self' blob:; object-src 'none'; frame-ancestors 'none'")
        for k,v in (extra or {}).items():self.send_header(k,v)
        self.end_headers()
    def json(self,value,status=200):
        data=json.dumps(value,ensure_ascii=False).encode();self.headers_out(status,'application/json; charset=utf-8',len(data));self.wfile.write(data)
    def do_GET(self):
        if not self.valid_host():self.json({'error':'Invalid host'},403);return
        path=unquote(urlparse(self.path).path)
        if path=='/api/models':
            folder=DATA/'model';folder.mkdir(parents=True,exist_ok=True)
            models={p.name:p for p in (ROOT/'model').glob('*.glb') if p.is_file() and not p.is_symlink()};models.update({p.name:p for p in folder.glob('*.glb') if p.is_file() and not p.is_symlink()});self.json({'models':[{'name':name,'size':p.stat().st_size} for name,p in sorted(models.items())]});return
        if path=='/api/status':self.json({'app':'previs-local','version':APP_VERSION,'build':BUILD_ID,'installation':INSTALL_ID,'apiVersion':1,'capabilities':CAPABILITIES,'pid':os.getpid(),'engineReady':BLENDER.is_file(),'token':TOKEN,'defaultOutputDirectory':str(PROJECTS.resolve())});return
        if path.startswith('/api/jobs/'):
            job=JOBS.get(path.rsplit('/',1)[-1])
            self.json({k:v for k,v in job.items() if k not in ('process','cancel','files') and not k.startswith('_')} if job else {'error':'任务不存在'},200 if job else 404);return
        if path.startswith('/api/downloads/'):
            parts=path.split('/',5)
            if len(parts)!=6:self.json({'error':'下载链接无效'},404);return
            _,_,_,ident,key,filename=parts;job=JOBS.get(ident);filepath=Path(job['files'][key]) if job and job.get('state')=='done' and key in job.get('files',{}) else None
            if not filepath or filename!=filepath.name or not filepath.is_file():self.json({'error':'文件不存在或任务尚未完成'},404);return
            inline=parse_qs(urlparse(self.path).query).get('inline')==['1'] and key=='video';self.send_file(filepath,attachment=not inline,inline=inline);return
        base=(DATA/'model') if path.startswith('/models/') else (DATA/'动作') if path.startswith('/motions/') else PROJECTS if path.startswith('/files/') else WEB
        relative=path[len('/models/'):] if path.startswith('/models/') else path[len('/motions/'):] if path.startswith('/motions/') else path[len('/files/'):]  if base==PROJECTS else path.lstrip('/') or 'index.html'
        target=(base/relative).resolve()
        if path.startswith(('/models/','/motions/')) and not target.is_file():target=asset_file('model' if path.startswith('/models/') else '动作',relative,DATA,ROOT)
        if path.startswith(('/models/','/motions/')) and target.parent==(ROOT/('model' if path.startswith('/models/') else '动作')).resolve():base=target.parent
        if base==WEB:
            if not target.is_relative_to(WEB.resolve()):self.json({'error':'文件不存在'},404);return
            key=target.relative_to(WEB.resolve()).as_posix();data=WEB_FILES.get(key)
            if data is None:self.json({'error':'文件不存在'},404);return
            mime='text/javascript' if target.suffix=='.js' else mimetypes.guess_type(key)[0] or 'application/octet-stream'
            self.headers_out(200,mime,len(data));self.wfile.write(data);return
        if not target.is_relative_to(base.resolve()) or not target.is_file():self.json({'error':'文件不存在'},404);return
        self.send_file(target,attachment=path.startswith('/files/'))
    def send_file(self,target,attachment=False,inline=False):
        size=target.stat().st_size;start=0;end=size-1;status=200;extra={}
        rng=self.headers.get('Range','')
        if rng:
            match=re.fullmatch(r'bytes=(\d+)-(\d*)',rng)
            if not match:self.json({'error':'Invalid range'},416);return
            start=int(match[1]);end=min(end,int(match[2])) if match[2] else end
            if start>end or start>=size:self.json({'error':'Invalid range'},416);return
            status=206;extra['Content-Range']=f'bytes {start}-{end}/{size}'
        mime={'.js':'text/javascript','.previs':'application/json','.blend':'application/octet-stream','.zip':'application/zip'}.get(target.suffix.lower(),mimetypes.guess_type(str(target))[0] or 'application/octet-stream')
        if attachment or target.suffix.lower()=='.zip' or inline:
            extra['Content-Disposition']=(('inline' if inline else 'attachment')+'; filename="'+('project.previs.zip' if target.name.endswith('.previs.zip') else 'download'+target.suffix.lower())+'"; filename*=UTF-8\'\''+quote(target.name,safe=''))
        extra['Accept-Ranges']='bytes';self.headers_out(status,mime,end-start+1,extra)
        try:
            with target.open('rb') as stream:
                stream.seek(start);remaining=end-start+1
                while remaining:
                    data=stream.read(min(1024*1024,remaining));self.wfile.write(data);remaining-=len(data)
        except (BrokenPipeError,ConnectionResetError):pass
    def do_POST(self):
        origin=self.headers.get('Origin')
        if not self.valid_host() or self.headers.get('X-Previs-Token')!=TOKEN or (origin and origin not in {f'http://127.0.0.1:{self.server.server_port}',f'http://localhost:{self.server.server_port}'}):
            self.json({'error':'请求校验失败，请刷新工作台'},403);return
        try:
            url=urlparse(self.path);length=int(self.headers.get('Content-Length','0'))
            limit=MAX_ARCHIVE if url.path=='/api/project-bundle' else MAX_BODY
            if not 0<length<=limit:raise ValueError('文件超过大小限制')
            raw=self.rfile.read(length)
            if url.path=='/api/project-bundle':
                if not raw.startswith(b'PK\x03\x04'):raise ValueError('选择的不是 ZIP 工程包；请使用保存目录中的 .previs.zip 文件')
                project=read_bundle(raw,DATA);errors=validate(project,asset_root=DATA)
                if errors:raise ValueError('；'.join(errors))
                self.json({'project':project});return
            if url.path=='/api/motions':
                query=parse_qs(url.query); name=query.get('model',[''])[0]
                source=asset_file('model',name,DATA,ROOT)
                if source.parent not in {(DATA/'model').resolve(),(ROOT/'model').resolve()} or source.suffix.lower()!='.glb' or not source.is_file():raise ValueError('请先将对象替换为原始 GLB 模型')
                def gltf(blob):
                    if len(blob)<20 or blob[:4]!=b'glTF' or struct.unpack_from('<I',blob,4)[0]!=2 or struct.unpack_from('<I',blob,8)[0]!=len(blob):raise ValueError('请选择有效的 GLB 文件')
                    size,kind=struct.unpack_from('<I4s',blob,12)
                    if kind!=b'JSON' or size>len(blob)-20:raise ValueError('GLB 文件无效')
                    return json.loads(blob[20:20+size])
                motion=gltf(raw);model=gltf(source.read_bytes()); clips=motion.get('animations',[])
                if len(clips)!=1:raise ValueError('动作文件必须包含一个动画片段')
                mn=motion.get('nodes',[]);tn=model.get('nodes',[]);target_parents={child:i for i,n in enumerate(tn) for child in n.get('children',[])};joints={i for skin in motion.get('skins',[]) for i in skin.get('joints',[])}
                parents={child:i for i,n in enumerate(mn) for child in n.get('children',[])}
                for joint in list(joints):
                    while joint in parents:
                        joint=parents[joint]
                        if joint in joints:break
                        joints.add(joint)
                byname={n.get('name'):n for n in tn if n.get('name')};targets=[]
                for c in clips[0].get('channels',[]):
                    target=c.get('target',{}); idx=target.get('node')
                    if not isinstance(idx,int) or not 0<=idx<len(mn) or idx not in joints or target.get('path') not in ('translation','rotation','scale'):raise ValueError('仅支持作用于模型骨骼的 GLB 动作')
                    node=mn[idx];name=node.get('name');other=byname.get(name)
                    if other is not None:
                        target_index=tn.index(other);mp=parents.get(idx);tp=target_parents.get(target_index)
                        if (mn[mp].get('name') if mp is not None else None)!=(tn[tp].get('name') if tp is not None else None):raise ValueError('动作骨架层级与模型不一致')
                    if not name or other is None or any(node.get(k)!=other.get(k) for k in ('translation','rotation','scale','matrix')):raise ValueError('动作骨架与模型不一致，需使用同一模型骨架制作的 GLB')
                    targets.append(name)
                if not targets:raise ValueError('文件没有骨骼动作')
                folder=DATA/'动作';folder.mkdir(parents=True,exist_ok=True); filename=hashlib.sha256(raw).hexdigest()+'.glb';dest=folder/filename
                if not dest.exists():dest.write_bytes(raw)
                self.json({'name':filename,'clip':clips[0].get('name','动作')});return
            if url.path=='/api/models/upload':
                query=parse_qs(url.query);name=query.get('name',[''])[0];suffix=Path(name).suffix.lower()
                if suffix=='.glb':
                    if len(raw)<20 or raw[:4]!=b'glTF' or struct.unpack_from('<I',raw,4)[0]!=2 or struct.unpack_from('<I',raw,8)[0]!=len(raw):raise ValueError('请选择有效的 GLB 文件')
                    folder=DATA/'model';folder.mkdir(parents=True,exist_ok=True);target=folder/(hashlib.sha256(raw).hexdigest()+'.glb')
                    if not target.exists():target.write_bytes(raw)
                    self.json({'name':target.name});return
                if suffix not in ('.gltf','.zip'):raise ValueError('请选择 GLB、内嵌资源的 glTF 或 glTF 资源 ZIP')
                self.json({'job':submit({'mode':'convert','kind':suffix[1:]},raw)},202);return
            if url.path=='/api/import':
                query=parse_qs(url.query)
                if raw[:7]!=b'BLENDER' and raw[:2]!=b'\x1f\x8b' and raw[:4]!=b'\x28\xb5\x2f\xfd':raise ValueError('请选择有效的 .blend 文件')
                job=submit({'mode':'import','sourceName':query.get('name',['静态场景'])[0],'snapshot':query.get('snapshot',['0'])[0]=='1','frame':int(query.get('frame',['1'])[0])},raw)
                self.json({'job':job},202);return
            if url.path.startswith('/api/preview-frame/'):
                ident=url.path.rsplit('/',1)[-1];job=JOBS.get(ident)
                if not job or job['state']!='uploading' or job['cancel'].is_set():raise ValueError('导出已取消或不存在')
                if not raw.startswith(b'\x89PNG\r\n\x1a\n') or len(raw)<24:raise ValueError('无效 PNG 帧')
                p=job['_payload']['project'];width,height=struct.unpack('>II',raw[16:24])
                if (width,height)!=(p['settings']['width'],p['settings']['height']):raise ValueError('导出帧尺寸不一致')
                index=job['_received']
                if index>=job['frames']:raise ValueError('帧数超出范围')
                (Path(job['_payload']['frameFolder'])/f'{index:06d}.png').write_bytes(raw);job['_received']+=1;job['progress']=int(80*job['_received']/job['frames'])
                self.json({'received':job['_received']});return
            data=json.loads(raw)
            if url.path=='/api/models/import':
                source=asset_file('model',data['name'],DATA,ROOT)
                if source.parent not in {(DATA/'model').resolve(),(ROOT/'model').resolve()} or source.suffix.lower()!='.glb' or not source.is_file():raise ValueError('模型不存在')
                self.json({'job':submit({'mode':'import','source':str(source),'sourceName':source.stem,'glb':True,'snapshot':True})},202);return
            if url.path=='/api/shutdown':
                if any(j['state'] in ('queued','running','uploading') for j in JOBS.values()):self.json({'error':'仍有任务正在运行'},409);return
                self.json({'stopping':True});threading.Thread(target=self.server.shutdown,daemon=True).start();return
            if url.path in ('/api/choose-directory','/api/choose-video'):
                answer=choose_path(ROOT,'video' if url.path.endswith('choose-video') else 'directory',data.get('name','Vantage.mp4'),data.get('directory',''))
                self.json(answer);return
            if url.path=='/api/video-release':
                job=JOBS.get(data['job'])
                if not job or not job.get('_browserSave') or job['state']!='done':raise ValueError('视频尚未完成')
                release_video(job);self.json({'released':True});return
            if url.path=='/api/preview-finish':
                job=JOBS.get(data['job'])
                if not job or job['state']!='uploading' or job['_received']!=job['frames']:raise ValueError('导出帧尚未上传完整')
                job['state']='queued';threading.Thread(target=run_video_job if job.get('_videoOnly') else run_job,args=(job,job['_payload']),daemon=True).start();self.json({'job':data['job']});return
            if url.path in ('/api/save','/api/export'):
                if url.path=='/api/export':
                    times=export_times(data['project'],data.get('scope','all'),data.get('owner'),data.get('segment'))
                    mode='render' if data.get('lighting',False) else 'preview'
                    ident=submit_video({'mode':mode,'project':data['project'],'outputFile':data.get('outputFile'),'overwrite':data.get('overwrite') is True,'browserSave':data.get('browserSave') is True,'times':times})
                    self.json({'job':ident,'times':times if mode=='preview' else None},202);return
                self.json({'job':submit({'mode':'render' if url.path.endswith('export') else 'save','project':data['project'],'outputDirectory':data.get('outputDirectory')})},202);return
            if url.path=='/api/validate':self.json({'errors':validate(data['project'],data.get('export',False),asset_root=DATA)});return
            if url.path.endswith('/cancel'):
                job=JOBS.get(url.path.split('/')[-2])
                if job and job['state'] in ('queued','running','uploading'):
                    job['cancel'].set();process=job.get('process')
                    if process and process.poll() is None:process.terminate()
                    if job['state']=='uploading':
                        job['state']='cancelled';job.pop('_temp').cleanup();job.pop('_payload',None)
                self.json({'cancelled':True});return
            self.json({'error':'Unknown action'},404)
        except (ValueError,KeyError,TypeError,OSError) as exc:self.json({'error':str(exc)},400)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=8765);parser.add_argument('--open',action='store_true');parser.add_argument('--stop',action='store_true');args=parser.parse_args()
    if args.stop:
        failed=False
        for candidate in range(8765,8866):
            ours=False
            try:
                status=json.load(urllib.request.urlopen(f'http://127.0.0.1:{candidate}/api/status',timeout=.15))
                if status.get('installation')!=INSTALL_ID:continue
                ours=True
                request=urllib.request.Request(f'http://127.0.0.1:{candidate}/api/shutdown',data=b'{}',headers={'X-Previs-Token':status['token'],'Content-Type':'application/json'})
                urllib.request.urlopen(request,timeout=2).close()
                time.sleep(.6)
            except urllib.error.HTTPError:
                if ours:failed=True
            except (OSError,ValueError):
                if ours:failed=True
        if failed:raise SystemExit(2)
        return
    port=args.port;legacy_port=None;server=None
    if args.open:
        def existing(port):
            try:return json.load(urllib.request.urlopen(f'http://127.0.0.1:{port}/api/status',timeout=1))
            except Exception:return None
        current=existing(port)
        if current and current.get('app')=='previs-local':
            if current.get('version')==APP_VERSION and current.get('build')==BUILD_ID:webbrowser.open(f'http://127.0.0.1:{port}');return
            legacy_port=port
            # Keep the user's older session alive; reuse or start a newer server on another loopback port.
            for candidate in range(port+1,min(port+101,65536)):
                found=existing(candidate)
                if found and found.get('app')=='previs-local' and found.get('version')==APP_VERSION and found.get('build')==BUILD_ID:
                    webbrowser.open(f'http://127.0.0.1:{candidate}/?legacyPort={legacy_port}');return
                if found:continue
                try:server=ThreadingHTTPServer(('127.0.0.1',candidate),Handler);port=candidate;break
                except OSError:continue
            if server is None:raise OSError('没有可用的本机端口，请关闭旧版工作台后重试')
    if server is None:server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    url=f'http://127.0.0.1:{port}'+(f'/?legacyPort={legacy_port}' if legacy_port is not None else '')
    if args.open:threading.Timer(.5,lambda:webbrowser.open(url)).start()
    print('Vantage: '+url,flush=True)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:
        for job in JOBS.values():
            job['cancel'].set();process=job.get('process')
            if process and process.poll() is None:process.terminate()
        server.server_close()
if __name__=='__main__':main()
