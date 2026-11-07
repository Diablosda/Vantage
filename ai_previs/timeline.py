"""Compact product tracks over Blender's shared, zoomable Timeline."""
import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from . import runtime
from .operators import activate

_handle=None
_keymaps=[]
ROW=23

def track_objects(scene):
    return [o for o in runtime.controls(scene) if o.previs.nodes or o.previs.angles or o.previs.lenses]

def rect(x0,y0,x1,y1,color):
    shader=gpu.shader.from_builtin('UNIFORM_COLOR');shader.bind();shader.uniform_float('color',color)
    batch_for_shader(shader,'TRIS',{'pos':[(x0,y0),(x1,y0),(x1,y1),(x0,y0),(x1,y1),(x0,y1)]}).draw(shader)

def text(x,y,value,color=(.85,.87,.9,1)):
    blf.position(0,x,y,0);blf.size(0,11);blf.color(0,*color);blf.draw(0,value)

def draw():
    c=bpy.context
    if not c.scene or not c.scene.previs.enabled or c.space_data.mode!='TIMELINE':return
    s=c.scene;region=c.region;v=region.view2d
    objects=track_objects(s)[s.previs.track_offset:]
    gpu.state.blend_set('ALPHA')
    try:
        for row,obj in enumerate(objects):
            y=25+ROW*row
            if y+ROW>region.height-15:break
            rect(0,y,region.width,y+ROW-2,(.10,.13,.18,.92))
            nodes=obj.previs.nodes
            for i,n in enumerate(nodes):
                x=v.view_to_region(1+n.time*s.previs.fps,0,clip=False)[0]
                end=v.view_to_region(1+(n.time+n.dwell)*s.previs.fps,0,clip=False)[0]
                if i:
                    prev=nodes[i-1]
                    start=v.view_to_region(1+(prev.time+prev.dwell)*s.previs.fps,0,clip=False)[0]
                    rect(start,y+5,x,y+17,(.18,.43,.68,.95))
                    if x-start>55:text(start+4,y+8,n.easing,(.9,.95,1,1))
                if end>x:rect(x,y+4,end,y+18,(.9,.54,.12,1))
                rect(x-2,y+2,x+2,y+20,(.9,.9,.95,1))
            for keys,color in [(obj.previs.angles,(.65,.45,1,1)),(obj.previs.lenses,(.15,.9,.65,1))]:
                for key in keys:
                    x=v.view_to_region(1+key.time*s.previs.fps,0,clip=False)[0]
                    rect(x-3,y+1,x+3,y+5,color)
            rect(0,y,135,y+21,(.08,.1,.14,.96));text(6,y+7,obj.name[:19])
        x=v.view_to_region(s.frame_current,0,clip=False)[0]
        rect(x-1,0,x+1,region.height,(1,.28,.2,.85))
    finally:gpu.state.blend_set('NONE')

class PREVIS_OT_select_segment(bpy.types.Operator):
    bl_idname='previs.select_segment';bl_label='选中预演运动段'
    @classmethod
    def poll(cls,c):return c.area.type=='DOPESHEET_EDITOR' and c.space_data.mode=='TIMELINE' and c.scene.previs.enabled
    def invoke(self,c,event):
        row=int((event.mouse_region_y-25)//ROW)+c.scene.previs.track_offset
        objects=track_objects(c.scene)
        if not 0<=row<len(objects):return {'CANCELLED'}
        obj=objects[row];activate(c,obj)
        frame=c.region.view2d.region_to_view(event.mouse_region_x,0)[0]
        time=(frame-1)/c.scene.previs.fps
        for i,n in enumerate(obj.previs.nodes):
            if time<=n.time+n.dwell:obj.previs.node_index=i;break
        else:obj.previs.node_index=max(0,len(obj.previs.nodes)-1)
        c.scene.frame_set(max(1,min(c.scene.frame_end,round(frame))))
        for area in c.screen.areas:area.tag_redraw()
        return {'FINISHED'}

def header(self,c):
    if c.scene and c.scene.previs.enabled and c.space_data.mode=='TIMELINE':
        row=self.layout.row(align=True);row.label(text='Shift+单击选段 · 蓝运动 / 橙停留')
        row.prop(c.scene.previs,'track_offset',text='轨道偏移')

def register():
    global _handle
    bpy.utils.register_class(PREVIS_OT_select_segment)
    bpy.types.DOPESHEET_HT_header.append(header)
    if not bpy.app.background:
        _handle=bpy.types.SpaceDopeSheetEditor.draw_handler_add(draw,(),'WINDOW','POST_PIXEL')
        config=bpy.context.window_manager.keyconfigs.addon
        if config:
            km=config.keymaps.new(name='Dopesheet',space_type='DOPESHEET_EDITOR')
            kmi=km.keymap_items.new('previs.select_segment','LEFTMOUSE','PRESS',shift=True)
            _keymaps.append((km,kmi))

def unregister():
    global _handle
    for km,kmi in _keymaps:km.keymap_items.remove(kmi)
    _keymaps.clear()
    if _handle:bpy.types.SpaceDopeSheetEditor.draw_handler_remove(_handle,'WINDOW');_handle=None
    bpy.types.DOPESHEET_HT_header.remove(header)
    bpy.utils.unregister_class(PREVIS_OT_select_segment)
