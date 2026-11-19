"""Blender runs only in background mode; this bridge owns no desktop UI."""
import json
from pathlib import Path
import sys
import os
sys.dont_write_bytecode=True
import traceback
import bpy
from mathutils import Matrix, Vector
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from backend.paths import asset_file
from backend.model import validate
import ai_previs
from ai_previs import runtime
from ai_previs.operators import mark,assign_nodes,edit_batch
from ai_previs.geometry import Node

def matrix(values):return Matrix([values[i::4] for i in range(4)])
def flat(m):return [m[r][c] for c in range(4) for r in range(4)]

def build(project,render=False):
    errors=validate(project,export=render)
    if errors:raise ValueError('\n'.join(errors))
    ai_previs.register();bpy.ops.previs.new();scene=bpy.context.scene
    for old in list(bpy.data.scenes):
        if old!=scene:bpy.data.scenes.remove(old)
    scene.render.fps=project['settings']['fps'];objects={};collections={}
    # Append a source library once, so a detailed set shares its materials and textures.
    sources={}
    for item in project['objects']:
        meta=item.get('sceneSource')
        if meta:sources.setdefault(meta['asset'],{})[meta['object']]=None
    for asset, originals in sources.items():
        path=asset_file('场景',asset,legacy=ROOT)
        names=list(originals)
        with bpy.data.libraries.load(str(path),link=False) as (available,loaded):
            missing=set(names).difference(available.objects)
            if missing:raise ValueError('场景对象不存在：'+min(missing))
            loaded.objects=names[:]
        originals.update(zip(names,loaded.objects))
    with edit_batch():
        for data in project['objects']:
            role=data['role']
            if role=='CAMERA':
                obj=bpy.data.objects.new(data['name'],bpy.data.cameras.new(data['name']))
                obj.data.lens=data['lens'];obj.data.sensor_width=36;obj.data.sensor_fit='HORIZONTAL'
            else:obj=bpy.data.objects.new(data['name'],None)
            scene.collection.objects.link(obj);mark(obj,role);objects[data['id']]=obj
            source_meta=data.get('sceneSource') or {}
            for path in source_meta.get('collectionPaths',[]):
                parent=scene.collection
                for i,label in enumerate(path):
                    key=(source_meta.get('asset'),tuple(path[:i+1]))
                    if key not in collections:
                        collections[key]=bpy.data.collections.new(label);parent.children.link(collections[key])
                    parent=collections[key]
                if path and obj.name not in parent.objects:parent.objects.link(obj)
            if source_meta.get('collectionPaths') and all(source_meta['collectionPaths']) and obj.name in scene.collection.objects:scene.collection.objects.unlink(obj)
            obj['previs_id']=data['id']
            obj.location=data['position'];obj.rotation_euler=data['rotation'];obj.scale=data['scale']
            obj.previs.base_rotation=data['rotation'];obj.previs.smooth=data.get('smooth',False)
            obj.previs.orientation=data.get('orientation','FIXED');obj.previs.lock_z=data.get('lockZ',False)
            obj.hide_render=data.get('hidden',False)
            model_source=data.get('modelSource')
            if model_source:
                source=asset_file('model',model_source['name'],legacy=ROOT)
                if source.suffix.lower()!='.glb' or not source.is_file():raise ValueError('找不到原始模型：'+model_source['name'])
                before=set(bpy.data.objects)
                bpy.ops.import_scene.gltf(filepath=str(source))
                imported=set(bpy.data.objects)-before
                for child in imported:
                    if data.get('hidden'):child.hide_render=True
                    if child.parent not in imported:
                        world=child.matrix_world.copy()
                        child.parent=obj
                        child.matrix_parent_inverse=Matrix.Identity(4)
                        child.matrix_basis=Matrix.Rotation(model_source.get('localYaw',0),4,'Z')@Matrix.Translation(-Vector(model_source['center']))@world
                rig=next((child for child in imported if child.type=='ARMATURE'),None)
                bindings=[s for s in data.get('segments',[]) if s.get('motion')]
                if bindings and not rig:raise ValueError(data['name']+'：模型缺少骨架')
                if bindings:
                    rig.animation_data_create();rig.animation_data.action=None
                    for seg in sorted(bindings,key=lambda s:s['startTime']):
                        motion_path=asset_file('动作',seg['motion']['name'],legacy=ROOT);prior=set(bpy.data.objects)
                        bpy.ops.import_scene.gltf(filepath=str(motion_path));temporary=set(bpy.data.objects)-prior
                        source_rig=next((x for x in temporary if x.type=='ARMATURE' and x.animation_data and x.animation_data.action),None)
                        if not source_rig:raise ValueError('动作文件缺少骨骼动画')
                        action=source_rig.animation_data.action;start,end=action.frame_range
                        if end<=start:raise ValueError('动作时长无效')
                        first=1+seg['startTime']*scene.render.fps;last=1+seg['endTime']*scene.render.fps
                        track=rig.animation_data.nla_tracks.new();track.name='预演线段动作'
                        strip=track.strips.new('线段动作',int(round(first)),action);strip.action_frame_start=start;strip.action_frame_end=end
                        strip.repeat=max(.001,(last-first)/(end-start));strip.frame_start=first;strip.frame_end=last;strip.extrapolation='NOTHING'
                        for item in temporary:bpy.data.objects.remove(item,do_unlink=True)
                bpy.context.view_layer.objects.active=obj
            scene_source=data.get('sceneSource')
            original=None
            if scene_source:
                original=sources[scene_source['asset']][scene_source['object']]
                if scene_source.get('kind')=='LIGHT':
                    original=original.copy()
                    scene.collection.objects.link(original);original.animation_data_clear();original.parent=obj
                    original.matrix_parent_inverse=Matrix.Identity(4);original.matrix_basis=matrix(scene_source['localMatrix']);original.hide_render=data.get('hidden',False)
            for part in ([] if model_source else data.get('parts',[])):
                shape=part['shape']
                if shape=='BOX':bpy.ops.mesh.primitive_cube_add(size=1)
                elif shape=='SPHERE':bpy.ops.mesh.primitive_uv_sphere_add(segments=24,ring_count=16,radius=.5)
                elif shape=='CYLINDER':bpy.ops.mesh.primitive_cylinder_add(vertices=32,radius=.5,depth=1)
                elif shape=='CONE':bpy.ops.mesh.primitive_cone_add(vertices=32,radius1=.5,radius2=.5*part.get('topRatio',0),depth=1)
                else:
                    mesh=bpy.data.meshes.new('白模网格');mesh.from_pydata(part['vertices'],[],part['triangles']);mesh.update()
                    child=bpy.data.objects.new('白模部件',mesh);scene.collection.objects.link(child)
                if shape!='MESH':child=bpy.context.object
                if original and scene_source.get('kind')!='LIGHT' and child.type=='MESH':
                    for material in original.data.materials:child.data.materials.append(material)
                    for face,index in zip(child.data.polygons,part.get('materialIndices',[])):
                        face.material_index=min(index,max(0,len(child.data.materials)-1))
                    for face,smooth in zip(child.data.polygons,part.get('smoothFaces',[])):face.use_smooth=bool(smooth)
                    for uv_data in part.get('uvLayers',[]):
                        uv=child.data.uv_layers.new(name=uv_data['name'])
                        for face,coords in zip(child.data.polygons,uv_data['values']):
                            for index,coord in zip(face.loop_indices,coords):uv.data[index].uv=coord
                if data.get('locatorColor') and child.type=='MESH':
                    color=data['locatorColor'].lstrip('#');rgb=[int(color[i:i+2],16)/255 for i in (0,2,4)]
                    material=bpy.data.materials.new('定位颜色');material.diffuse_color=(*rgb,1);material.use_nodes=True;material.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(*rgb,1);child.data.materials.clear();child.data.materials.append(material)
                child.parent=obj;child.matrix_parent_inverse=Matrix.Identity(4)
                child.matrix_basis=matrix(part['matrix']);child.hide_render=data.get('hidden',False)
            assign_nodes(obj,[Node(tuple(n['position']),n['time'],n.get('dwell',0),n.get('exact',False),n.get('radius',.5),n.get('easing','LINEAR')) for n in (data.get('nodes',[]) if 'segments' not in data else [])])
            for key in data.get('angles',[]):
                k=obj.previs.angles.add();k.time=key['time'];k.rotation=key['rotation'];k.easing=key.get('easing','LINEAR')
            for key in data.get('lenses',[]):
                k=obj.previs.lenses.add();k.time=key['time'];k.value=key['value'];k.easing=key.get('easing','LINEAR')
            for key in data.get('rolls',[]):
                k=obj.previs.rolls.add();k.time=key['time'];k.rotation=(0,0,key['value']);k.easing=key.get('easing','LINEAR')
            obj.previs.roll=data.get('roll',0);obj.previs.roll_enabled=data.get('rollEnabled',False)
        for data in project['objects']:
            obj=objects[data['id']]
            if data.get('target'):obj.previs.target=objects[data['target']]
            if data.get('follow'):obj.previs.follow=objects[data['follow']]
            obj.previs.offset=data.get('offset',[0,0,0]);obj.previs.view_mode=data.get('viewMode','FREE')
        scene.camera=objects.get(project.get('activeCamera'))
        for key in ('duration','fps','width','height','grid'):setattr(scene.previs,key,project['settings'][key])
    scene['previs_web_project']=json.dumps(project,ensure_ascii=False,separators=(',',':'))
    scene.frame_set(1);runtime.invalidate();runtime.evaluate(scene,strict=True)
    return scene

