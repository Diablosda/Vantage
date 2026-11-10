"""Validate the portable product document without requiring Blender."""
import importlib.util
import math
from pathlib import Path
import sys
from backend.paths import asset_file
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('previs_geometry',ROOT/'ai_previs'/'geometry.py')
geometry=importlib.util.module_from_spec(spec);sys.modules[spec.name]=geometry;spec.loader.exec_module(geometry)

def validate(project,export=False,asset_root=None):
    errors=[]
    if not isinstance(project,dict) or project.get('version')!=2:return ['不是此工作台的有效工程文件']
    objects=project.get('objects',[]);settings=project.get('settings',{})
    if not isinstance(objects,list) or len(objects)>300:return ['对象数量超过轻量场景上限（300）']
    def finite(n):return isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n)
    def vector(v,size=3):return isinstance(v,list) and len(v)==size and all(finite(x) for x in v)
    for key,lo,hi in [('fps',1,120),('duration',.05,600),('width',16,8192),('height',16,8192),('grid',.001,100)]:
        n=settings.get(key)
        if not finite(n) or not lo<=n<=hi:errors.append(f'工程参数 {key} 无效')
    if 'sceneScale' in settings and (not finite(settings['sceneScale']) or not .001<=settings['sceneScale']<=1000):errors.append('工程参数 sceneScale 无效')
    if 'sceneScalePivot' in settings and not vector(settings['sceneScalePivot']):errors.append('场景缩放中心无效')
    if errors:return errors
    if any(settings[k]!=int(settings[k]) for k in ('width','height','fps')):errors.append('尺寸与帧率必须为整数')
    if export and (settings['width']%2 or settings['height']%2):errors.append('H.264 的宽和高必须为偶数')
    if project.get('shotFramework')==2 and sum(isinstance(o,dict) and o.get('role')=='CAMERA' for o in objects)>1:errors.append('当前只支持一台拍摄相机')
    ids=[o.get('id') for o in objects if isinstance(o,dict)]
    if len(ids)!=len(objects) or any(not isinstance(i,str) or not i for i in ids) or len(set(ids))!=len(ids):return ['对象标识无效或重复']
    by_id={o['id']:o for o in objects};vertices=0
    for o in objects:
        name=str(o.get('name','对象'))[:80]
        if o.get('timing')=='SPEED' and (not finite(o.get('speed')) or o['speed']<=0):errors.append(name+'：路径速度无效')
        if 'controlScale' in o and (not finite(o['controlScale']) or o['controlScale']<=0):errors.append(name+'：控制点比例无效')
        if o.get('role') not in ('ACTOR','PROP','ENV','CAMERA','TARGET'):errors.append(name+'：对象类型无效')
        for key in ('position','rotation','scale'):
            if not vector(o.get(key)):errors.append(name+'：'+key+' 无效')
        if vector(o.get('scale')) and min(o['scale'])<=0:errors.append(name+'：尺寸必须大于零')
        if 'locatorColor' in o and (not isinstance(o['locatorColor'],str) or len(o['locatorColor'])!=7 or o['locatorColor'][0]!='#' or any(c not in '0123456789abcdefABCDEF' for c in o['locatorColor'][1:])):errors.append(name+'：定位颜色无效')
        if o.get('orientation','FIXED') not in ('FIXED','PATH','MANUAL'):errors.append(name+'：朝向模式无效')
        if not vector(o.get('offset',[0,0,0])):errors.append(name+'：跟随偏移无效')
        nodes=o.get('nodes',[])
        if not isinstance(nodes,list) or len(nodes)>500:errors.append(name+'：节点数量超过 500');continue
        try:
            path=[geometry.Node(tuple(n['position']),n['time'],n.get('dwell',0),n.get('exact',False),n.get('radius',.5),n.get('easing','LINEAR')) for n in nodes]
            if any(not vector(list(n.position)) for n in path):raise ValueError()
            if 'segments' not in o:errors.extend(name+'：'+e for e in geometry.validate(path,settings['duration'] if export else None))
            elif export and any(n.time+n.dwell>settings['duration']+1e-7 for n in path):errors.append(name+'：路径超出片段时长')
        except (KeyError,TypeError,ValueError):errors.append(name+'：路径数据无效')
        for kind in ('angles','lenses','rolls'):
            keys=o.get(kind,[])
            if not isinstance(keys,list) or len(keys)>500:errors.append(name+'：关键帧数量无效');continue
            times=[]
            for k in keys:
                t=k.get('time')
                if not finite(t) or t<0 or (export and t>settings['duration']):errors.append(name+'：关键时间无效')
                times.append(t)
                if kind=='angles' and not vector(k.get('rotation')):errors.append(name+'：关键角度无效')
                if kind!='angles' and not finite(k.get('value')):errors.append(name+'：镜头关键值无效')
                if kind=='lenses' and finite(k.get('value')) and not 1<=k['value']<=1000:errors.append(name+'：焦距超出范围')
            if len(set(str(t) for t in times))!=len(times):errors.append(name+'：关键时间重复')
        if o.get('follow'):
            follow=by_id.get(o['follow'])
            if not follow or follow['role'] not in ('ACTOR','PROP','ENV') or follow is o:errors.append(name+'：跟随目标无效')
            if nodes:errors.append(name+'：跟随与独立路径不能同时启用')
        if o.get('role')=='CAMERA':
            if not finite(o.get('lens')) or not 1<=o['lens']<=1000:errors.append(name+'：焦距无效')
            if o.get('viewMode')=='LOCK' and (o.get('target') not in by_id or by_id[o['target']]['role']!='TARGET'):errors.append(name+'：缺失视线目标 T')
        source=o.get('modelSource')
        if source is not None:
            if not isinstance(source,dict) or not isinstance(source.get('name'),str) or not source['name'] or '/' in source['name'] or '\\' in source['name'] or Path(source['name']).suffix.lower()!='.glb' or not vector(source.get('center')):
                errors.append(name+'：模型来源无效')
            elif not finite(source.get('localYaw',0)):errors.append(name+'：模型方向校准无效')
            elif not asset_file('model',source['name'],asset_root,ROOT).is_file():errors.append(name+'：找不到原始模型 '+source['name'])
        scene_source=o.get('sceneSource')
        if scene_source is not None:
            if not isinstance(scene_source,dict) or not isinstance(scene_source.get('asset'),str) or len(scene_source['asset'])!=70 or not scene_source['asset'].endswith('.blend') or any(c not in '0123456789abcdef' for c in scene_source['asset'][:-6]) or not isinstance(scene_source.get('object'),str) or not scene_source['object'] or scene_source.get('kind') not in ('MESH','LIGHT'):
                errors.append(name+'：场景来源无效')
            elif scene_source['kind']=='LIGHT' and not vector(scene_source.get('localMatrix'),16):errors.append(name+'：灯光变换无效')
            elif not asset_file('场景',scene_source['asset'],asset_root,ROOT).is_file():errors.append(name+'：找不到场景资源')
        for segment in o.get('segments',[]):
            motion=segment.get('motion')
            if motion is not None:
                name_motion=motion.get('name') if isinstance(motion,dict) else None
                if not o.get('modelSource') or not isinstance(name_motion,str) or len(name_motion)!=68 or not name_motion.endswith('.glb') or any(c not in '0123456789abcdef' for c in name_motion[:-4]):errors.append(name+'：动作来源无效')
                elif not asset_file('动作',name_motion,asset_root,ROOT).is_file():errors.append(name+'：找不到绑定的动作文件')
        for part in o.get('parts',[]):
            if part.get('shape') not in ('BOX','SPHERE','CYLINDER','CONE','MESH'):errors.append(name+'：部件形状无效')
            if part.get('shape')=='CONE' and (not finite(part.get('topRatio',0)) or part.get('topRatio',0)<0):errors.append(name+'：圆锥顶部半径无效')
            if not vector(part.get('matrix'),16):errors.append(name+'：部件变换无效')
            if part.get('shape')=='MESH':
                points=part.get('vertices',[]);faces=part.get('triangles',[]);vertices+=len(points)
                if any(not vector(p) for p in points):errors.append(name+'：网格坐标无效')
                if any(not isinstance(f,list) or len(f)!=3 or any(not isinstance(i,int) or not 0<=i<len(points) for i in f) for f in faces):errors.append(name+'：网格拓扑无效')
    if vertices>400000:errors.append('导入网格超过 40 万顶点，请先简化或使用代理')
    if export and (project.get('activeCamera') not in by_id or by_id[project['activeCamera']]['role']!='CAMERA'):errors.append('请先添加并选择活动摄影机')
    from backend.segments import validate_shots
    errors.extend(validate_shots(project,export))
    return errors
