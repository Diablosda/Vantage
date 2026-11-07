import math
import os
from contextlib import contextmanager
import bpy
from bpy.props import StringProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, BoolProperty
from bpy_extras.io_utils import ImportHelper, ExportHelper
from mathutils import Vector, Matrix
from . import runtime
from .geometry import Node, orthogonalize

@contextmanager
def edit_batch():
    old = runtime.busy; runtime.busy = True
    try: yield
    finally: runtime.busy = old; runtime.invalidate()

def active_control(context):
    obj = context.object
    while obj and not obj.previs.managed: obj = obj.parent
    return obj

def activate(context,obj):
    for o in context.selected_objects: o.select_set(False)
    obj.hide_set(False); obj.hide_select = False
    obj.select_set(True); context.view_layer.objects.active = obj

def mark(obj,role='PROP'):
    obj.previs.managed = True; obj.previs.role = role
    obj.previs.lock_z = role == 'ACTOR'
    obj.previs.base_rotation = obj.rotation_euler
    obj.rotation_mode = 'XYZ'
    obj.show_in_front = obj.type == 'EMPTY'
    if obj.type == 'EMPTY': obj.empty_display_type = 'PLAIN_AXES'; obj.empty_display_size = .5

def assign_nodes(obj,nodes):
    with edit_batch():
        obj.previs.nodes.clear()
        for node in nodes:
            n = obj.previs.nodes.add()
            for key in ('position','time','dwell','exact','radius','easing'): setattr(n,key,getattr(node,key))
        obj.previs.node_index = min(obj.previs.node_index,max(0,len(nodes)-1))

def snap_position(scene,obj,position):
    p = list(position)
    if scene.previs.snap: p = [round(v/scene.previs.grid)*scene.previs.grid for v in p]
    if obj.previs.lock_z: p[2] = obj.previs.nodes[0].position[2] if obj.previs.nodes else obj.location.z
    return tuple(p)

def add_node(context,obj,position,time=None):
    nodes = runtime.nodes_for(obj)
    if not nodes: nodes.append(Node(tuple(obj.location)))
    pos = snap_position(context.scene,obj,position)
    end_time = time if time is not None else nodes[-1].time + nodes[-1].dwell + 1.
    if end_time <= nodes[-1].time + nodes[-1].dwell: raise ValueError('到达时间必须晚于上一点离开时间')
    nodes.append(Node(pos,end_time))
    assign_nodes(obj,orthogonalize(nodes,context.scene.previs.axis_order))
    obj.previs.node_index = len(obj.previs.nodes)-1
    runtime.evaluate(context.scene)

def new_project(context):
    scene = bpy.data.scenes.new('AI Previs')
    context.window.scene = scene
    scene.world = bpy.data.worlds.new('Previs World')
    scene.unit_settings.system = 'METRIC'; scene.unit_settings.scale_length = 1.
    scene.previs.enabled = True
    scene.frame_start = 1; scene.frame_end = 120; scene.render.fps = 24
    scene.render.resolution_x = 1280; scene.render.resolution_y = 720
    scene.render.engine = 'BLENDER_WORKBENCH'
    return scene

class SafeOperator:
    def execute(self,context):
        try:
            result = self.run(context)
            runtime.invalidate()
            if context.scene.previs.enabled: runtime.evaluate(context.scene)
            return result or {'FINISHED'}
        except (ValueError, OSError, RuntimeError) as exc:
            self.report({'ERROR'},str(exc)); return {'CANCELLED'}

