import math
import bpy
import blf
import gpu
from bpy.props import EnumProperty, IntProperty, FloatProperty
from bpy_extras import view3d_utils
from gpu_extras.batch import batch_for_shader
from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_plane
from . import runtime
from .geometry import Node, orthogonalize
from .operators import SafeOperator, active_control, assign_nodes, add_node, snap_position, edit_batch

_draw_handles = []

class PREVIS_OT_workspace(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.workspace'; bl_label = '进入简化工作区'
    def run(self,context):
        if bpy.app.background: return
        context.scene.previs.enabled = True
        if context.workspace.name != 'AI Previs Studio':
            existing = bpy.data.workspaces.get('AI Previs Studio')
            if existing: context.window.workspace = existing
            else:
                bpy.ops.workspace.duplicate()
                # Workspace duplication switches the window on the next UI cycle.
                def finish_workspace():
                    bpy.context.window.workspace.name = 'AI Previs Studio'
                    bpy.ops.previs.workspace()
                    return None
                bpy.app.timers.register(finish_workspace,first_interval=.15)
                return
        screen = context.window.screen
        views = sorted([a for a in screen.areas if a.type == 'VIEW_3D'],key=lambda a:a.x)
        if not views:
            largest = max(screen.areas,key=lambda a:a.width*a.height); largest.type = 'VIEW_3D'; views=[largest]
        if len(views) == 1:
            with context.temp_override(area=views[0]):
                bpy.ops.screen.area_split(direction='VERTICAL',factor=.62)
            def finish_split():
                bpy.ops.previs.workspace()
                return None
            bpy.app.timers.register(finish_split,first_interval=.15)
            return
        views = sorted([a for a in screen.areas if a.type == 'VIEW_3D'],key=lambda a:a.x)
        # Keep Blender's native object inspector and one Outliner alongside the product panels.
        for area in screen.areas:
            if area.type == 'PROPERTIES': area.spaces.active.context = 'OBJECT'
            if area.type == 'DOPESHEET_EDITOR' and area.spaces.active.mode == 'TIMELINE':
                area.spaces.active.show_seconds=True
                if area.height<150:
                    with context.temp_override(window=context.window,screen=screen,area=None,region=None):
                        if bpy.ops.screen.area_move.poll():
                            bpy.ops.screen.area_move(x=area.x+area.width//2,y=area.y+area.height,delta=140)
        for i,area in enumerate(views):
            space = area.spaces.active
            space.show_region_ui = i == 0
            space.show_region_toolbar = i == 0
            space.show_gizmo = i == 0
            space.shading.type = 'SOLID'; space.shading.color_type = 'SINGLE'
            space.shading.single_color = (.65,.65,.65)
            space.overlay.show_floor = i == 0
            space.overlay.show_extras = i == 0
            space.overlay.show_overlays = i == 0
            space.overlay.grid_scale = context.scene.previs.grid
            space.region_3d.view_distance = 12
            if i:
                space.region_3d.view_perspective = 'CAMERA'
                space.region_3d.view_camera_zoom = 22
            else:
                region = next((r for r in area.regions if r.type == 'WINDOW'),None)
                if region:
                    with context.temp_override(area=area,region=region):
                        bpy.ops.view3d.view_axis(type='TOP')
                        bpy.ops.wm.tool_set_by_id(name='builtin.move')
        # Open the product tab without depending on a particular screen geometry.
        def focus_tab():
            for area in bpy.context.screen.areas if bpy.context.screen else []:
                if area.type == 'VIEW_3D' and area.spaces.active.show_region_ui:
                    region = next((r for r in area.regions if r.type == 'UI'),None)
                    if region:
                        try: region.active_panel_category = '预演'
                        except (AttributeError,TypeError): pass
            return None
        bpy.app.timers.register(focus_tab,first_interval=.3)

class PREVIS_OT_view(SafeOperator,bpy.types.Operator):
    bl_idname = 'previs.view'; bl_label = '切换工作视图'
    view: EnumProperty(items=[('TOP','俯视',''),('FRONT','前视',''),('RIGHT','侧视',''),('CAMERA','摄影机',''),('FREE','自由',''),('FULL','全屏预览','')])
    def run(self,context):
        area = context.area
        if self.view == 'FULL':
            area = next((a for a in context.screen.areas if a.type=='VIEW_3D' and a.spaces.active.region_3d.view_perspective=='CAMERA'),area)
            with context.temp_override(area=area): bpy.ops.screen.screen_full_area(use_hide_panels=True)
            return
        region = next(r for r in area.regions if r.type=='WINDOW')
        with context.temp_override(area=area,region=region):
            if self.view == 'CAMERA': bpy.ops.view3d.view_camera()
            elif self.view == 'FREE': bpy.ops.view3d.view_orbit(type='ORBITRIGHT')
            else: bpy.ops.view3d.view_axis(type=self.view)

class PREVIS_OT_grid(SafeOperator,bpy.types.Operator):
    bl_idname='previs.grid'; bl_label='设置网格'; bl_options={'REGISTER','UNDO'}
    value: FloatProperty(default=.5)
    def run(self,context): context.scene.previs.grid=self.value

class PREVIS_OT_lens(SafeOperator,bpy.types.Operator):
    bl_idname='previs.lens'; bl_label='焦距预设'; bl_options={'REGISTER','UNDO'}
    value: FloatProperty(default=50)
    def run(self,context):
        obj=active_control(context)
        if obj and obj.type=='CAMERA': obj.data.lens=self.value

class PREVIS_OT_pick_nodes(bpy.types.Operator):
    bl_idname='previs.pick_nodes'; bl_label='在视图中点击布点'; bl_options={'REGISTER','UNDO'}
    def invoke(self,context,event):
        self.obj=active_control(context)
        if not self.obj or self.obj.previs.follow: return {'CANCELLED'}
        if context.space_data.region_3d.view_perspective != 'ORTHO':
            self.report({'ERROR'},'请先切换俯视、前视或侧视'); return {'CANCELLED'}
        self.original=runtime.nodes_for(self.obj)
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set('左键添加节点（每段默认 1 秒）；Enter 完成；Esc 撤销本次布点；中键/滚轮导航')
        return {'RUNNING_MODAL'}
    def modal(self,context,event):
        if event.type in {'RET','NUMPAD_ENTER'}:
            context.area.header_text_set(None); return {'FINISHED'}
        if event.type in {'ESC','RIGHTMOUSE'}:
            assign_nodes(self.obj,self.original); context.area.header_text_set(None); return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            region=next(r for r in context.area.regions if r.type=='WINDOW')
            coord=(event.mouse_x-region.x,event.mouse_y-region.y)
            if not (0<=coord[0]<region.width and 0<=coord[1]<region.height): return {'RUNNING_MODAL'}
            rv=context.space_data.region_3d
            origin=view3d_utils.region_2d_to_origin_3d(region,rv,coord)
            ray=view3d_utils.region_2d_to_vector_3d(region,rv,coord)
            axis=max(range(3),key=lambda i:abs(ray[i])); normal=Vector((0,0,0)); normal[axis]=1
            base=Vector(self.obj.previs.nodes[-1].position) if self.obj.previs.nodes else self.obj.location
            hit=intersect_line_plane(origin,origin+ray,base,normal)
            if hit is not None: add_node(context,self.obj,hit)
            context.area.tag_redraw(); return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'} if event.type in {'MIDDLEMOUSE','WHEELUPMOUSE','WHEELDOWNMOUSE'} else {'RUNNING_MODAL'}

class PREVIS_OT_drag_node(bpy.types.Operator):
    bl_idname='previs.drag_node'; bl_label='轴向拖动路径节点'; bl_options={'REGISTER','UNDO','BLOCKING'}
    axis: IntProperty(default=0,min=0,max=2)
    def invoke(self,context,event):
        self.obj=active_control(context)
        if not self.obj or not self.obj.previs.nodes:return {'CANCELLED'}
        self.nodes=runtime.nodes_for(self.obj); self.index=self.obj.previs.node_index
        self.start=Vector(self.nodes[self.index].position)
        self.mouse=Vector((event.mouse_region_x,event.mouse_region_y))
        end=self.start.copy(); end[self.axis]+=1
        a=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,self.start)
        b=view3d_utils.location_3d_to_region_2d(context.region,context.region_data,end)
        if a is None or b is None or (b-a).length < 2:
            self.report({'WARNING'},'此轴垂直于屏幕，请切换正交视图');return {'CANCELLED'}
        self.screen_axis=b-a
        context.window_manager.modal_handler_add(self);return {'RUNNING_MODAL'}
    def modal(self,context,event):
        if event.type in {'ESC','RIGHTMOUSE'}:
            assign_nodes(self.obj,self.nodes);return {'CANCELLED'}
        if event.type=='MOUSEMOVE':
            delta=Vector((event.mouse_region_x,event.mouse_region_y))-self.mouse
            pos=self.start.copy();pos[self.axis]+=delta.dot(self.screen_axis)/self.screen_axis.length_squared
            with edit_batch():self.obj.previs.nodes[self.index].position=snap_position(context.scene,self.obj,pos)
            context.area.tag_redraw();return {'RUNNING_MODAL'}
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':
            assign_nodes(self.obj,orthogonalize(runtime.nodes_for(self.obj),context.scene.previs.axis_order))
            runtime.evaluate(context.scene);return {'FINISHED'}
        return {'RUNNING_MODAL'}

class PREVIS_OT_orbit_drag(bpy.types.Operator):
    bl_idname='previs.orbit_drag'; bl_label='拖动环绕摄影机'; bl_options={'REGISTER','UNDO','BLOCKING'}
    def invoke(self,context,event):
        self.cam=active_control(context)
        if not self.cam or not self.cam.previs.target or self.cam.previs.nodes:return {'CANCELLED'}
        self.start=self.cam.location.copy();self.rot=self.cam.rotation_euler.copy();self.x=event.mouse_x
        context.window_manager.modal_handler_add(self);return {'RUNNING_MODAL'}
    def modal(self,context,event):
        if event.type in {'ESC','RIGHTMOUSE'}:
            self.cam.location=self.start;self.cam.rotation_euler=self.rot;return {'CANCELLED'}
        if event.type=='MOUSEMOVE':
            target=self.cam.previs.target.matrix_world.translation
            self.cam.location=target+Matrix.Rotation((event.mouse_x-self.x)*.01,4,'Z')@(self.start-target)
            self.cam.rotation_euler=runtime.camera_quaternion(self.cam.location,target).to_euler()
            context.area.tag_redraw()
        if event.type=='LEFTMOUSE' and event.value=='RELEASE':return {'FINISHED'}
        return {'RUNNING_MODAL'}

class PREVIS_GGT_controls(bpy.types.GizmoGroup):
    bl_idname='PREVIS_GGT_controls';bl_label='预演节点与摄影机控制'
    bl_space_type='VIEW_3D';bl_region_type='WINDOW';bl_options={'3D','PERSISTENT'}
    @classmethod
    def poll(cls,context):
        obj=active_control(context)
        return context.scene.previs.enabled and context.scene.previs.show_helpers and obj is not None and context.space_data.region_3d.view_perspective!='CAMERA'
    def setup(self,context):
        self.arrows=[]
        for i,color in enumerate(((.9,.15,.12),(.2,.8,.25),(.2,.45,1.))):
            g=self.gizmos.new('GIZMO_GT_arrow_3d');g.color=color;g.alpha=.8;g.color_highlight=(1,1,1);g.alpha_highlight=1
            g.scale_basis=.8;g.target_set_operator('previs.drag_node').axis=i;self.arrows.append(g)
        self.orbit=self.gizmos.new('GIZMO_GT_dial_3d');self.orbit.color=(1,.65,.1);self.orbit.alpha=.7
        self.orbit.scale_basis=1.5;self.orbit.target_set_operator('previs.orbit_drag')
        self.lens=self.gizmos.new('GIZMO_GT_arrow_3d');self.lens.color=(.1,.8,1);self.lens.alpha=.8;self.lens.scale_basis=.8
    def refresh(self,context):
        obj=active_control(context)
        if not obj:return
        p=obj.previs
        for i,g in enumerate(self.arrows):
            g.hide=not bool(p.nodes) or (i==2 and p.lock_z)
            if p.nodes:
                direction=Vector(tuple(1 if j==i else 0 for j in range(3)))
                g.matrix_basis=direction.to_track_quat('Z','Y').to_matrix().to_4x4()
                g.matrix_basis.translation=p.nodes[min(p.node_index,len(p.nodes)-1)].position
        camera=obj.type=='CAMERA'
        self.orbit.hide=not(camera and p.target and not p.nodes)
        if not self.orbit.hide:self.orbit.matrix_basis=Matrix.Translation(p.target.matrix_world.translation)
        self.lens.hide=not camera
        if camera:
            self.lens.matrix_basis=obj.matrix_world.copy();self.lens.matrix_basis.translation+=Vector((0,0,.5))
            self.lens.target_set_handler('offset',get=lambda:obj.data.lens/100,
                                         set=lambda value:setattr(obj.data,'lens',min(1000,max(1,value*100))))

def line(points,color,width=1,strip=True):
    if len(points)<2:return
    shader=gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.line_width_set(width);shader.bind();shader.uniform_float('color',color)
    batch_for_shader(shader,'LINE_STRIP' if strip else 'LINES',{'pos':points}).draw(shader)

def draw_world():
    context=bpy.context
    if not context.scene or not context.scene.previs.enabled:return
    if context.space_data.region_3d.view_perspective=='CAMERA':return
    selected=active_control(context)
    tool=context.workspace.tools.from_space_view3d_mode('OBJECT',create=False)
    context.space_data.show_gizmo_tool=not(context.scene.previs.show_helpers and selected and selected.previs.nodes and tool and tool.idname=='builtin.move')
    if not context.scene.previs.show_helpers:return
    gpu.state.blend_set('ALPHA');gpu.state.depth_test_set('NONE')
    try:
        step=context.scene.previs.grid
        # Adjustable grid in the current orthographic editing plane, bounded for responsiveness.
        rv=context.space_data.region_3d;normal=rv.view_rotation@Vector((0,0,1))
        axis=max(range(3),key=lambda i:abs(normal[i]));others=[i for i in range(3) if i!=axis]
        center=rv.view_location
        for k in range(-20,21):
            for direction in range(2):
                a=list(center);b=list(center);a[axis]=b[axis]=0
                fixed=others[direction];vary=others[1-direction]
                a[fixed]=b[fixed]=round(center[fixed]/step)*step+k*step
                a[vary]-=20*step;b[vary]+=20*step
                line([a,b],(.35,.4,.48,.18))
        for obj in runtime.controls(context.scene):
            if obj.hide_get():continue
            p=obj.previs
            if p.nodes:
                points=[n.position for n in orthogonalize(runtime.nodes_for(obj),context.scene.previs.axis_order)]
                line(points,(.4,.65,1,.7))
                try:
                    motion=runtime.motion_for(obj)
                    for arc in motion.arcs:line(arc.points,(1,.65,.12,1),2)
                except ValueError:pass
            if p.role not in {'CAMERA','TARGET','ENV'}:
                m=obj.matrix_world;origin=m.translation
                front=m@Vector((0,.9,0));back=m@Vector((0,-.55,0))
                line([back,origin],(.95,.3,.35,1),2);line([origin,front],(.2,1,.6,1),3)
                line([m@Vector((-.14,.65,0)),front,m@Vector((.14,.65,0))],(.2,1,.6,1),2)
                for i,color in enumerate(((1,.2,.2,1),(.2,1,.2,1),(.2,.4,1,1))):
                    v=Vector((0,0,0));v[i]=.4;line([origin,m@v],color)
                line([m@Vector(v) for v in [(-.3,0,-.3),(.3,0,-.3),(.3,0,.3),(-.3,0,.3),(-.3,0,-.3)]],(.2,1,.6,.35))
            if obj.type=='CAMERA' and p.target:line([obj.matrix_world.translation,p.target.matrix_world.translation],(1,.75,.25,.6))
    finally:gpu.state.line_width_set(1);gpu.state.depth_test_set('NONE');gpu.state.blend_set('NONE')

def label(region,rv,point,text,color):
    pixel=view3d_utils.location_3d_to_region_2d(region,rv,Vector(point))
    if pixel:
        blf.position(0,pixel.x+7,pixel.y+6,0);blf.size(0,12);blf.color(0,*color);blf.draw(0,text)

def draw_labels():
    c=bpy.context
    if not c.scene or not c.scene.previs.enabled or not c.scene.previs.show_helpers:return
    if c.space_data.region_3d.view_perspective=='CAMERA':
        blf.position(0,20,30,0);blf.size(0,14);blf.color(0,.8,.85,.9,1)
        blf.draw(0,'Camera Preview' if c.scene.camera else 'Add Camera C / Target T to start preview')
        return
    for obj in runtime.controls(c.scene):
        if obj.hide_get():continue
        for i,n in enumerate(obj.previs.nodes):
            label(c.region,c.region_data,n.position,f'P{i}  {n.time:.2f}s'+(f' +{n.dwell:.2f}s' if n.dwell else ''),(1,.8,.35,1))
        if obj.previs.role not in {'CAMERA','TARGET','ENV'}:
            label(c.region,c.region_data,obj.matrix_world@Vector((0,.9,0)),'Front +Y',(.2,1,.6,1))
            label(c.region,c.region_data,obj.matrix_world@Vector((0,-.55,0)),'Back -Y',(1,.4,.4,1))

class PREVIS_UL_nodes(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        row=layout.row(align=True);row.label(text=f'P{index}',icon='DECORATE_KEYFRAME')
        row.label(text=f'{item.time:.2f}s');row.label(text=f'停 {item.dwell:.2f}s' if item.dwell else '')

class PREVIS_UL_keys(bpy.types.UIList):
    def draw_item(self,context,layout,data,item,icon,active_data,active_propname,index):
        layout.label(text=f'{item.time:.2f}s' + (f' / {item.value:.1f}mm' if hasattr(item,'value') else ' / 角度'))

class PrevisPanel:
    bl_space_type='VIEW_3D';bl_region_type='UI';bl_category='预演'
    @classmethod
    def poll(cls,context):return True

class PREVIS_PT_project(PrevisPanel,bpy.types.Panel):
    bl_idname='PREVIS_PT_project';bl_label='AI Previs Studio · 01 工程'
    def draw(self,context):
        l=self.layout;s=context.scene;p=s.previs
        row=l.row(align=True);row.operator('previs.new',text='新建');row.operator('previs.import_scene',text='导入静态场景')
        row=l.row(align=True);row.operator('previs.open_project',text='打开工程');row.operator('previs.save_project',text='保存副本')
        row=l.row(align=True);row.operator('ed.undo',text='撤销',icon='LOOP_BACK');row.operator('ed.redo',text='重做',icon='LOOP_FORWARDS')
        l.operator('previs.workspace',icon='WORKSPACE')
        if p.source_path:l.label(text='源：'+bpy.path.basename(p.source_path),icon='LOCKED')
        row=l.row(align=True)
        for view,text in [('TOP','俯'),('FRONT','前'),('RIGHT','侧'),('FREE','自由')]:row.operator('previs.view',text=text).view=view
        l.operator('previs.view',text='全屏摄影机预览').view='FULL'
        row=l.row(align=True);row.prop(p,'grid');row.prop(p,'snap',text='吸附')
        row=l.row(align=True)
        for value in (.25,.5,1):row.operator('previs.grid',text=f'{value} m').value=value
        l.prop(p,'show_helpers')
        if p.error:
            box=l.box();box.alert=True
            for e in p.error.split('; ')[:4]:box.label(text=e[:65],icon='ERROR')
        if p.warning:
            box=l.box()
            for warning in p.warning.split('; '):box.label(text=warning[:65],icon='INFO')

class PREVIS_PT_objects(PrevisPanel,bpy.types.Panel):
    bl_idname='PREVIS_PT_objects';bl_label='02 对象与白模'
    def draw(self,context):
        l=self.layout
        row=l.row(align=True)
        for shape,text in [('CUBE','方'),('BOX','长方'),('SPHERE','球'),('CYLINDER','柱')]:row.operator('previs.primitive',text=text).shape=shape
        row=l.row(align=True)
        for role,text in [('ACTOR','设为人物'),('PROP','设为物品'),('ENV','环境组')]:row.operator('previs.root',text=text).role=role
        row=l.row(align=True);row.operator('previs.proxy',text='方盒代理').shape='BOX';row.operator('previs.proxy',text='圆柱代理').shape='CYLINDER'
        l.operator('previs.camera',icon='OUTLINER_OB_CAMERA')
        for obj in runtime.controls(context.scene):
            row=l.row(align=True)
            op=row.operator('previs.object_action',text=obj.name,icon='CAMERA_DATA' if obj.type=='CAMERA' else 'OBJECT_ORIGIN');op.object_name=obj.name;op.action='SELECT'
            for action,icon in [('HIDE','HIDE_ON' if obj.previs.hidden else 'HIDE_OFF'),('LOCK','LOCKED' if obj.previs.locked else 'UNLOCKED'),('DELETE','X')]:
                op=row.operator('previs.object_action',text='',icon=icon);op.action=action;op.object_name=obj.name
        obj=active_control(context)
        if obj:
            l.prop(obj,'name',text='名称');l.prop(obj.previs,'role')
            l.prop(obj,'location',text='位置 XYZ');l.prop(obj,'rotation_euler',text='旋转 XYZ')
            l.prop(context.scene.transform_orientation_slots[0],'type',text='操作坐标轴')
            if obj.type=='MESH':l.prop(obj,'dimensions',text='尺寸')
            else:
                meshes=[o for o in obj.children if o.type=='MESH']
                if len(meshes)==1:l.prop(meshes[0],'dimensions',text='部件尺寸')
            if obj.previs.role not in {'CAMERA','TARGET','ENV'}:
                l.prop(obj.previs,'orientation');l.operator('previs.calibrate')
                l.label(text='绿色 +Y 正面；红色 -Y 背面')

class PREVIS_PT_path(PrevisPanel,bpy.types.Panel):
    bl_idname='PREVIS_PT_path';bl_label='03 路径与时间'
    def draw(self,context):
        l=self.layout;obj=active_control(context)
        if not obj:l.label(text='先选中或创建 Root 控制器');return
        p=obj.previs
        if p.role=='ENV':l.label(text='静态环境不设置运动');return
        if p.follow:l.label(text='当前跟随 Root；清除跟随后可布路径');return
        l.prop(p,'lock_z');l.prop(context.scene.previs,'axis_order')
        row=l.row(align=True);row.operator('previs.node_add',text='数值加点');row.operator('previs.pick_nodes',text='视图布点')
        l.template_list('PREVIS_UL_nodes','',p,'nodes',p,'node_index',rows=4)
        row=l.row(align=True)
        for action,text in [('INSERT','插入'),('DUPLICATE','复制'),('DELETE','删除'),('UP','↑'),('DOWN','↓')]:row.operator('previs.node_edit',text=text).action=action
        if p.nodes:
            n=p.nodes[min(p.node_index,len(p.nodes)-1)]
            l.label(text='XYZ: '+', '.join(f'{v:.2f}' for v in n.position))
            l.operator('previs.node_position',text='精确修改 XYZ（自动转折）')
            if p.node_index > 0:
                prev=p.nodes[p.node_index-1]
                l.label(text=f'本段出发 {prev.time+prev.dwell:.2f}s · 耗时 {n.time-prev.time-prev.dwell:.2f}s')
            l.prop(n,'time');l.prop(n,'dwell');l.prop(n,'easing');l.prop(n,'exact');l.prop(n,'radius')
            row=l.row(align=True);row.operator('previs.node_edit',text='移除冗余点').action='CLEAN';row.operator('previs.object_action',text='重置路径').action='RESET'
        l.prop(p,'smooth')
        if p.smooth:l.label(text='蓝：控制折线 · 橙：实际曲线')

class PREVIS_PT_camera(PrevisPanel,bpy.types.Panel):
    bl_idname='PREVIS_PT_camera';bl_label='04 摄影机与关键角度'
    def draw(self,context):
        l=self.layout;obj=active_control(context)
        if not obj:return
        p=obj.previs
        if p.role=='TARGET':
            l.prop(p,'follow');l.prop(p,'offset');l.label(text='跟随与独立路径二选一');return
        if obj.type=='CAMERA':
            l.prop(context.scene,'camera',text='活动摄影机')
            l.label(text='当前：目标锁定' if p.view_mode=='LOCK' else '当前：自由朝向')
            l.operator('previs.camera_mode');l.prop(p,'target',text='目标 T')
            if p.target:
                op=l.operator('previs.object_action',text='选择目标 T');op.object_name=p.target.name;op.action='SELECT'
            l.operator('previs.orbit')
            if p.view_mode=='LOCK':
                l.prop(p,'roll_enabled')
                if p.roll_enabled:
                    l.prop(p,'roll');l.operator('previs.key',text='记录当前 Roll').kind='ROLL'
                    l.template_list('PREVIS_UL_keys','roll',p,'rolls',p,'roll_index',rows=2)
                    if p.rolls:
                        key=p.rolls[min(p.roll_index,len(p.rolls)-1)]
                        l.prop(key,'time');l.prop(key,'rotation',index=2,text='Roll 角度');l.prop(key,'easing')
                        op=l.operator('previs.key',text='删除选中 Roll');op.kind='ROLL';op.remove=True
            else:l.label(text='自由 Roll：旋转控件选择 Local Z')
            l.prop(obj.data,'lens',text='焦距 mm',slider=True)
            row=l.row(align=True)
            for v in (18,24,35,50,85):row.operator('previs.lens',text=str(v)).value=v
            l.label(text='传感器固定 36 mm / 水平视角；景深关闭')
            row=l.row(align=True);row.operator('previs.key',text='记录焦距').kind='LENS'
            op=row.operator('previs.key',text='删除');op.kind='LENS';op.remove=True
            l.template_list('PREVIS_UL_keys','lens',p,'lenses',p,'lens_index',rows=2)
            if p.lenses:
                key=p.lenses[min(p.lens_index,len(p.lenses)-1)];l.prop(key,'time');l.prop(key,'value');l.prop(key,'easing')
        if obj.type!='CAMERA' or p.view_mode=='FREE':
            l.prop(p,'orientation')
            row=l.row(align=True);row.operator('previs.key',text='记录当前角度').kind='ANGLE'
            op=row.operator('previs.key',text='删除');op.kind='ANGLE';op.remove=True
            l.template_list('PREVIS_UL_keys','angles',p,'angles',p,'angle_index',rows=2)
            if p.angles:
                key=p.angles[min(p.angle_index,len(p.angles)-1)];l.prop(key,'time');l.prop(key,'rotation');l.prop(key,'easing')

class PREVIS_PT_output(PrevisPanel,bpy.types.Panel):
    bl_idname='PREVIS_PT_output';bl_label='05 播放与输出'
    def draw(self,context):
        l=self.layout;s=context.scene;p=s.previs
        row=l.row(align=True);row.prop(p,'fps');row.prop(p,'duration')
        row=l.row(align=True);row.operator('previs.transport',text='起点',icon='REW').action='START';row.operator('previs.transport',text='播放 / 暂停',icon='PLAY').action='PLAY'
        l.prop(s,'frame_current',text=f'时间 {(s.frame_current-1)/p.fps:.2f} 秒')
        l.prop(p,'loop');l.prop(p,'ratio')
        row=l.row(align=True);row.prop(p,'width');row.prop(p,'height')
        l.prop(p,'project_path');l.prop(p,'output_path')
        l.operator('previs.export',icon='RENDER_ANIMATION')
        l.label(text='仅输出 MP4；辅助线不参与渲染')

def header(self,context):
    if context.scene and context.scene.previs.enabled:
        row=self.layout.row(align=True);row.label(text='PREVIS')
        row.operator('previs.save_project',text='',icon='FILE_TICK')
        row.operator('previs.transport',text='',icon='PLAY').action='PLAY'
        row.operator('previs.export',text='MP4',icon='RENDER_ANIMATION')

CLASSES=(PREVIS_OT_workspace,PREVIS_OT_view,PREVIS_OT_grid,PREVIS_OT_lens,PREVIS_OT_pick_nodes,
         PREVIS_OT_drag_node,PREVIS_OT_orbit_drag,PREVIS_GGT_controls,PREVIS_UL_nodes,PREVIS_UL_keys,
         PREVIS_PT_project,PREVIS_PT_objects,PREVIS_PT_path,PREVIS_PT_camera,PREVIS_PT_output)

def register():
    for cls in CLASSES:bpy.utils.register_class(cls)
    if not bpy.app.background:
        _draw_handles.append(bpy.types.SpaceView3D.draw_handler_add(draw_world,(),'WINDOW','POST_VIEW'))
        _draw_handles.append(bpy.types.SpaceView3D.draw_handler_add(draw_labels,(),'WINDOW','POST_PIXEL'))
    bpy.types.VIEW3D_HT_header.append(header)

def unregister():
    bpy.types.VIEW3D_HT_header.remove(header)
    for h in _draw_handles:bpy.types.SpaceView3D.draw_handler_remove(h,'WINDOW')
    _draw_handles.clear()
    for cls in reversed(CLASSES):bpy.utils.unregister_class(cls)
