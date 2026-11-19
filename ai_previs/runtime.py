import json
import math
import os
import shutil
import tempfile
import bpy
from bpy.app.handlers import persistent
from mathutils import Vector, Euler, Quaternion
from .geometry import Node, Motion, key_interval, length, validate

busy = False
cache = {}
_transform_stamps = {}

def invalidate(): cache.clear(); _transform_stamps.clear()

def nodes_for(obj):
    return [Node(tuple(n.position), n.time, n.dwell, n.exact, n.radius, n.easing) for n in obj.previs.nodes]

def motion_for(obj):
    key = obj.as_pointer()
    if key not in cache: cache[key] = Motion(nodes_for(obj), obj.previs.smooth)
    return cache[key]

def controls(scene): return [o for o in scene.objects if o.previs.managed]

def transform_stamp(scene):
    return tuple((o.as_pointer(),tuple(o.location),tuple(o.rotation_euler),tuple(o.scale)) for o in controls(scene))

def apply_rotation(obj, time, tangent):
    p = obj.previs
    if p.orientation == 'PATH':
        if length(tangent) > 1e-7:
            obj.rotation_euler = Vector(tangent).to_track_quat('Y','Z').to_euler()
        else: obj.rotation_euler = p.base_rotation
    elif p.orientation == 'MANUAL' and p.angles:
        keys = sorted(p.angles, key=lambda k: k.time)
        a,b,f = key_interval(keys,time)
        obj.rotation_euler = Euler(a.rotation).to_quaternion().slerp(Euler(b.rotation).to_quaternion(),f).to_euler()

def camera_quaternion(position, target, roll=0.):
    direction = Vector(target) - Vector(position)
    if direction.length < 1e-5: raise ValueError('摄影机 C 与目标 T 重合，请拉开距离')
    direction.normalize()
    # Deterministic fallback avoids NaNs at poles; validation warns about proximity.
    q = direction.to_track_quat('-Z', 'Y')
    return q @ Quaternion((0,0,1), roll)

def portable_evaluator(scene):
    raw=scene.get('previs_web_project')
    if not raw:return None
    key=('portable',scene.as_pointer())
    if key not in cache:
        project=json.loads(raw)
        if not any('segments' in o for o in project['objects']):return None
        from backend.segments import Evaluator
        cache[key]=Evaluator(project)
    return cache[key]

def portable_rotation(state):
    from backend.segments import camera_quaternion
    x,y,z,w=camera_quaternion(state)
    return Quaternion((w,x,y,z))


def evaluate(scene, strict=False, *, scene_time=None, camera_segment=None):
    global busy
    if busy or not scene.previs.enabled: return
    busy = True
    errors = []
    warnings = []
    try:
        time = (scene.frame_current + scene.frame_subframe - 1) / scene.previs.fps
        objs = controls(scene)
        portable=portable_evaluator(scene)
        if portable:
            from backend.segments import shot_range
            time = time + shot_range(portable.p)[0] if scene_time is None else scene_time
            for obj in objs:
                data=portable.objects.get(obj.get('previs_id'))
                if not data:continue
                try:
                    state=portable.camera(data,time,camera_segment) if data['role']=='CAMERA' else portable.pose(data,time)
                    obj.location=state['position'];obj.rotation_euler=portable_rotation(state).to_euler();obj.scale=data['scale']
                    if data['role']=='CAMERA':obj.data.lens=state['lens']
                except ValueError as exc:errors.append(str(exc))
            scene.previs.error='; '.join(errors)[:1024];scene.previs.warning=''
            if errors and strict:raise ValueError('; '.join(errors))
            return
        for obj in objs:
            p = obj.previs
            tangent = (0,0,0)
            try:
                if p.nodes and not (p.role == 'TARGET' and p.follow):
                    pos,tangent = motion_for(obj).at(time)
                    obj.location = pos
                apply_rotation(obj,time,tangent)
                if obj.type == 'CAMERA' and p.lenses:
                    a,b,f = key_interval(sorted(p.lenses,key=lambda k:k.time),time)
                    obj.data.lens = a.value+(b.value-a.value)*f
            except (ValueError, ZeroDivisionError) as exc: errors.append(f'{obj.name}: {exc}')
        bpy.context.view_layer.update()
        for obj in objs:
            p = obj.previs
            if p.role == 'TARGET' and p.follow:
                if p.follow == obj or p.follow.previs.role in {'TARGET','CAMERA'}:
                    errors.append(f'{obj.name}: 跟随目标必须是人物或物品 Root')
                else: obj.location = p.follow.matrix_world @ Vector(p.offset)
        bpy.context.view_layer.update()
        for obj in objs:
            p = obj.previs
            if obj.type == 'CAMERA' and p.view_mode == 'LOCK':
                if not p.target or p.target.name not in scene.objects:
                    errors.append(f'{obj.name}: 缺失视线目标 T'); continue
                try:
                    direction = p.target.matrix_world.translation-obj.location
                    if direction.length>1e-5 and abs(direction.normalized().z)>.999:
                        warnings.append(f'{obj.name}: 视线接近竖直，上方向退化；建议移动 T 避免跨越极点')
                    roll = p.roll if p.roll_enabled else 0.
                    if p.roll_enabled and p.rolls:
                        a,b,f = key_interval(sorted(p.rolls,key=lambda k:k.time),time)
                        roll = a.rotation[2]+(b.rotation[2]-a.rotation[2])*f
                    obj.rotation_euler = camera_quaternion(obj.location,p.target.matrix_world.translation,roll).to_euler()
                except ValueError as exc: errors.append(str(exc))
        scene.previs.error = '; '.join(errors)[:1024]
        scene.previs.warning = '; '.join(warnings)[:1024]
    finally: busy = False
    _transform_stamps[scene.as_pointer()] = transform_stamp(scene)
    if errors and strict: raise ValueError('; '.join(errors))

