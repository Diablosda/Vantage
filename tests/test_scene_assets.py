import test_environment
import os
import json, subprocess, tempfile, time, unittest
from pathlib import Path
import server
from backend.portable import create_bundle,read_bundle
from test_web_backend import fixture

ROOT=Path(__file__).resolve().parents[1]
BLENDER=server.BLENDER
class SceneAssetTests(unittest.TestCase):
 def test_blend_material_light_and_bundle_roundtrip(self):
  server.RUNTIME.mkdir(exist_ok=True)
  with tempfile.TemporaryDirectory(dir=server.RUNTIME) as folder:
   folder=Path(folder);old_projects=server.PROJECTS;server.PROJECTS=folder/'projects';self.addCleanup(setattr,server,'PROJECTS',old_projects);source=folder/'source.blend';script=folder/'create.py'
   script.write_text('''import bpy\nbpy.ops.wm.read_factory_settings(use_empty=True)\nbpy.ops.mesh.primitive_cube_add(location=(2,3,1))\no=bpy.context.object;o.name="测试场景墙"\ncoll=bpy.data.collections.new("内层集合");bpy.context.scene.collection.children.link(coll);coll.objects.link(o);bpy.context.scene.collection.objects.unlink(o)\nm=bpy.data.materials.new("测试材质");m.diffuse_color=(1,0,0,1);m.use_nodes=True;o.data.materials.append(m)\nimg=bpy.data.images.new("测试贴图",width=2,height=2);img.filepath_raw=str(__import__("pathlib").Path(bpy.data.filepath or __file__).with_suffix(".png"));img.file_format="PNG";img.save();m.node_tree.nodes.new("ShaderNodeTexImage").image=img\nbpy.ops.object.light_add(type="POINT",location=(3,4,5));bpy.context.object.name="测试灯光"\nbpy.ops.wm.save_as_mainfile(filepath=%r,relative_remap=False)\n''' % str(source),encoding='utf-8')
   proc=subprocess.run([str(BLENDER),'--background','--factory-startup','--python',str(script)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60);self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
   jobid=server.submit({'mode':'import','sourceName':'场景','snapshot':True},source.read_bytes())
   job=server.JOBS[jobid]
   for _ in range(600):
    if job['state'] in ('done','error'):break
    time.sleep(.1)
   self.assertEqual(job['state'],'done',job['message']);items=job['result']['objects'];wall=next(x for x in items if x['name']=='测试场景墙');lamp=next(x for x in items if x['name']=='测试灯光')
   self.assertEqual(lamp['sceneSource']['kind'],'LIGHT');self.assertIn(['内层集合'],wall['sceneSource']['collectionPaths']);self.assertEqual(wall['position'],[2,3,1]);self.assertEqual(len(wall['parts'][0]['materialIndices']),12);self.assertGreater(len(wall['parts'][0]['uvLayers']),0)
   project=fixture();project['objects']+=items
   sceneasset=server.DATA/'场景'/wall['sceneSource']['asset']
   try:
    self.assertEqual(server.validate(project),[])
    archive=folder/'project.zip';create_bundle(project,archive,server.DATA,legacy_root=ROOT);other=folder/'other';other.mkdir();recovered=read_bundle(archive.read_bytes(),other);self.assertEqual(recovered,project);self.assertEqual((other/'场景'/sceneasset.name).read_bytes(),sceneasset.read_bytes())
    jobid=server.submit({'mode':'save','project':project});job=server.JOBS[jobid]
    for _ in range(600):
     if job['state'] in ('done','error'):break
     time.sleep(.1)
    self.assertEqual(job['state'],'done',job['message'])
    blends=list(Path(job['directory']).glob('*.blend'));self.assertEqual(len(blends),1)
    check=folder/'check.py';check.write_text('''import bpy\nbpy.ops.wm.open_mainfile(filepath=%r)\nassert any(c.name.startswith("内层集合") for c in bpy.context.scene.collection.children)\nassert any(o.type=="LIGHT" and o.name.startswith("测试灯光") for o in bpy.context.scene.objects)\nassert any(i.name.startswith("测试贴图") and i.packed_file for i in bpy.data.images)\nassert any(o.type=="MESH" and len(o.data.uv_layers)>0 for o in bpy.context.scene.objects)\nassert any(o.type=="MESH" and any(m and m.name.startswith("测试材质") for m in o.data.materials) for o in bpy.context.scene.objects)\n''' % str(blends[0]),encoding='utf-8')
    proc=subprocess.run([str(BLENDER),'--background','--factory-startup','--python-exit-code','1','--python',str(check)],capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=60);self.assertEqual(proc.returncode,0,proc.stdout+proc.stderr)
    jobid=server.submit({'mode':'render','project':project});job=server.JOBS[jobid]
    for _ in range(1200):
     if job['state'] in ('done','error'):break
     time.sleep(.1)
    self.assertEqual(job['state'],'done',job['message']);self.assertTrue((Path(job['directory'])/'firstFrame.png').is_file());self.assertTrue((Path(job['directory'])/'lastFrame.png').is_file())
   finally:
    sceneasset.unlink(missing_ok=True)
if __name__=='__main__':unittest.main()

