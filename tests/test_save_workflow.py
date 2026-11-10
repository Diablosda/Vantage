import test_environment
import os
import io,json,tempfile,unittest,sys
from pathlib import Path
from urllib.parse import urlsplit
from unittest.mock import patch
import server
from test_web_backend import fixture

class SaveWorkflowTests(unittest.TestCase):
 def handler(self,path,body=None):
  h=object.__new__(server.Handler);h.path=path;h.headers={'Host':'127.0.0.1:1234','X-Previs-Token':server.TOKEN};h.server=type('S',(),{'server_port':1234})();h.wfile=io.BytesIO();h.rfile=io.BytesIO(body or b'');h.status=None;h.response_headers={}
  h.send_response=lambda status:setattr(h,'status',status)
  h.send_header=lambda k,v:h.response_headers.__setitem__(k,v)
  h.end_headers=lambda:None
  if body is not None:h.headers['Content-Length']=str(len(body))
  return h
 def test_selected_destination_and_download_round_trip(self):
  server.RUNTIME.mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=server.RUNTIME.resolve()) as tmp:
   dest=Path(tmp)/'指定目录';dest.mkdir();p=fixture();p['name']='中文工程'
   with patch.object(server.threading.Thread,'start',lambda self:None):
    jid=server.submit({'mode':'save','project':p,'outputDirectory':str(dest)})
   job=server.JOBS[jid];job['state']='done'
   try:
    self.assertEqual(Path(job['directory']).parent,dest)
    h=self.handler(job['downloads']['bundle']);h.do_GET()
    self.assertEqual(h.status,200);self.assertEqual(h.response_headers['Content-Type'],'application/zip');self.assertIn('attachment',h.response_headers['Content-Disposition']);self.assertIn('filename*=',h.response_headers['Content-Disposition']);data=h.wfile.getvalue();self.assertTrue(data.startswith(b'PK\x03\x04'))
    h=self.handler('/api/project-bundle',data);h.do_POST();self.assertEqual(h.status,200);restored=json.loads(h.wfile.getvalue());self.assertEqual(restored['project'],p)
    h=self.handler(job['downloads']['project']);h.do_GET();self.assertEqual(h.status,200);self.assertIn('attachment',h.response_headers['Content-Disposition'])
    h=self.handler(job['downloads']['bundle'].rsplit('/',1)[0]+'/wrong.zip');h.do_GET();self.assertEqual(h.status,404)
   finally:server.JOBS.pop(jid,None)
 def test_html_is_not_accepted_as_zip(self):
  h=self.handler('/api/project-bundle',b'<html>not a ZIP</html>');h.do_POST();self.assertEqual(h.status,400);self.assertIn('ZIP',json.loads(h.wfile.getvalue())['error'])
 def test_bad_directory_is_rejected_before_creating_files(self):
  p=fixture()
  with self.assertRaisesRegex(ValueError,'保存目录'):
   server.submit({'mode':'save','project':p,'outputDirectory':'relative/path'})
class DesktopSaveTests(unittest.TestCase):
 def test_desktop_system_file_does_not_block_save(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
   desktop=Path(tmp)/'Desktop';desktop.mkdir();(desktop/'desktop.ini').write_text('system metadata')
   with patch.object(server.threading.Thread,'start',lambda self:None):ident=server.submit({'mode':'save','project':fixture(),'outputDirectory':str(desktop.resolve())})
   try:self.assertEqual(Path(server.JOBS[ident]['directory']).parent,desktop.resolve());self.assertEqual((desktop/'desktop.ini').read_text(),'system metadata')
   finally:server.JOBS.pop(ident,None)
 def test_native_directory_response_supports_desktop_and_cancel(self):
  for path in ['C:/Example/Desktop','']:
   with patch.object(server,'choose_path',return_value={'directory':path,'cancelled':not bool(path)}):
    h=SaveWorkflowTests().handler('/api/choose-directory',b'{}');h.do_POST();self.assertEqual(json.loads(h.wfile.getvalue())['directory'],path)

class LauncherTests(unittest.TestCase):
 def test_old_service_stays_running_and_new_service_uses_another_port(self):
  class FakeServer:
   def __init__(self,address,handler):self.address=address
   def serve_forever(self):pass
   def server_close(self):pass
  class ImmediateTimer:
   def __init__(self,seconds,func):self.func=func
   def start(self):self.func()
  def status(url,timeout):
   if ':8765/' in url:return io.BytesIO(b'{"app":"previs-local","version":"1.3.0"}')
   raise OSError('no server')
  opened=[];servers=[]
  def newserver(address,handler):
   value=FakeServer(address,handler);servers.append(value);return value
  with patch.object(sys,'argv',['server.py','--open']),patch.object(server.urllib.request,'urlopen',side_effect=status),patch.object(server,'ThreadingHTTPServer',side_effect=newserver),patch.object(server.threading,'Timer',ImmediateTimer),patch.object(server.webbrowser,'open',side_effect=opened.append):server.main()
  self.assertEqual(servers[0].address,('127.0.0.1',8766));self.assertEqual(opened,['http://127.0.0.1:8766/?legacyPort=8765'])
 def test_current_service_is_reused(self):
  data=io.BytesIO(json.dumps({'app':'previs-local','version':server.APP_VERSION,'build':server.BUILD_ID}).encode());opened=[]
  with patch.object(sys,'argv',['server.py','--open']),patch.object(server.urllib.request,'urlopen',return_value=data),patch.object(server,'ThreadingHTTPServer') as bind,patch.object(server.webbrowser,'open',side_effect=opened.append):server.main()
  bind.assert_not_called();self.assertEqual(opened,['http://127.0.0.1:8765'])
class ReleaseTests(unittest.TestCase):
 def test_build_changes_when_frontend_or_backend_changes(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
   root=Path(tmp);(root/'web').mkdir();(root/'backend').mkdir();(root/'ai_previs').mkdir()
   (root/'server.py').write_text('one');(root/'web'/'app.js').write_text('one');(root/'backend'/'model.py').write_text('one')
   first=server.source_build(root);(root/'web'/'app.js').write_text('two');second=server.source_build(root)
   self.assertNotEqual(first,second);(root/'backend'/'model.py').write_text('two');self.assertNotEqual(second,server.source_build(root))
 def test_web_snapshot_stays_coherent_during_file_update(self):
  with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as tmp:
   web=Path(tmp);(web/'app.js').write_bytes(b'new release')
   with patch.object(server,'WEB',web),patch.object(server,'WEB_FILES',{'app.js':b'running release'}):
    h=SaveWorkflowTests().handler('/app.js');h.do_GET();self.assertEqual(h.wfile.getvalue(),b'running release');self.assertEqual(h.response_headers['Cache-Control'],'no-store')
 def test_status_advertises_capabilities_and_current_build(self):
  h=SaveWorkflowTests().handler('/api/status');h.do_GET();data=json.loads(h.wfile.getvalue());self.assertEqual(data['build'],server.BUILD_ID);self.assertEqual(data['apiVersion'],1);self.assertIn('render-video',data['capabilities'])
if __name__=='__main__':unittest.main()