@persistent
def transforms_changed(scene,depsgraph):
    if busy or not scene.previs.enabled:return
    stamp=transform_stamp(scene)
    if _transform_stamps.get(scene.as_pointer())==stamp:return
    for obj in controls(scene):
        if obj.previs.orientation=='FIXED':obj.previs.base_rotation=obj.rotation_euler
    evaluate(scene)

@persistent
def frame_change(scene, depsgraph=None):
    evaluate(scene)
    if scene.previs.enabled and not scene.previs.loop and not bpy.app.background:
        screen=bpy.context.screen
        if screen and screen.is_animation_playing and scene.frame_current>=scene.frame_end:
            def stop_playback():
                if bpy.context.screen and bpy.context.screen.is_animation_playing:
                    bpy.ops.screen.animation_cancel(restore_frame=False)
                return None
            if not bpy.app.timers.is_registered(stop_playback):bpy.app.timers.register(stop_playback,first_interval=.001)

@persistent
def loaded(_):
    invalidate()
    if bpy.context.scene: evaluate(bpy.context.scene)

@persistent
def undo_post(_): loaded(None)

def animation_sources(scene):
    found = []
    ids = [scene, scene.world] + list(scene.objects)
    ids += [o.data for o in scene.objects if o.data]
    ids += [o.data.shape_keys for o in scene.objects if o.type == 'MESH' and o.data.shape_keys]
    for data in ids:
        anim = getattr(data, 'animation_data', None)
        if anim and (anim.action or anim.nla_tracks or anim.drivers): found.append(data.name)
    # Constraints can be time-dependent indirectly: treat all as requiring explicit snapshot.
    for obj in scene.objects:
        if obj.constraints or any(m.type in {'ARMATURE','MESH_CACHE','MESH_SEQUENCE_CACHE','NODES'} for m in obj.modifiers):
            found.append(obj.name + '（约束/动态修改器）')
    return sorted(set(found))

def validate_scene(scene):
    if portable_evaluator(scene):
        from backend.model import validate as validate_document
        return validate_document(json.loads(scene['previs_web_project']),True)
    errors = []
    if not scene.camera or scene.camera.type != 'CAMERA': errors.append('没有活动摄影机')
    for obj in controls(scene):
        p = obj.previs
        errors.extend(f'{obj.name}: {e}' for e in validate(nodes_for(obj),scene.previs.duration))
        if p.nodes and obj.parent: errors.append(f'{obj.name}: 路径 Root 不能有父节点')
        for name, keys in [('角度',p.angles),('焦距',p.lenses),('Roll',p.rolls)]:
            times = sorted(k.time for k in keys)
            if len(set(times)) != len(times): errors.append(f'{obj.name}: {name}关键时间重复')
            if any(t > scene.previs.duration for t in times): errors.append(f'{obj.name}: {name}关键时间超出片段')
        if obj.type == 'CAMERA' and p.view_mode == 'LOCK' and (not p.target or p.target.name not in scene.objects):
            errors.append(f'{obj.name}: 缺失目标 T')
        if p.follow and p.nodes: errors.append(f'{obj.name}: 跟随与独立路径不能同时启用')
    external = animation_sources(scene)
    if external: errors.append('场景含外部动画/约束，请先静态化导入：' + '、'.join(external[:5]))
    return errors

def safe_output(path, suffix):
    if not path: raise ValueError('请填写输出路径')
    result = os.path.abspath(bpy.path.abspath(path))
    if not result.lower().endswith(suffix): raise ValueError(f'路径必须以 {suffix} 结尾')
    parent = os.path.dirname(result)
    if not os.path.isdir(parent): raise ValueError('输出目录不存在')
    if os.path.isdir(result): raise ValueError('输出路径是文件夹')
    try:
        with tempfile.NamedTemporaryFile(dir=parent, prefix='.previs_write_'): pass
    except OSError as exc: raise ValueError(f'输出目录不可写：{exc}') from exc
    return result