def import_scene(payload):
    if payload.get('glb'):
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=payload['source'])
    else:bpy.ops.wm.open_mainfile(filepath=payload['source'],load_ui=False,use_scripts=False)
    scene=bpy.context.scene
    if scene.get('previs_web_project'):
        project=json.loads(scene['previs_web_project']);errors=validate(project)
        if errors:raise ValueError('\n'.join(errors))
        return {'project':project,'reopened':True}
    animated=runtime.animation_sources(scene)
    if animated and not payload.get('snapshot'):return {'needsSnapshot':True,'sources':animated[:10]}
    scene.frame_set(int(payload.get('frame',1)))
    deps=bpy.context.evaluated_depsgraph_get();objects=[];count=0
    collection_paths={}
    def collect(collection,path):
        for item in collection.objects:collection_paths.setdefault(item.name,[]).append(path)
        for child in collection.children:collect(child,path+[child.name])
    collect(scene.collection,[])
    for source in scene.objects:
        if source.hide_render or not source.visible_get():continue
        if source.instance_type!='NONE':raise ValueError('源文件含集合实例，请先将实例实体化后导入')
        obj=source.evaluated_get(deps)
        if obj.type not in {'MESH','CURVE','SURFACE','FONT','META','CAMERA','LIGHT'}:continue
        position=list(obj.matrix_world.translation)
        data={'id':'import-'+str(len(objects)),'name':source.name,'role':'ENV','position':position,'rotation':[0,0,0],'scale':[1,1,1],'nodes':[],'angles':[],'lenses':[],'rolls':[],'parts':[],'locked':True,'hidden':False,'orientation':'FIXED','smooth':False,'lockZ':False}
        if obj.type=='CAMERA':data.update(role='CAMERA',locked=False,rotation=list(obj.matrix_world.to_euler('XYZ')),lens=obj.data.lens*36/obj.data.sensor_width,viewMode='FREE')
        elif obj.type=='LIGHT':
            local=Matrix.Translation(Vector(position)).inverted()@obj.matrix_world
            data['sceneSource']={'asset':'PENDING.blend','object':source.name,'kind':'LIGHT','scene':scene.name,'localMatrix':flat(local),'collectionPaths':collection_paths.get(source.name,[])}
        else:
            mesh=obj.to_mesh();mesh.calc_loop_triangles();count+=len(mesh.vertices)
            if count>400000:raise ValueError('场景超过 40 万顶点，请先简化白模')
            local=Matrix.Translation(Vector(position)).inverted()@obj.matrix_world
            data['parts']=[{'shape':'MESH','matrix':flat(local),'vertices':[list(v.co) for v in mesh.vertices],'triangles':[list(t.vertices) for t in mesh.loop_triangles],'materialIndices':[t.material_index for t in mesh.loop_triangles],'smoothFaces':[mesh.polygons[t.polygon_index].use_smooth for t in mesh.loop_triangles],'uvLayers':[{'name':uv.name,'values':[[list(uv.data[i].uv) for i in t.loops] for t in mesh.loop_triangles]} for uv in (mesh.uv_layers if not payload.get('glb') else [])]}];obj.to_mesh_clear()
            if not payload.get('glb'):data['sceneSource']={'asset':'PENDING.blend','object':source.name,'kind':'MESH','scene':scene.name,'collectionPaths':collection_paths.get(source.name,[])}
        objects.append(data)
    if payload.get('glb'):
        parts=[];points=[]
        for data in objects:
            for part in data['parts']:
                transform=Matrix.Translation(Vector(data['position']))@matrix(part['matrix'])
                vertices=[list(transform@Vector(v)) for v in part['vertices']];points.extend(vertices)
                parts.append({**part,'vertices':vertices,'matrix':flat(Matrix.Identity(4))})
        if not points:raise ValueError('模型没有可见网格')
        center=[(min(p[i] for p in points)+max(p[i] for p in points))/2 for i in range(2)]+[min(p[2] for p in points)]
        for part in parts:part['vertices']=[[round(v[i]-center[i],6) for i in range(3)] for v in part['vertices']]
        objects=[{'id':'model','name':payload.get('sourceName','模型'),'role':'PROP','parts':parts,'position':[0,0,0],'rotation':[0,0,0],'scale':[1,1,1],'nodes':[],'angles':[],'lenses':[],'rolls':[],'orientation':'FIXED','locked':False,'hidden':False,'lockZ':False,'modelSource':{'name':Path(payload['source']).name,'center':center}}]
    if not payload.get('glb') and payload.get('packedSource'):
        for image in bpy.data.images:
            if image.users and image.source=='FILE' and not image.packed_file:
                path=Path(bpy.path.abspath(image.filepath,library=image.library))
                if not path.is_file():raise ValueError('场景贴图缺失：'+image.filepath+'。请先在 Blender 中打包外部资源后重新导入。')
        bpy.ops.file.pack_all()
        bpy.ops.wm.save_as_mainfile(filepath=payload['packedSource'],copy=True,check_existing=False)
    return {'objects':objects,'sourceName':payload.get('sourceName','静态场景')}