class PREVIS_OT_new(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.new'; bl_label = '新建白模工程'; bl_options = {'REGISTER','UNDO'}
    def run(self,context):
        new_project(context)
        bpy.ops.previs.workspace()

class PREVIS_OT_import(SafeOperator,bpy.types.Operator,ImportHelper):
    bl_idname = 'previs.import_scene'; bl_label = '导入静态 .blend 副本'
    filename_ext = '.blend'
    filter_glob: StringProperty(default='*.blend', options={'HIDDEN'})
    snapshot: BoolProperty(name='明确按指定帧静态化（冻结动画与约束）', default=False)
    frame: IntProperty(name='静态化帧号', default=1)
    scene_name: StringProperty(name='源场景名称（留空取第一个）')
    def run(self,context):
        if not os.path.isfile(self.filepath): raise ValueError('源文件不存在')
        if runtime.same_path(self.filepath,bpy.data.filepath):
            raise ValueError('请从新启动的空白工作台导入此文件，避免将当前文件同时作为源文件与工程')
        before = set(bpy.data.objects)
        source = None
        try:
            with bpy.data.libraries.load(self.filepath,link=False) as (src,dst):
                chosen = self.scene_name or (src.scenes[0] if src.scenes else '')
                if chosen not in src.scenes: raise ValueError('找不到指定源场景')
                dst.scenes = [chosen]
            source = dst.scenes[0]
            if source.previs.enabled: raise ValueError('这是预演工程，请使用“打开工程”继续编辑')
            animated = runtime.animation_sources(source)
            if animated and not self.snapshot:
                raise ValueError('检测到动画/约束：'+'、'.join(animated[:5])+'。请勾选按指定帧静态化，或先准备静态副本。原文件未修改。')
            source.frame_set(self.frame if self.snapshot else source.frame_current)
            snapshots = []
            with context.temp_override(scene=source,view_layer=source.view_layers[0]):
                deps = context.evaluated_depsgraph_get()
                for obj in source.objects:
                    if obj.hide_render or not obj.visible_get(view_layer=source.view_layers[0]): continue
                    if obj.instance_type != 'NONE': raise ValueError('V1 不导入集合实例，请先在源文件副本中将实例实体化')
                    evaluated = obj.evaluated_get(deps)
                    if obj.type in {'MESH','CURVE','SURFACE','FONT','META'}:
                        data = bpy.data.meshes.new_from_object(evaluated,depsgraph=deps)
                        copy = bpy.data.objects.new(obj.name,data)
                    elif obj.type == 'CAMERA':
                        copy = bpy.data.objects.new(obj.name,evaluated.data.copy()); copy.data.animation_data_clear()
                    else: continue
                    copy.matrix_world = evaluated.matrix_world.copy()
                    snapshots.append(copy)
            scene = new_project(context)
            for obj in snapshots:
                scene.collection.objects.link(obj)
                if obj.type == 'CAMERA':
                    mark(obj,'CAMERA'); obj.data.dof.use_dof = False
                    if not scene.camera: scene.camera = obj
            scene.previs.source_path = os.path.abspath(self.filepath)
            self.report({'INFO'},f'已导入 {len(snapshots)} 个静态对象；源文件未修改')
        finally:
            if source: bpy.data.scenes.remove(source)
            for obj in list(bpy.data.objects):
                if obj not in before and obj.users == 0: bpy.data.objects.remove(obj)
        bpy.ops.previs.workspace()

class PREVIS_OT_open(SafeOperator,bpy.types.Operator,ImportHelper):
    bl_idname = 'previs.open_project'; bl_label = '打开预演工程'
    filename_ext = '.blend'
    filter_glob: StringProperty(default='*.blend', options={'HIDDEN'})
    def run(self,context):
        bpy.ops.wm.open_mainfile(filepath=self.filepath,load_ui=True)

class PREVIS_OT_save(SafeOperator,bpy.types.Operator,ExportHelper):
    bl_idname = 'previs.save_project'; bl_label = '保存工程副本'
    filename_ext = '.blend'
    filter_glob: StringProperty(default='*.blend', options={'HIDDEN'})
    def invoke(self,context,event):
        self.filepath = context.scene.previs.project_path or 'previs_project.blend'
        return ExportHelper.invoke(self,context,event)
    def run(self,context): runtime.save_project(context.scene,self.filepath)

class PREVIS_OT_primitive(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.primitive'; bl_label = '添加基本体'; bl_options = {'REGISTER','UNDO'}
    shape: EnumProperty(items=[('CUBE','立方体',''),('BOX','长方体',''),('SPHERE','球体',''),('CYLINDER','圆柱体','')])
    def run(self,context):
        if not context.scene.previs.enabled: context.scene.previs.enabled = True
        if self.shape == 'SPHERE': bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=12,radius=.5,location=context.scene.cursor.location)
        elif self.shape == 'CYLINDER': bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.4,depth=1.5,location=context.scene.cursor.location)
        else:
            bpy.ops.mesh.primitive_cube_add(size=1,location=context.scene.cursor.location)
            if self.shape == 'BOX': context.object.scale = (1.5,.6,.8)
        context.object.name = {'CUBE':'立方体','BOX':'长方体','SPHERE':'球体','CYLINDER':'圆柱体'}[self.shape]
        # Geometry remains unmarked until grouped, so several primitives can share one Root.