def same_path(a,b):
    return bool(a and b) and os.path.normcase(os.path.realpath(bpy.path.abspath(a))) == os.path.normcase(os.path.realpath(bpy.path.abspath(b)))

def save_project(scene,path):
    path = safe_output(path,'.blend')
    if same_path(path,scene.previs.source_path): raise ValueError('不能覆盖原始导入文件，请选择工程副本路径')
    scene.previs.project_path = path
    # Establish the project as the current file, so subsequent Ctrl-S cannot overwrite source.
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False)
    return path

def configure_render(scene):
    p = scene.previs; r = scene.render
    if p.width % 2 or p.height % 2: raise ValueError('H.264 视频宽高必须为偶数')
    r.engine = 'BLENDER_WORKBENCH'
    r.fps = p.fps; r.fps_base = 1.; r.resolution_percentage = 100
    r.resolution_x = p.width; r.resolution_y = p.height
    duration=p.duration
    portable=portable_evaluator(scene)
    if portable:
        from backend.segments import shot_range
        start,end=shot_range(portable.p);duration=end-start
    scene.frame_start = 1; scene.frame_end = max(1,round(duration*p.fps))
    if hasattr(r.image_settings,'media_type'): r.image_settings.media_type = 'VIDEO'
    r.image_settings.file_format = 'FFMPEG'
    r.ffmpeg.format = 'MPEG4'; r.ffmpeg.codec = 'H264'
    r.ffmpeg.constant_rate_factor = 'MEDIUM'; r.ffmpeg.audio_codec = 'NONE'
    r.use_file_extension = True
    r.use_sequencer = False; r.use_compositing = False
    r.use_lock_interface = True
    shade = scene.display.shading
    shade.light = 'STUDIO'; shade.color_type = 'SINGLE'; shade.single_color = (.65,.65,.65)
    shade.show_shadows = True; shade.show_cavity = True
    shade.background_type = 'WORLD'; scene.world.color = (.08,.08,.08)
    scene.camera.data.dof.use_dof = False

def prepare_export(scene):
    errors = validate_scene(scene)
    if errors: raise ValueError('\n'.join(errors))
    video = safe_output(scene.previs.output_path,'.mp4')
    project = safe_output(scene.previs.project_path,'.blend')
    if same_path(project,scene.previs.source_path): raise ValueError('工程副本不能覆盖原始文件')
    free = shutil.disk_usage(os.path.dirname(video)).free
    estimate = max(128*1024**2, int(scene.previs.duration*4*1024**2))
    if free < estimate: raise ValueError('输出磁盘可用空间不足')
    configure_render(scene)
    old = scene.frame_current
    # Evaluate every output sample before writing; catch target collisions along animations.
    try:
        for frame in range(scene.frame_start,scene.frame_end+1):
            scene.frame_set(frame); evaluate(scene,strict=True)
    finally: scene.frame_set(old)
    scene.render.filepath = video
    save_project(scene,project)
    return video

def bake(scene):
    """Temporary Blender curves for deterministic render; product metadata remains authoritative."""
    old = scene.frame_current
    animated = []
    for obj in controls(scene):
        p = obj.previs
        if portable_evaluator(scene) or p.nodes or p.angles or p.follow or (obj.type == 'CAMERA' and p.view_mode == 'LOCK'):
            animated.append(obj)
        if obj.type == 'CAMERA' and (p.lenses or portable_evaluator(scene)): animated.append(obj.data)
    for frame in range(scene.frame_start,scene.frame_end+1):
        scene.frame_set(frame); evaluate(scene,strict=True)
        for item in animated:
            if isinstance(item,bpy.types.Object):
                item.keyframe_insert(data_path='location',frame=frame,group='Previs')
                item.keyframe_insert(data_path='rotation_euler',frame=frame,group='Previs')
            else: item.keyframe_insert(data_path='lens',frame=frame,group='Previs')
    scene.frame_set(old)
    return animated

def clear_bake(animated):
    for item in animated:
        action = item.animation_data.action if item.animation_data else None
        item.animation_data_clear()
        if action and action.users == 0: bpy.data.actions.remove(action)

def register():
    for collection,fn in [(bpy.app.handlers.frame_change_pre,frame_change),(bpy.app.handlers.load_post,loaded),
                          (bpy.app.handlers.undo_post,undo_post),(bpy.app.handlers.redo_post,undo_post),
                          (bpy.app.handlers.depsgraph_update_post,transforms_changed)]:
        if fn not in collection: collection.append(fn)

def unregister():
    for collection,fn in [(bpy.app.handlers.frame_change_pre,frame_change),(bpy.app.handlers.load_post,loaded),
                          (bpy.app.handlers.undo_post,undo_post),(bpy.app.handlers.redo_post,undo_post),
                          (bpy.app.handlers.depsgraph_update_post,transforms_changed)]:
        if fn in collection: collection.remove(fn)
    invalidate()