def convert_model(payload):
    import zipfile
    from urllib.parse import unquote, urlparse
    folder=Path(payload['source']).parent/'gltf';folder.mkdir()
    source=Path(payload['source']);kind=payload['kind']
    if kind=='zip':
        with zipfile.ZipFile(source) as z:
            infos=z.infolist()
            if len(infos)>500 or sum(i.file_size for i in infos)>128*1024*1024:raise ValueError('模型资源包过大')
            for info in infos:
                name=info.filename.replace('\\','/')
                target=(folder/name).resolve()
                if not target.is_relative_to(folder.resolve()) or name.startswith('/') or ':' in name or (info.external_attr >> 16)&0o170000==0o120000:raise ValueError('模型资源包包含无效路径')
                if info.is_dir():target.mkdir(parents=True,exist_ok=True);continue
                target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(z.read(info))
        candidates=list(folder.rglob('*.gltf'))
        if len(candidates)!=1:raise ValueError('资源包中必须且只能有一个 .gltf 文件')
        gltf=candidates[0]
    else:
        gltf=folder/'model.gltf';gltf.write_bytes(source.read_bytes())
    document=json.loads(gltf.read_text(encoding='utf-8-sig'))
    for item in document.get('buffers',[])+document.get('images',[]):
        uri=item.get('uri','')
        if not uri or uri.startswith('data:'):continue
        parsed=urlparse(uri);path=(gltf.parent/unquote(parsed.path)).resolve()
        if parsed.scheme or parsed.netloc or not path.is_relative_to(folder.resolve()) or not path.is_file():raise ValueError('模型外部资源缺失或路径无效：'+uri)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=str(gltf))
    if not any(o.type=='MESH' for o in bpy.context.scene.objects):raise ValueError('模型没有网格')
    result=Path(payload['output']);bpy.ops.export_scene.gltf(filepath=str(result),export_format='GLB')
    return {'converted':True}

