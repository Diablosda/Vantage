"""Optional temporary GUI fixture; writes no scene or media files."""
import sys
from pathlib import Path
import bpy
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ai_previs
from ai_previs.operators import assign_nodes,activate
from ai_previs.geometry import Node
ai_previs.register();bpy.ops.previs.new()

def setup():
    bpy.ops.previs.primitive(shape='BOX');bpy.ops.previs.root(role='PROP');obj=bpy.context.object
    assign_nodes(obj,[Node((0,0,0)),Node((1.5,0,0),1.3,radius=.35),Node((1.5,1,0),2.7)])
    obj.previs.smooth=True
    bpy.ops.previs.camera();bpy.ops.previs.camera_mode()
    activate(bpy.context,obj)
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D' and area.spaces.active.region_3d.view_perspective!='CAMERA':
            region=next(r for r in area.regions if r.type=='WINDOW')
            with bpy.context.temp_override(area=area,region=region):bpy.ops.view3d.view_all(center=False)
    print('UI_FIXTURE_READY',flush=True)
    bpy.ops.ed.undo_push(message='临时界面测试初始状态')
    return None
bpy.app.timers.register(setup,first_interval=1.)
