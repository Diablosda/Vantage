import test_environment
import os
import json,tempfile,threading,unittest
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import server
from test_web_backend import fixture
import test_save_workflow as workflow
from backend.video_output import video_target,publish_video,file_stamp

class VideoOutputTests(unittest.TestCase):
 def work(self):return tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent)
 def test_only_mp4_is_published_at_exact_path(self):
  with self.work() as tmp:
   root=Path(tmp);source=root/'cache';source.mkdir();encoded=source/'encoded.mp4';encoded.write_bytes(b'new-video');dest=root/'Desktop';dest.mkdir();(dest/'desktop.ini').write_text('system')
   target,stamp=video_target(str((dest/'中文视频.mp4').resolve()));publish_video(encoded,target,stamp,threading.Event());self.assertEqual(sorted(p.name for p in dest.iterdir()),['desktop.ini','中文视频.mp4'])
 def test_overwrite_requires_confirmation(self):
  with self.work() as tmp:
   target=Path(tmp)/'existing.mp4';target.write_bytes(b'original')
   with self.assertRaises(ValueError):video_target(str(target.resolve()))
   self.assertEqual(target.read_bytes(),b'original')
 def test_cancelled_export_preserves_existing_video(self):
  with self.work() as tmp:
   target=Path(tmp)/'existing.mp4';target.write_bytes(b'original');source=Path(tmp)/'new';source.write_bytes(b'new');_,stamp=video_target(str(target.resolve()),True);cancel=threading.Event();cancel.set()
   with self.assertRaises(ValueError):publish_video(source,target,stamp,cancel)
   self.assertEqual(target.read_bytes(),b'original')
 def test_confirmed_overwrite_is_atomic_and_no_side_files(self):
  with self.work() as tmp:
   root=Path(tmp);target=root/'existing.mp4';target.write_bytes(b'original');source=root/'new';source.write_bytes(b'new');_,stamp=video_target(str(target.resolve()),True);publish_video(source,target,stamp,threading.Event());self.assertEqual(target.read_bytes(),b'new');self.assertEqual(sorted(p.name for p in root.iterdir()),['existing.mp4','new'])
 def test_external_change_is_preserved(self):
  with self.work() as tmp:
   root=Path(tmp);target=root/'existing.mp4';target.write_bytes(b'original');source=root/'new';source.write_bytes(b'new');stamp=file_stamp(target);target.write_bytes(b'user changed video')
   with self.assertRaises(ValueError):publish_video(source,target,stamp,threading.Event())
   self.assertEqual(target.read_bytes(),b'user changed video')
 def test_encoder_failure_does_not_touch_existing_video_and_cleans_cache(self):
  with self.work() as tmp:
   target=Path(tmp)/'existing.mp4';target.write_bytes(b'original')
   temporary=tempfile.TemporaryDirectory
   with patch.object(server.tempfile,'TemporaryDirectory',side_effect=lambda **kwargs:temporary(dir=tmp,**kwargs)):
    ident=server.submit_video({'mode':'preview','project':fixture(),'times':[0],'outputFile':str(target.resolve()),'overwrite':True})
   job=server.JOBS[ident];cache=Path(job['_temp'].name)
   try:
    with patch.object(server.subprocess,'Popen',return_value=SimpleNamespace(wait=lambda:1)):server.run_video_job(job,job['_payload'])
    self.assertEqual(job['state'],'error');self.assertEqual(target.read_bytes(),b'original');self.assertFalse(cache.exists());self.assertEqual(list(job['files']),['video'])
   finally:server.JOBS.pop(ident,None)
 def test_native_save_api_passes_filename_and_preserves_cancellation(self):
  for answer in [{'cancelled':True},{'outputFile':'C:/example/test.mp4','overwrite':True,'cancelled':False}]:
   with patch.object(server,'choose_path',return_value=answer) as choose:
    h=workflow.SaveWorkflowTests().handler('/api/choose-video',json.dumps({'name':'test.mp4','directory':'C:/example'}).encode());h.do_POST();self.assertEqual(json.loads(h.wfile.getvalue()),answer);choose.assert_called_once_with(server.ROOT,'video','test.mp4','C:/example')

 def test_browser_export_cache_is_released_after_file_write(self):
  with self.work() as tmp:
   temporary=tempfile.TemporaryDirectory
   with patch.object(server.tempfile,'TemporaryDirectory',side_effect=lambda **kwargs:temporary(dir=tmp,**kwargs)):
    ident=server.submit_video({'mode':'preview','project':fixture(),'times':[0],'browserSave':True})
   job=server.JOBS[ident];cache=Path(job['_temp'].name)
   try:
    job['state']='done';server.release_video(job);self.assertFalse(cache.exists());self.assertEqual(job['files'],{})
   finally:server.JOBS.pop(ident,None)
 def test_native_helper_result_protocol_supports_unicode_and_cancel(self):
  from backend import native_dialog
  for answer in [{'cancelled':True},{'cancelled':False,'outputFile':'C:/example/视频.mp4','overwrite':False}]:
   with self.work() as tmp:
    root=Path(tmp);(root/'Vantage.Dialogs.exe').write_bytes(b'test helper');temporary=tempfile.TemporaryDirectory
    def execute(command,**kwargs):
     Path(command[command.index('--result')+1]).write_text(json.dumps(answer),encoding='utf-8');return SimpleNamespace(returncode=0)
    with patch.object(native_dialog.tempfile,'TemporaryDirectory',side_effect=lambda **kwargs:temporary(dir=tmp,**kwargs)),patch.object(native_dialog.subprocess,'run',side_effect=execute):
     self.assertEqual(native_dialog.choose_path(root),answer)
 def test_missing_native_helper_reports_clear_error(self):
  from backend.native_dialog import choose_path
  with self.work() as tmp:
   with self.assertRaisesRegex(ValueError,'缺少保存窗口程序'):choose_path(Path(tmp))