def configure_preview(scene, payload):
    project=payload['project']
    settings=project['settings']
    scene.render.engine='BLENDER_EEVEE'
    source_meta=next((o['sceneSource'] for o in project['objects']
                      if o.get('sceneSource') and o['sceneSource']['asset']==payload.get('sceneAsset')),None)
    if source_meta:
        source=asset_file('场景',source_meta['asset'],legacy=ROOT)
        with bpy.data.libraries.load(str(source),link=False) as (available,loaded):
            name=source_meta.get('scene')
            loaded.scenes=[name if name in available.scenes else available.scenes[0]] if available.scenes else []
        if loaded.scenes:
            original=loaded.scenes[0]
            scene.world=original.world
            scene.render.engine=original.render.engine if original.render.engine in ('CYCLES','BLENDER_EEVEE') else 'BLENDER_EEVEE'
            scene.render.film_transparent=original.render.film_transparent
            scene.view_settings.view_transform=original.view_settings.view_transform
            scene.view_settings.look=original.view_settings.look
            scene.view_settings.exposure=original.view_settings.exposure
            scene.view_settings.gamma=original.view_settings.gamma
            if scene.render.engine=='CYCLES':
                scene.cycles.samples=original.cycles.samples
                scene.cycles.use_denoising=original.cycles.use_denoising
            bpy.data.scenes.remove(original)
    elif not any(o.type=='LIGHT' and not o.hide_render for o in scene.objects):
        light=bpy.data.lights.new('预演照明','SUN')
        light.energy=3
        obj=bpy.data.objects.new('预演照明',light)
        scene.collection.objects.link(obj)
        obj.rotation_euler=(.4,-.5,-.3)
    scene.render.resolution_x=settings['width']
    scene.render.resolution_y=settings['height']
    scene.render.resolution_percentage=100
    scene.render.image_settings.file_format='PNG'
    scene.render.image_settings.color_mode='RGBA' if scene.render.film_transparent else 'RGB'

