import os,sys,time,json,subprocess,tempfile,threading,urllib.request
from pathlib import Path
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tests'))
from test_web_backend import fixture
class Old(BaseHTTPRequestHandler):
 def log_message(self,*a):pass
 def do_GET(self):
  data=json.dumps({'app':'previs-local','version':'1.0.0'}).encode();self.send_response(200);self.end_headers();self.wfile.write(data)
old=ThreadingHTTPServer(('127.0.0.1',0),Old);threading.Thread(target=old.serve_forever,daemon=True).start();pid=None
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
with tempfile.TemporaryDirectory(prefix='vantage-release-') as work:
 try:
  work=Path(work);capture=work/'capture.py';urlfile=work/'opened-url.txt';capture.write_text("import os,sys\nfrom pathlib import Path\nPath(os.environ['VANTAGE_CAPTURE_URL']).write_text(sys.argv[1])\n")
  env={**os.environ,'VANTAGE_DATA_DIR':str(work/'Data'),'VANTAGE_CACHE_DIR':str(work/'Cache'),'BROWSER':f'"{Path(sys.executable).as_posix()}" "{capture.as_posix()}" %s','VANTAGE_CAPTURE_URL':str(urlfile)}
  port=old.server_port
  def launch():
   urlfile.unlink(missing_ok=True);subprocess.run([str(ROOT/'Vantage.exe'),'--port',str(port)],env=env,check=True,timeout=15)
   until=time.monotonic()+25
   while not urlfile.exists() and time.monotonic()<until:time.sleep(.1)
   assert urlfile.exists(),'EXE did not open matching frontend'
   url=urlfile.read_text();data=json.load(opener.open(url.split('/?')[0]+'/api/status',timeout=5));return url,data
  url,status=launch();assert status['version']=='2.1.2' and status['build'];pid=status['pid'];url2,status2=launch();assert status2['pid']==pid
  p=fixture();p['objects'][0]['locatorColor']='#ff2040';p['objects'][0]['nodes'].insert(1,dict(position=[.325,0,0],time=.2,dwell=0,radius=0,easing='LINEAR'));p['settings']['snap']=True
  fp=work/'fixture.json';fp.write_text(json.dumps(p));dest=work/'output';dest.mkdir();(dest/'desktop.ini').write_text('system metadata');project_dest=work/'project-output';project_dest.mkdir()
  subprocess.run(['node',str(ROOT/'tests/browser_release.cjs')],env={**env,'PREVIS_URL':url,'VANTAGE_FIXTURE':str(fp),'VANTAGE_OUTPUT':str(dest),'VANTAGE_PROJECT_OUTPUT':str(project_dest),'VANTAGE_FFMPEG':str(ROOT.parent/'blender/tools/ffmpeg/ffmpeg.exe')},check=True,timeout=160)
  assert list(dest.rglob('*.mp4')) and list(project_dest.rglob('*.previs.zip'))
  print('PASS: real EXE opens matching release beside older service; repeat EXE reuses correct build; real outputs verified')
 finally:
  if pid:subprocess.run(['taskkill','/PID',str(pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
  old.shutdown();old.server_close()
