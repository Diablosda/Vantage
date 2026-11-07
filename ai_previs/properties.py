import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty,
                       FloatVectorProperty, IntProperty, PointerProperty, StringProperty)

EASING = [('LINEAR', '匀速', ''), ('IN', '加速', ''), ('OUT', '减速', ''), ('IN_OUT', '先加速后减速', '')]

def changed(self, context):
    from . import runtime
    runtime.invalidate()
    if context and context.scene and not runtime.busy:
        runtime.evaluate(context.scene)
    if context and context.screen:
        for area in context.screen.areas: area.tag_redraw()

def grid_changed(self,context):
    if context and context.scene:
        settings=context.scene.tool_settings
        settings.use_snap=self.snap;settings.snap_elements={'INCREMENT'}
        settings.use_snap_grid_absolute=True
        if context.screen:
            for area in context.screen.areas:
                if area.type=='VIEW_3D':area.spaces.active.overlay.grid_scale=self.grid
    changed(self,context)

def ground_changed(self,context):
    obj=self.id_data
    if isinstance(obj,bpy.types.Object):obj.lock_location[2]=self.lock_z or self.locked
    changed(self,context)

def ratio_changed(self, context):
    sizes = {'1:1': (720,720), '4:3': (960,720), '3:4': (720,960),
             '16:9': (1280,720), '9:16': (720,1280), '21:9': (1680,720)}
    if self.ratio in sizes: self.width, self.height = sizes[self.ratio]
    settings_changed(self, context)

def settings_changed(self, context):
    if not context or not context.scene: return
    s = context.scene
    s.render.fps = self.fps; s.render.fps_base = 1.
    s.frame_start = 1; s.frame_end = max(1, round(self.duration * self.fps))
    s.render.resolution_x = self.width; s.render.resolution_y = self.height
    changed(self, context)

class PREVIS_PG_Node(bpy.types.PropertyGroup):
    position: FloatVectorProperty(name='位置 XYZ', size=3, subtype='TRANSLATION', update=changed)
    time: FloatProperty(name='到达（秒）', min=0, update=changed)
    dwell: FloatProperty(name='停留（秒）', min=0, update=changed)
    exact: BoolProperty(name='必须精确经过', update=changed)
    radius: FloatProperty(name='圆角范围（米）', default=.5, min=0, update=changed)
    easing: EnumProperty(name='到达此点的速度', items=EASING, update=changed)

class PREVIS_PG_Angle(bpy.types.PropertyGroup):
    time: FloatProperty(name='时间（秒）', min=0, update=changed)
    rotation: FloatVectorProperty(name='角度', size=3, subtype='EULER', update=changed)
    easing: EnumProperty(name='插值', items=EASING, update=changed)

class PREVIS_PG_Lens(bpy.types.PropertyGroup):
    time: FloatProperty(name='时间（秒）', min=0, update=changed)
    value: FloatProperty(name='焦距 mm', default=50, min=1, max=1000, update=changed)
    easing: EnumProperty(name='插值', items=EASING, update=changed)

class PREVIS_PG_Object(bpy.types.PropertyGroup):
    managed: BoolProperty(default=False)
    role: EnumProperty(name='类型', items=[('ACTOR','人物',''),('PROP','物品',''),('CAMERA','摄影机',''),('TARGET','目标点',''),('ENV','静态环境','')])
    orientation: EnumProperty(name='朝向', items=[('FIXED','固定朝向',''),('PATH','沿路径朝向',''),('MANUAL','手动关键角度','')], update=changed)
    lock_z: BoolProperty(name='路径锁定地面 Z', default=False, update=ground_changed)
    nodes: CollectionProperty(type=PREVIS_PG_Node)
    node_index: IntProperty(default=0)
    smooth: BoolProperty(name='平滑拐角', update=changed)
    angles: CollectionProperty(type=PREVIS_PG_Angle)
    angle_index: IntProperty(default=0)
    lenses: CollectionProperty(type=PREVIS_PG_Lens)
    lens_index: IntProperty(default=0)
    base_rotation: FloatVectorProperty(size=3, subtype='EULER')
    view_mode: EnumProperty(items=[('FREE','自由朝向',''),('LOCK','目标锁定','')], default='FREE')
    target: PointerProperty(type=bpy.types.Object)
    follow: PointerProperty(name='跟随人物 Root', type=bpy.types.Object, update=changed)
    offset: FloatVectorProperty(name='本地偏移', size=3, subtype='TRANSLATION', update=changed)
    roll_enabled: BoolProperty(name='启用 Roll', update=changed)
    roll: FloatProperty(name='Roll', subtype='ANGLE', update=changed)
    rolls: CollectionProperty(type=PREVIS_PG_Angle)
    roll_index: IntProperty(default=0)
    hidden: BoolProperty(default=False)
    locked: BoolProperty(default=False)

class PREVIS_PG_Project(bpy.types.PropertyGroup):
    enabled: BoolProperty(default=False)
    fps: IntProperty(name='FPS', default=24, min=1, max=120, update=settings_changed)
    duration: FloatProperty(name='片段时长（秒）', default=5, min=.05, max=3600, update=settings_changed)
    grid: FloatProperty(name='网格步长（米）', default=.5, min=.001, update=grid_changed)
    snap: BoolProperty(name='网格吸附', default=True, update=grid_changed)
    axis_order: EnumProperty(name='转折轴顺序', items=[(s,s,'') for s in ('XYZ','XZY','YXZ','YZX','ZXY','ZYX')])
    show_helpers: BoolProperty(name='编辑辅助线', default=True, update=changed)
    ratio: EnumProperty(name='画幅', items=[(s,s,'') for s in ('1:1','4:3','3:4','16:9','9:16','21:9','CUSTOM')], default='16:9', update=ratio_changed)
    width: IntProperty(name='宽', default=1280, min=16, max=16384, update=settings_changed)
    height: IntProperty(name='高', default=720, min=16, max=16384, update=settings_changed)
    source_path: StringProperty(subtype='FILE_PATH')
    project_path: StringProperty(name='工程副本', subtype='FILE_PATH')
    output_path: StringProperty(name='视频输出', subtype='FILE_PATH')
    error: StringProperty()
    warning: StringProperty()
    loop: BoolProperty(name='循环播放', default=True)
    track_offset: IntProperty(name='轨道偏移',default=0,min=0)

CLASSES = (PREVIS_PG_Node, PREVIS_PG_Angle, PREVIS_PG_Lens, PREVIS_PG_Object, PREVIS_PG_Project)

def register():
    for cls in CLASSES: bpy.utils.register_class(cls)
    bpy.types.Object.previs = PointerProperty(type=PREVIS_PG_Object)
    bpy.types.Scene.previs = PointerProperty(type=PREVIS_PG_Project)

def unregister():
    del bpy.types.Scene.previs; del bpy.types.Object.previs
    for cls in reversed(CLASSES): bpy.utils.unregister_class(cls)