def render_at(scene, settings, time, segment, output):
    frame=1+time*settings['fps']
    scene.frame_set(int(frame),subframe=frame-int(frame))
    runtime.evaluate(scene,strict=True,scene_time=time,camera_segment=segment)
    scene.render.filepath=str(output)
    # Render callbacks must retain the explicitly evaluated shot, including overlaps.
    previous_busy=runtime.busy
    runtime.busy=True
    try:
        bpy.context.view_layer.update()
        bpy.ops.render.render(write_still=True)
    finally:
        runtime.busy=previous_busy


def main():
    task=Path(sys.argv[sys.argv.index('--')+1]);payload=json.loads(task.read_text(encoding='utf-8'));result=task.parent/'result.json'
    try:
        mode=payload['mode']
        if payload.get('dataRoot'):os.environ['VANTAGE_DATA_DIR']=payload['dataRoot']
        if mode=='import':answer=import_scene(payload)
        elif mode=='convert':answer=convert_model(payload)
        elif mode in ('frame','clip'):
            project=payload['project']
            scene=build(project)
            configure_preview(scene,payload)
            if mode=='frame':
                render_at(scene,project['settings'],payload['time'],payload.get('segment'),payload['frameOutput'])
            else:
                folder=Path(payload['frameFolder'])
                for i,t in enumerate(payload['times']):
                    render_at(scene,project['settings'],t,payload['segment'],folder/f'{i:06d}.png')
                    print('Vantage clip frame',i+1,flush=True)
            answer={'rendered':True}
        else:
            project=payload['project'];scene=build(project,mode=='render')
            scene.previs.project_path=payload['blend'];scene.previs.output_path=payload.get('video','')
            if mode=='render' and payload.get('times'):
                runtime.configure_render(scene);scene.render.engine='BLENDER_EEVEE'
                if not any(o.type=='LIGHT' and not o.hide_render for o in scene.objects):
                    light=bpy.data.lights.new('预演照明','SUN');light.energy=3;obj=bpy.data.objects.new('预演照明',light);scene.collection.objects.link(obj);obj.rotation_euler=(.4,-.5,-.3)
                if hasattr(scene.render.image_settings,'media_type'):scene.render.image_settings.media_type='IMAGE'
                scene.render.image_settings.file_format='PNG';folder=Path(payload['frameFolder']);folder.mkdir(parents=True,exist_ok=True)
                bpy.ops.wm.save_as_mainfile(filepath=payload['blend'],check_existing=False)
                for i,t in enumerate(payload['times']):
                    frame=1+t*scene.render.fps;scene.frame_set(int(frame),subframe=frame-int(frame));runtime.evaluate(scene,strict=True)
                    scene.render.filepath=str(folder/f'{i:06d}.png');bpy.ops.render.render(write_still=True)
            elif mode=='render':
                runtime.prepare_export(scene)
                if any(o.type=='LIGHT' and not o.hide_render for o in scene.objects):
                    scene.render.engine='BLENDER_EEVEE'
                    white=bpy.data.materials.new('预演白模');white.diffuse_color=(.65,.65,.65,1);white.use_nodes=True
                    bsdf=white.node_tree.nodes.get('Principled BSDF');bsdf.inputs['Base Color'].default_value=(.65,.65,.65,1);bsdf.inputs['Roughness'].default_value=.8
                    scene.view_layers[0].material_override=white
                animated=runtime.bake(scene)
                bpy.ops.wm.save_as_mainfile(filepath=payload['blend'],check_existing=False)
                bpy.ops.render.render(animation=True);runtime.clear_bake(animated)
            elif payload.get('finalBlend'):
                scene.previs.project_path=payload['finalBlend']
                bpy.ops.wm.save_as_mainfile(filepath=payload['blend'],check_existing=False,relative_remap=False)
            else:runtime.save_project(scene,payload['blend'])
            answer={'saved':True}
        result.write_text(json.dumps(answer,ensure_ascii=False),encoding='utf-8');print('PREVIS_JOB_DONE',flush=True)
    except Exception as exc:
        result.write_text(json.dumps({'error':str(exc)},ensure_ascii=False),encoding='utf-8');traceback.print_exc();raise SystemExit(1)
if __name__=='__main__':main()

