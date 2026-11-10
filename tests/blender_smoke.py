"""Temporary engineering checks, deliberately not the PRD's deferred acceptance scene."""
import sys
import tempfile
import subprocess
from pathlib import Path
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import ai_previs
from ai_previs import runtime
from ai_previs.operators import assign_nodes, edit_batch
from ai_previs.geometry import Node

ai_previs.register()
bpy.ops.previs.new()
scene=bpy.context.scene
bpy.ops.previs.primitive(shape='CUBE')
part=bpy.context.object
bpy.ops.previs.root(role='PROP')
root=bpy.context.object
relative=part.matrix_local.copy()
assign_nodes(root,[Node((0,0,0)),Node((.7,0,0),.4)])
bpy.ops.previs.primitive(shape='SPHERE')
bpy.ops.previs.root(role='PROP')
second=bpy.context.object
assign_nodes(second,[Node((0,1,0)),Node((0,1,.4),.4)])
bpy.ops.previs.camera()
camera=bpy.context.object
bpy.ops.previs.camera_mode()
with edit_batch():
    scene.previs.duration=.5;scene.previs.fps=12
    scene.previs.width=192;scene.previs.height=144
scene.frame_set(4)
assert root.location.x>0 and second.location.z>0
assert all(abs(a-b)<1e-5 for ra,rb in zip(part.matrix_local,relative) for a,b in zip(ra,rb))
with tempfile.TemporaryDirectory(prefix='.previs_smoke_',dir=ROOT) as tmp:
    project=str(Path(tmp)/'engineering.blend');video=str(Path(tmp)/'engineering.mp4')
    scene.previs.project_path=project;scene.previs.output_path=video
    assert bpy.ops.previs.export()=={'FINISHED'}
    assert Path(video).stat().st_size>1000
    ffmpeg=ROOT.parent/'blender'/'tools'/'ffmpeg'/'ffmpeg.exe'
    if ffmpeg.exists():
        probe=subprocess.run([str(ffmpeg),'-v','info','-i',video,'-f','null','-'],capture_output=True,text=True)
        assert probe.returncode==0,probe.stderr
        assert 'h264' in probe.stderr and '192x144' in probe.stderr and '12 fps' in probe.stderr,probe.stderr
    assert not root.animation_data
    bpy.ops.wm.open_mainfile(filepath=project)
    scene=bpy.context.scene
    root=next(o for o in scene.objects if o.previs.nodes and o.previs.nodes[-1].position.x>.5)
    assert len(root.previs.nodes)==2
    scene.frame_set(4)
    assert root.location.x>0
    print('PHASE_A_PASS: grouping, two-object playback, metadata save/reload, Workbench H264 MP4',flush=True)
ai_previs.unregister()