class PREVIS_OT_root(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.root'; bl_label = '选中部件 → Root'; bl_options = {'REGISTER','UNDO'}
    role: EnumProperty(items=[('ACTOR','人物',''),('PROP','物品',''),('ENV','静态环境','')],default='PROP')
    def run(self,context):
        selected = list(context.selected_objects)
        if not selected: raise ValueError('请先选择一个或多个部件')
        if any(o.previs.managed or any(c.previs.managed for c in o.children_recursive) for o in selected):
            raise ValueError('选择包含已有 Root，请选择尚未分组的部件，避免嵌套动画控制器')
        top = [o for o in selected if o.parent not in selected]
        center = sum((o.matrix_world.translation for o in top),Vector())/len(top)
        root = bpy.data.objects.new('人物 Root' if self.role == 'ACTOR' else '物品 Root',None)
        context.scene.collection.objects.link(root); root.location = center
        context.view_layer.update()
        for obj in top:
            world = obj.matrix_world.copy(); obj.parent = root; obj.matrix_world = world
        mark(root,self.role); activate(context,root)

class PREVIS_OT_object_action(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.object_action'; bl_label = '对象操作'; bl_options = {'REGISTER','UNDO'}
    object_name: StringProperty()
    action: EnumProperty(items=[(s,s,'') for s in ('SELECT','HIDE','LOCK','DELETE','RESET')])
    def invoke(self,context,event):
        if self.action in {'DELETE','RESET'}: return context.window_manager.invoke_confirm(self,event)
        return self.execute(context)
    def run(self,context):
        obj = context.scene.objects.get(self.object_name) if self.object_name else active_control(context)
        if not obj: raise ValueError('没有可操作对象')
        if self.action == 'SELECT': activate(context,obj)
        elif self.action == 'HIDE':
            obj.previs.hidden = not obj.previs.hidden
            for o in [obj,*obj.children_recursive]: o.hide_set(obj.previs.hidden); o.hide_render = obj.previs.hidden
        elif self.action == 'LOCK':
            p = obj.previs; p.locked = not p.locked
            for o in [obj,*obj.children_recursive]:
                o.hide_select = p.locked; o.lock_location = (p.locked,)*3; o.lock_rotation = (p.locked,)*3
            if not p.locked:obj.lock_location[2]=p.lock_z
        elif self.action == 'DELETE':
            for o in reversed([obj,*obj.children_recursive]): bpy.data.objects.remove(o,do_unlink=True)
        elif self.action == 'RESET':
            if obj.previs.nodes: obj.location = obj.previs.nodes[0].position
            obj.previs.nodes.clear()

class PREVIS_OT_proxy(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.proxy'; bl_label = '生成包围盒代理'; bl_options = {'REGISTER','UNDO'}
    shape: EnumProperty(items=[('BOX','长方体',''),('CYLINDER','圆柱体','')])
    def run(self,context):
        selection = list(context.selected_objects)
        objects = set(selection)
        for o in selection: objects.update(o.children_recursive)
        points = [o.matrix_world @ Vector(c) for o in objects if o.type == 'MESH' for c in o.bound_box]
        if not points: raise ValueError('请选择含网格的对象或组')
        lo = Vector(tuple(min(p[i] for p in points) for i in range(3)))
        hi = Vector(tuple(max(p[i] for p in points) for i in range(3)))
        center, size = (lo+hi)*.5, hi-lo
        if self.shape == 'BOX': bpy.ops.mesh.primitive_cube_add(size=1,location=center)
        else: bpy.ops.mesh.primitive_cylinder_add(vertices=24,radius=.5,depth=1,location=center)
        proxy = context.object; proxy.name = '白模代理'; proxy.dimensions = size
        for o in objects: o.hide_set(True); o.hide_render = True
        bpy.ops.previs.root(role='PROP')

class PREVIS_OT_calibrate(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.calibrate'; bl_label = '校准模型正面'; bl_options = {'REGISTER','UNDO'}
    angle: FloatProperty(name='模型相对逻辑 +Y 的修正',subtype='ANGLE',default=math.pi/2)
    def invoke(self,context,event): return context.window_manager.invoke_props_dialog(self)
    def run(self,context):
        obj = active_control(context)
        if not obj or obj.type != 'EMPTY': raise ValueError('请先创建人物/物品 Root')
        correction = next((c for c in obj.children if c.get('previs_calibration')),None)
        if not correction:
            children = list(obj.children)
            correction = bpy.data.objects.new('正面校准层',None); context.scene.collection.objects.link(correction)
            correction.parent = obj; correction['previs_calibration'] = True
            context.view_layer.update()
            for child in children:
                world = child.matrix_world.copy(); child.parent = correction; child.matrix_world = world
        correction.rotation_euler.z += self.angle

class PREVIS_OT_node_add(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.node_add'; bl_label = '添加路径节点'; bl_options = {'REGISTER','UNDO'}
    position: FloatVectorProperty(name='新节点 XYZ',size=3,subtype='TRANSLATION')
    time: FloatProperty(name='到达（秒）',min=0,default=1)
    def invoke(self,context,event):
        obj = active_control(context)
        if not obj: return {'CANCELLED'}
        self.position = context.scene.cursor.location
        self.time = obj.previs.nodes[-1].time+obj.previs.nodes[-1].dwell+1 if obj.previs.nodes else 1
        return context.window_manager.invoke_props_dialog(self)
    def run(self,context):
        obj = active_control(context)
        if not obj: raise ValueError('请先选择 Root 或摄影机')
        if obj.previs.follow: raise ValueError('跟随目标不能同时编辑独立路径')
        add_node(context,obj,self.position,self.time)

class PREVIS_OT_node_edit(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.node_edit'; bl_label = '编辑节点'; bl_options = {'REGISTER','UNDO'}
    action: EnumProperty(items=[(s,s,'') for s in ('DELETE','DUPLICATE','INSERT','UP','DOWN','ORTHO','CLEAN','CAPTURE')])
    def run(self,context):
        obj = active_control(context)
        if not obj: raise ValueError('请选择 Root')
        p = obj.previs; nodes = runtime.nodes_for(obj); i = min(p.node_index,len(nodes)-1)
        if not nodes: raise ValueError('没有路径节点')
        if self.action == 'DELETE': nodes.pop(i)
        elif self.action in {'DUPLICATE','INSERT'}:
            n = nodes[i]
            if i+1 < len(nodes):
                end = nodes[i+1]
                t = (n.time+n.dwell+end.time)*.5
                pos = n.position if self.action == 'DUPLICATE' else tuple((a+b)*.5 for a,b in zip(n.position,end.position))
            else: t = n.time+n.dwell+1; pos = n.position
            nodes.insert(i+1,Node(pos,t))
        elif self.action in {'UP','DOWN'}:
            j = i+(-1 if self.action == 'UP' else 1)
            if not 0 <= j < len(nodes): return
            # Swap spatial positions, keep chronological slots intact.
            a,b = nodes[i],nodes[j]
            nodes[i] = Node(b.position,a.time,a.dwell,a.exact,a.radius,a.easing)
            nodes[j] = Node(a.position,b.time,b.dwell,b.exact,b.radius,b.easing)
            p.node_index = j
        elif self.action == 'CAPTURE':
            n = nodes[i]; nodes[i] = Node(snap_position(context.scene,obj,obj.location),n.time,n.dwell,n.exact,n.radius,n.easing)
        elif self.action == 'CLEAN':
            # Never silently discard intentional pauses or exact anchors.
            nodes = [n for k,n in enumerate(nodes) if k == 0 or n.position != nodes[k-1].position or n.dwell or n.exact]
        nodes = orthogonalize(nodes,context.scene.previs.axis_order)
        assign_nodes(obj,nodes)

class PREVIS_OT_node_position(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.node_position'; bl_label = '修改节点位置'; bl_options = {'REGISTER','UNDO'}
    position: FloatVectorProperty(name='位置 XYZ',size=3,subtype='TRANSLATION')
    def invoke(self,context,event):
        obj=active_control(context)
        if not obj or not obj.previs.nodes:return {'CANCELLED'}
        self.position=obj.previs.nodes[obj.previs.node_index].position
        return context.window_manager.invoke_props_dialog(self)
    def run(self,context):
        obj=active_control(context);nodes=runtime.nodes_for(obj);i=obj.previs.node_index;n=nodes[i]
        nodes[i]=Node(snap_position(context.scene,obj,self.position),n.time,n.dwell,n.exact,n.radius,n.easing)
        assign_nodes(obj,orthogonalize(nodes,context.scene.previs.axis_order))

class PREVIS_OT_key(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.key'; bl_label = '记录关键帧'; bl_options = {'REGISTER','UNDO'}
    kind: EnumProperty(items=[('ANGLE','角度',''),('LENS','焦距',''),('ROLL','Roll','')])
    remove: BoolProperty(default=False)
    def run(self,context):
        obj = active_control(context)
        if not obj: raise ValueError('请选择控制器')
        p = obj.previs
        keys = p.angles if self.kind == 'ANGLE' else p.lenses if self.kind == 'LENS' else p.rolls
        index = p.angle_index if self.kind == 'ANGLE' else p.lens_index if self.kind == 'LENS' else p.roll_index
        if self.remove:
            if keys: keys.remove(min(index,len(keys)-1))
            return
        time = (context.scene.frame_current-1)/context.scene.previs.fps
        rot = tuple(obj.rotation_euler); lens = obj.data.lens if obj.type == 'CAMERA' else 50
        with edit_batch():
            key = next((k for k in keys if abs(k.time-time)<1e-5),None)
            if key is None: key = keys.add()
            key.time = time
            if self.kind == 'LENS': key.value = lens
            else: key.rotation = (0,0,p.roll) if self.kind == 'ROLL' else rot
            if self.kind == 'ANGLE': p.orientation = 'MANUAL'; p.angle_index = len(keys)-1
            elif self.kind == 'LENS': p.lens_index = len(keys)-1
            else:p.roll_index=len(keys)-1

class PREVIS_OT_camera(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.camera'; bl_label = '添加摄影机 C / 目标 T'; bl_options = {'REGISTER','UNDO'}
    def run(self,context):
        bpy.ops.object.camera_add(location=(5,-7,4))
        cam = context.object; cam.name = '摄影机 C'; mark(cam,'CAMERA')
        cam.data.lens = 50; cam.data.sensor_width = 36; cam.data.sensor_fit = 'HORIZONTAL'
        cam.rotation_euler = runtime.camera_quaternion(cam.location,(0,0,1)).to_euler()
        cam.previs.base_rotation = cam.rotation_euler
        target = bpy.data.objects.new('视线目标 T',None); context.scene.collection.objects.link(target)
        target.location = (0,0,1); target.empty_display_type = 'SPHERE'; target.empty_display_size = .2
        mark(target,'TARGET'); target.empty_display_type = 'SPHERE'; target.empty_display_size = .2
        cam.previs.target = target
        context.scene.camera = cam

class PREVIS_OT_camera_mode(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.camera_mode'; bl_label = '切换自由 / 目标锁定'; bl_options = {'REGISTER','UNDO'}
    def run(self,context):
        cam = active_control(context)
        if not cam or cam.type != 'CAMERA': raise ValueError('请选择摄影机 C')
        p = cam.previs
        if p.view_mode == 'LOCK':
            rot = cam.rotation_euler.copy(); p.view_mode = 'FREE'
            p.orientation = 'FIXED'; p.base_rotation = rot; cam.rotation_euler = rot
        else:
            if not p.target:
                target = bpy.data.objects.new('视线目标 T',None); context.scene.collection.objects.link(target)
                mark(target,'TARGET'); p.target = target
            target = p.target
            distance = max((target.location-cam.location).length,1.)
            desired = cam.location + cam.rotation_euler.to_quaternion() @ Vector((0,0,-distance))
            delta = desired-target.location
            if target.previs.follow:
                with edit_batch():target.previs.offset = target.previs.follow.matrix_world.inverted() @ desired
            elif target.previs.nodes:
                nodes=runtime.nodes_for(target)
                assign_nodes(target,[Node(tuple(Vector(n.position)+delta),n.time,n.dwell,n.exact,n.radius,n.easing) for n in nodes])
            target.location = desired
            base = runtime.camera_quaternion(cam.location,target.location)
            relative = base.inverted() @ cam.rotation_euler.to_quaternion()
            with edit_batch():
                p.roll = relative.to_euler().z; p.roll_enabled = abs(p.roll)>1e-5
                p.view_mode = 'LOCK'

class PREVIS_OT_orbit(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.orbit'; bl_label = '围绕 T 旋转 C'; bl_options = {'REGISTER','UNDO'}
    angle: FloatProperty(name='水平环绕角度',subtype='ANGLE',default=math.pi/12)
    elevation: FloatProperty(name='升降环绕角度',subtype='ANGLE')
    def invoke(self,context,event): return context.window_manager.invoke_props_dialog(self)
    def run(self,context):
        cam = active_control(context)
        if not cam or cam.type != 'CAMERA' or not cam.previs.target: raise ValueError('请选择有 T 的摄影机')
        if cam.previs.nodes: raise ValueError('已有 C 路径，请编辑路径节点或重置路径后环绕摆位')
        target = cam.previs.target.matrix_world.translation
        offset = cam.location-target
        if offset.length < 1e-5: raise ValueError('C 与 T 重合')
        offset = Matrix.Rotation(self.angle,4,'Z') @ offset
        right = offset.cross(Vector((0,0,1))).normalized()
        if right.length < .01: right = Vector((1,0,0))
        offset = Matrix.Rotation(self.elevation,4,right) @ offset
        cam.location = target+offset
        cam.rotation_euler = runtime.camera_quaternion(cam.location,target,cam.previs.roll if cam.previs.roll_enabled else 0).to_euler()

class PREVIS_OT_transport(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.transport'; bl_label = '播放控制'
    action: EnumProperty(items=[('START','回到起点',''),('PLAY','播放 / 暂停','')])
    def run(self,context):
        if self.action == 'START': context.scene.frame_set(1)
        else: bpy.ops.screen.animation_play()

class PREVIS_OT_export(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.export'; bl_label = '导出 MP4（先保存工程）'
    def invoke(self,context,event):
        path = bpy.path.abspath(context.scene.previs.output_path)
        if path and os.path.exists(path): return context.window_manager.invoke_confirm(self,event,message='覆盖已有 MP4？')
        return self.execute(context)
    def run(self,context):
        scene = context.scene
        video = runtime.prepare_export(scene)
        animated = []
        try:
            animated = runtime.bake(scene)
            # Blocking render in background tests; interactive render gets a cancellable job.
            if bpy.app.background:
                bpy.ops.render.render(animation=True)
            else:
                _render_cleanup['animated'] = animated
                bpy.ops.render.render('INVOKE_DEFAULT',animation=True)
                animated = []
        finally:
            runtime.clear_bake(animated)
        self.report({'INFO'},'已保存工程，开始输出：'+video)

_render_cleanup = {}
def render_done(scene,*args):
    runtime.clear_bake(_render_cleanup.pop('animated',[]))
    runtime.invalidate()

CLASSES = (PREVIS_OT_new,PREVIS_OT_import,PREVIS_OT_open,PREVIS_OT_save,PREVIS_OT_primitive,
           PREVIS_OT_root,PREVIS_OT_object_action,PREVIS_OT_proxy,PREVIS_OT_calibrate,
           PREVIS_OT_node_add,PREVIS_OT_node_edit,PREVIS_OT_node_position,PREVIS_OT_key,PREVIS_OT_camera,
           PREVIS_OT_camera_mode,PREVIS_OT_orbit,PREVIS_OT_transport,PREVIS_OT_export)

def register():
    for cls in CLASSES: bpy.utils.register_class(cls)
    bpy.app.handlers.render_complete.append(render_done); bpy.app.handlers.render_cancel.append(render_done)

def unregister():
    render_done(None)
    for handlers in (bpy.app.handlers.render_complete,bpy.app.handlers.render_cancel):
        if render_done in handlers: handlers.remove(render_done)
    for cls in reversed(CLASSES): bpy.utils.unregister_class(cls)
