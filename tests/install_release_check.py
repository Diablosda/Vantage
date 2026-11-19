"""Install offline in isolation, exercise installed EXE, then uninstall without data loss."""
import os,sys,time,json,socket,subprocess,urllib.request,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from test_web_backend import fixture
work=ROOT/'.release-work'/'acceptance-2.1.4'
if work.exists():raise SystemExit('Choose a fresh acceptance directory')
work.mkdir(parents=True);install=work/'Installed';data=work/'UserData';cache=work/'UserCache';output=work/'Videos';projects=work/'Projects'
for p in [data,cache,output,projects]:p.mkdir()
(data/'keep-user-data.txt').write_text('must survive uninstall')
(output/'desktop.ini').write_text('system metadata')
setup=ROOT/'dist'/'Vantage-2.1.4-Setup.exe'
result=subprocess.run([str(setup),'/S','/TEST=1','/D='+str(install)],timeout=180);assert result.returncode==0
assert (install/'Vantage.exe').is_file() and (install/'runtime/blender/blender.exe').is_file()
(install/'keep-custom-file.txt').write_text('uninstaller must preserve unknown files')
def snapshot():return {p.relative_to(install).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in install.rglob('*') if p.is_file()}
before=snapshot();env={**os.environ,'VANTAGE_DATA_DIR':str(data),'VANTAGE_CACHE_DIR':str(cache),'PYTHONDONTWRITEBYTECODE':'1','PATH':os.environ.get('SystemRoot','C:/Windows')+'/System32'}
for key in ['PREVIS_BLENDER','PREVIS_FFMPEG','PYTHONPATH','PYTHONHOME']:env.pop(key,None)
assert subprocess.run([str(install/'Vantage.exe'),'--check'],env=env,timeout=15).returncode==0
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));status=None;success=False
try:
 for candidate in range(8820,8866):
  sock=socket.socket()
  try:sock.bind(('127.0.0.1',candidate));port=candidate;break
  except OSError:continue
  finally:sock.close()
 subprocess.run([str(install/'Vantage.exe'),'--no-open','--port',str(port)],env=env,check=True,timeout=15)
 for _ in range(100):
  try:status=json.load(opener.open(f'http://127.0.0.1:{port}/api/status',timeout=1));break
  except OSError:time.sleep(.1)
 assert status and status['version']=='2.1.4' and status['engineReady']
 assert Path(status['defaultOutputDirectory'])==data/'Projects'
 assert json.load(opener.open(f'http://127.0.0.1:{port}/api/models'))=={'models':[]}
 p=fixture();p['objects'][0]['locatorColor']='#ff2040';p['objects'][0]['nodes'].insert(1,dict(position=[.325,0,0],time=.2,dwell=0,radius=0,easing='LINEAR'));p['settings']['snap']=True;source=work/'fixture.json';source.write_text(json.dumps(p))
 testenv={**os.environ,'PREVIS_URL':f'http://127.0.0.1:{port}','VANTAGE_FIXTURE':str(source),'VANTAGE_OUTPUT':str(output),'VANTAGE_PROJECT_OUTPUT':str(projects),'VANTAGE_FFMPEG':str(install/'runtime/ffmpeg/ffmpeg.exe')}
 subprocess.run(['node',str(ROOT/'tests/browser_release.cjs')],env=testenv,check=True,timeout=180)
 after=snapshot();added=sorted(set(after)-set(before));changed=[p for p in before if before[p]!=after.get(p)]
 print('Installation folder additions:',added,flush=True);print('Installation folder changed files:',changed,flush=True)
 assert not added and not changed,'Application wrote to installation folder'
 assert list(projects.rglob('*.previs.zip')) and (output/'all.mp4').is_file()
 success=True
finally:
 if status and not success:subprocess.run(['taskkill','/PID',str(status['pid']),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import threading
class Foreign(BaseHTTPRequestHandler):
 def log_message(self,*args):pass
 def do_GET(self):self.send_response(404 if self.path=='/api/status' else 200);self.end_headers();self.wfile.write(b'alive')
for candidate in range(8765,8820):
 try:foreign=ThreadingHTTPServer(('127.0.0.1',candidate),Foreign);break
 except OSError:continue
threading.Thread(target=foreign.serve_forever,daemon=True).start()
try:
 subprocess.run([str(install/'Uninstall.exe'),'/S'],env=env,timeout=60)
 for _ in range(300):
  if not (install/'Vantage.exe').exists():break
  time.sleep(.1)
 assert not (install/'Vantage.exe').exists()
 assert opener.open(f'http://127.0.0.1:{foreign.server_port}/ping').read()==b'alive'
 assert (install/'keep-custom-file.txt').read_text()=='uninstaller must preserve unknown files'
 assert (data/'keep-user-data.txt').read_text()=='must survive uninstall'
 assert (output/'all.mp4').is_file() and list(projects.rglob('*.previs.zip'))
 print('PASS: offline install, bundled engines with stripped PATH, no installation writes, uninstall stops owned service, ignores foreign 404, preserves user data and custom files',flush=True)
finally:
 foreign.shutdown();foreign.server_close()
 if status:subprocess.run(['taskkill','/PID',str(status['pid']),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
