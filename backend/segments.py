"""Portable V1.1 path/shot evaluator, numerically mirrored by web/segments.js."""
import math
from .model import geometry as g
EPS=1e-7
add,sub,mul,length,distance,unit=g.add,g.sub,g.mul,g.length,g.distance,g.unit
def dot(a,b):return sum(x*y for x,y in zip(a,b))
def cross(a,b):return (a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0])
def qmul(a,b):
 x,y,z,w=a;X,Y,Z,W=b
 return (w*X+x*W+y*Z-z*Y,w*Y-x*Z+y*W+z*X,w*Z+x*Y-y*X+z*W,w*W-x*X-y*Y-z*Z)
def qrot(r):
 x,y,z=[v/2 for v in r]
 return qmul(qmul((0,0,math.sin(z),math.cos(z)),(0,math.sin(y),0,math.cos(y))),(math.sin(x),0,0,math.cos(x)))
def rotate(v,q):return qmul(qmul(q,(*v,0)),(-q[0],-q[1],-q[2],q[3]))[:3]
def axis_quaternion(axis,angle):return (*mul(axis,math.sin(angle/2)),math.cos(angle/2))
def camera_quaternion(state):
 if state.get('cameraRotation') is not None:return state['cameraRotation']
 if state.get('focus') is None:return state['quaternion']
 if distance(state['position'],state['focus'])<EPS:return state.get('quaternion',(0,0,0,1))
 z=unit(sub(state['position'],state['focus']));x=unit(cross(state.get('up',(0,0,1)),z))
 if length(x)<EPS:x=unit(cross((0,1,0),z))
 y=cross(z,x);m=[[x[i],y[i],z[i]] for i in range(3)];trace=sum(m[i][i] for i in range(3))
 if trace>0:
  s=math.sqrt(trace+1)*2;q=((m[2][1]-m[1][2])/s,(m[0][2]-m[2][0])/s,(m[1][0]-m[0][1])/s,s/4)
 else:
  i=max(range(3),key=lambda i:m[i][i]);j=(i+1)%3;k=(i+2)%3;s=math.sqrt(1+m[i][i]-m[j][j]-m[k][k])*2;q=[0,0,0,0]
  q[i]=s/4;q[j]=(m[j][i]+m[i][j])/s;q[k]=(m[k][i]+m[i][k])/s;q[3]=(m[k][j]-m[j][k])/s
 return qmul(q,axis_quaternion((0,0,1),state.get('roll',0)))
def slerp(a,b,f):
 d=dot(a,b)
 if d<0:b=mul(b,-1);d=-d
 if d>.9995:return unit(add(mul(a,1-f),mul(b,f)))
 theta=math.acos(min(1,d));s=math.sin(theta)
 return add(mul(a,math.sin((1-f)*theta)/s),mul(b,math.sin(f*theta)/s))
def key(keys,t,fallback,rotation=False):
 ks=sorted(keys,key=lambda k:k['time'])
 if not ks:return fallback
 a=b=ks[0];f=0
 if t>ks[0]['time']:
  a=b=ks[-1]
  for i in range(1,len(ks)):
   if t<=ks[i]['time']:a,b=ks[i-1:i+1];f=g.ease((t-a['time'])/(b['time']-a['time']),b.get('easing'));break
 return slerp(qrot(a['rotation']),qrot(b['rotation']),f) if rotation else a['value']+(b['value']-a['value'])*f

def edges(o):
 ns={n['id']:n for n in o.get('nodes',[])}
 return sorted([dict(s,a=ns[s['start']],b=ns[s['end']]) for s in o.get('segments',[]) if s.get('start') in ns and s.get('end') in ns],key=lambda s:s['startTime'])
def path_errors(o,full=False):
 errors=[];ns=o.get('nodes',[]);ss=edges(o)
 if len({n['id'] for n in ns})!=len(ns):errors.append('控制点标识重复')
 if len({s['id'] for s in o.get('segments',[])})!=len(o.get('segments',[])):errors.append('线段标识重复')
 if len(ss)!=len(o.get('segments',[])):errors.append('线段端点不存在')
 for n in ns:
  if not all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) for v in [*n['position'],n['time'],n.get('dwell',0),n.get('radius',.5)]) or n['time']<0 or n.get('dwell',0)<0 or n.get('radius',.5)<0:errors.append('控制点数值无效')
 for i,s in enumerate(ss):
  if s['endTime']-s['startTime']<=EPS:errors.append('线段时长必须大于零')
  if distance(s['a']['position'],s['b']['position'])<=EPS:errors.append('线段长度必须大于零')
  if abs(s['startTime']-s['a']['time']-s['a'].get('dwell',0))>EPS or abs(s['endTime']-s['b']['time'])>EPS:errors.append('线段时间与端点不一致')
  if i and s['startTime']<ss[i-1]['endTime']-EPS:errors.append('线段时间重叠')
  if full and i and s['start']!=ss[i-1]['end']:errors.append('路径不连续：请修复连接或单独预演线段')
 return list(dict.fromkeys(errors))
class SegmentMotion:
 def __init__(self,o):
  self.object=o;self.segments=edges(o);self.arcs=[];corners={}
  if o.get('smooth'):
   for i in range(1,len(self.segments)):
    prev,s=self.segments[i-1:i+1];n=s['a']
    if prev['end']!=s['start'] or n.get('exact') or n.get('dwell'):continue
    a,b,c=prev['a']['position'],n['position'],s['b']['position'];u,v=unit(sub(a,b)),unit(sub(c,b));r=min(n.get('radius',.5),distance(a,b)*.49,distance(b,c)*.49)
    if r>EPS and abs(dot(u,v))<.99999:corners[n['id']]=(add(b,mul(u,r)),b,add(b,mul(v,r)))
  for s in self.segments:
   points=[g.bezier(*corners[s['start']],.5+j/128) for j in range(65)] if s['start'] in corners else [s['a']['position']]
   points.extend([g.bezier(*corners[s['end']],j/128) for j in range(65)] if s['end'] in corners else [s['b']['position']]);self.arcs.append(g.Arc(points))
 def at(self,t,only=None):
  last=None
  for s,arc in zip(self.segments,self.arcs):
   if only and s['id']!=only:continue
   if t<s['startTime'] and last:return last
   f=g.ease((t-s['startTime'])/max(EPS,s['endTime']-s['startTime']),s['b'].get('easing'));p=arc.at(f)[0];tangent=unit(sub(arc.at(min(1,f+.001))[0],arc.at(max(0,f-.001))[0]));last=(p,tangent)
   if t<s['endTime']:return last
  return last or (self.object['nodes'][0]['position'] if self.object.get('nodes') else self.object['position'],(0,0,0))
class Evaluator:
 def __init__(self,p):
  self.p=p;self.objects={o['id']:o for o in p['objects']};self.motions={o['id']:SegmentMotion(o) for o in p['objects'] if o.get('segments')}
 def pose(self,o,t,only=None):
  position,tangent=self.motions[o['id']].at(t,only) if o['id'] in self.motions else (o['position'],(0,0,0));q=qrot(o['rotation'])
  if o.get('orientation')=='PATH' and length(tangent)>EPS:q=qrot((0 if o.get('lockZ') or o['role'] in ('ACTOR','PROP') else math.asin(tangent[2]),0,math.atan2(-tangent[0],tangent[1])+(math.pi if o.get('frontAxis')=='-Y' else 0)))
  elif o.get('orientation')=='MANUAL' and o.get('angles'):q=key(o['angles'],t,q,True)
  if o.get('follow') and o['follow'] in self.objects:position=self.focus(self.objects[o['follow']],o.get('offset',[0,0,0]),t,only)
  return dict(position=position,quaternion=q,scale=o['scale'])
 def focus(self,o,local,t,only=None):
  pose=self.pose(o,t,only);return add(pose['position'],rotate([v*s for v,s in zip(local,o['scale'])],pose['quaternion']))
 def base(self,c,t):
  pose=self.pose(c,t);target=self.objects.get(c.get('target'));return dict(pose,focus=self.pose(target,t)['position'] if c.get('viewMode')=='LOCK' and target else None,lens=key(c.get('lenses',[]),t,c['lens']),roll=key(c.get('rolls',[]),t,c.get('roll',0)) if c.get('rollEnabled') else 0,up=(0,0,1))
 def previous(self,c,owner,index):
  ss=edges(owner);return self.shot(c,owner,index-1,ss[index-1]['endTime']) if index>0 else self.base(c,ss[0]['startTime'] if ss else 0)
 def shot(self,c,owner,index,t,unit_override=None):
  s=unit_override or edges(owner)[index];cfg=c.get('shots',{}).get(s['id'])
  if not cfg:return self.base(c,t)
  target=self.objects.get(cfg['focusTarget'])
  if not target and cfg.get('mode')!='FREE':raise ValueError('镜头焦点对象不存在')
  inherited=cfg.get('controlVersion')!=3 and cfg['inherit'] and index>0;start=self.previous(c,owner,index) if inherited else cfg['start'];duration=s['endTime']-s['startTime'];dt=max(0,min(t-s['startTime'],duration));progress=dt/duration
  f0=cfg['focusWorld'] if cfg.get('mode')=='FREE' else self.focus(target,cfg['focusLocal'],s['startTime']);focus=f0 if cfg.get('mode')=='FREE' else self.focus(target,cfg['focusLocal'],s['startTime']+dt);up=(0,0,1);free=cfg.get('orientation')=='FREE'
  if cfg['motion']=='ORBIT':
   theta=cfg['tilt']*math.pi/180;offset=sub(start['position'],f0)
   if cfg.get('controlVersion')==3:
    angle=cfg['direction']*cfg.get('orbitAngle',360)*math.pi/180*progress;co=math.cos(angle);si=math.sin(angle)
    position=add(focus,(offset[0]*co-offset[1]*si,offset[0]*si+offset[1]*co,offset[2]))
   elif cfg.get('orbitFree'):
    radius=length(offset)
    if radius<1e-5:raise ValueError('环绕起始机位不能与焦点重合')
    u=unit(offset);reference=(0,0,1) if abs(dot((0,0,1),u))<=.999 else (0,1,0)
    base=unit(sub(reference,mul(u,dot(reference,u))));normal=rotate(base,axis_quaternion(u,theta));v=cross(normal,u);angle=cfg['direction']*2*math.pi*progress
    position=add(focus,add(mul(u,radius*math.cos(angle)),mul(v,radius*math.sin(angle))));up=normal
   else:
    u=(1,0,0);v=(0,math.cos(theta),math.sin(theta));normal=cross(u,v);radius=cfg['radius']
    if abs(dot(offset,normal))>1e-4 or abs(length(offset)-radius)>1e-4:raise ValueError('环绕起始机位与焦点、半径或倾角冲突：调整参数，或解除继承后设置起点')
    phase=math.atan2(dot(offset,v),dot(offset,u));angle=phase+cfg['direction']*2*math.pi*progress;position=add(focus,add(mul(u,radius*math.cos(angle)),mul(v,radius*math.sin(angle))));up=normal
  else:
   velocity=[0,0,0]
   if cfg['motion']=='DIAGONAL':velocity=cfg.get('velocity',[0,0,0])
   elif cfg['motion']=='DOLLY':
    sight=sub(f0,start['position']);dist=length(sight)
    if dist<1e-5:raise ValueError('沿视线运动需要不同的起始机位与焦点')
    if not free and cfg['direction']>0 and cfg['speed']*duration>=dist-1e-5:raise ValueError('推进会到达或越过焦点：请降低速度或缩短线段时长')
    velocity=mul(unit(sight),cfg['direction']*cfg['speed'])
   else:velocity['XYZ'.index(cfg['axis'])]=cfg['direction']*cfg['speed']
   position=add(add(start['position'],sub(focus,f0)),mul(velocity,dt))
  if cfg.get('mode')=='FREE' and cfg.get('freeMotion',{}).get('segments'):
   path=SegmentMotion(cfg['freeMotion']);position=add(position,sub(path.at(s['startTime']+dt)[0],path.at(s['startTime'])[0]))
  delta=cfg.get('rotationDelta',[0,0,0]);roll=start.get('roll',0) if inherited else cfg.get('roll',start.get('roll',0))
  state=dict(position=position,focus=focus,up=up,lens=cfg['lens']+(cfg['lensEnd']-cfg['lens'])*progress if 'lensEnd' in cfg else cfg.get('lens',start.get('lens',c['lens'])),roll=roll+delta[2]*progress)
  if free:
   initial=camera_quaternion(start) if inherited else start.get('quaternion') or camera_quaternion(dict(position=start['position'],focus=f0,up=up,roll=roll))
   state['cameraRotation']=unit(qmul(qmul(qmul(axis_quaternion((0,0,1),delta[0]*progress),initial),axis_quaternion((1,0,0),delta[1]*progress)),axis_quaternion((0,0,1),delta[2]*progress)))
  elif distance(position,focus)<EPS:
   state['cameraRotation']=start.get('quaternion') or qrot(c['rotation']);state['warning']='摄影机与焦点重合，暂时保留起始朝向；可继续移动机位'
  if not all(math.isfinite(v) and abs(v)<=1e6 for v in position) or not math.isfinite(state['lens']) or not 1<=state['lens']<=1000:raise ValueError('相机参数无效')
  if cfg.get('mode')=='FREE' and cfg.get('freeMotion'):
   m=cfg['freeMotion'];state['lens']=key(m.get('lenses',[]),s['startTime']+dt,state['lens'])
   if m.get('angles'):state['cameraRotation']=key(m['angles'],s['startTime']+dt,state.get('cameraRotation'),True)
  return state
 def camera(self,c,t,only=None):
  if self.p.get('shotFramework')==2:
   entry=shot_at(self.p,c,t,only)
   return self.shot(c,entry[1],0,t,entry[2]) if entry and entry[0]['id']==c['id'] else self.base(c,t)
  target=self.objects.get(c.get('target'));owner=self.objects.get(target.get('follow')) if target and c.get('viewMode')=='LOCK' else None
  if not owner:return self.base(c,t)
  ss=edges(owner)
  for i,s in enumerate(ss):
   if s['id']==only if only else t>=s['startTime'] and (t<s['endTime'] or i==len(ss)-1 and t<=s['endTime']):return self.shot(c,owner,i,t)
  return self.base(c,t)

def validate_shots(project,export=False):
 errors=[]

 for o in project['objects']:
  ss=o.get('segments',[]);shots=o.get('shots',{})
  if not isinstance(ss,list) or not isinstance(shots,dict):return ['线段或镜头数据类型无效']
  if any(not isinstance(s,dict) or not all(isinstance(s.get(k),str) for k in ('id','start','end')) for s in ss):return ['线段标识无效']
  if any(not isinstance(cfg,dict) for cfg in shots.values()):return ['镜头配置数据类型无效']
 all_ids=[s['id'] for o in project['objects'] for s in o.get('segments',[])]
 if len(set(all_ids))!=len(all_ids):return ['线段标识不能跨对象重复']
 objects={o['id']:o for o in project['objects']};segments={s['id']:(o,s) for o in project['objects'] for s in (units(o) if project.get('shotFramework')==2 else o.get('segments',[]))}
 for c in project['objects']:
  if 'segments' in c:
   try:errors.extend(c['name']+'：'+e for e in path_errors(c,export))
   except (KeyError,TypeError,ValueError):errors.append(c['name']+'：线段数据无效')
  for sid,cfg in c.get('shots',{}).items():
   try:
    if sid not in segments or c['role']!='CAMERA':raise ValueError()
    owner,s=segments[sid]
    if cfg['owner']!=owner['id'] or (cfg['focusTarget'] not in objects or (project.get('shotFramework')!=2 and cfg['focusTarget']!=owner['id'])):raise ValueError()
    if project.get('shotFramework')==2:
     if cfg.get('mode') not in ('FREE','TRACK'):raise ValueError()
     if cfg['mode']=='TRACK' and not edges(objects[cfg['focusTarget']]):raise ValueError()
     if cfg['mode']=='FREE' and (cfg.get('orientation')!='FREE' or len(cfg.get('focusWorld',[]))!=3 or not all(isinstance(v,(int,float)) and math.isfinite(v) for v in cfg['focusWorld'])):raise ValueError()
     if 'lensEnd' in cfg and not 1<=cfg['lensEnd']<=1000:raise ValueError()
     if cfg.get('freeMotion'):
      m=cfg['freeMotion']
      if path_errors(m):raise ValueError()
      for k in m.get('lenses',[]):
       if not math.isfinite(k['time']) or k['time']<0 or not 1<=k['value']<=1000:raise ValueError()
      for k in m.get('angles',[]):
       if not math.isfinite(k['time']) or k['time']<0 or len(k['rotation'])!=3 or not all(math.isfinite(v) for v in k['rotation']):raise ValueError()
    if not isinstance(cfg['inherit'],bool) or cfg['motion'] not in ('TRANSLATE','DIAGONAL','DOLLY','ORBIT') or cfg['axis'] not in ('X','Y','Z') or cfg['direction'] not in (-1,1):raise ValueError()
    if cfg.get('orientation','LOCK') not in ('LOCK','FREE'):raise ValueError()
    for key in ('velocity','rotationDelta'):
     v=cfg.get(key,[0,0,0])
     if not isinstance(v,list) or len(v)!=3 or not all(isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n) for n in v):raise ValueError()
    q=cfg['start'].get('quaternion')
    if q is not None and (not isinstance(q,list) or len(q)!=4 or not all(isinstance(n,(int,float)) and not isinstance(n,bool) and math.isfinite(n) for n in q) or abs(length(q)-1)>1e-4):raise ValueError()
    values=[*cfg['focusLocal'],*cfg['start']['position'],cfg['speed'],cfg['tilt'],cfg['radius'],cfg['lens'],cfg.get('roll',0)]
    if len(cfg['focusLocal'])!=3 or len(cfg['start']['position'])!=3 or not all(isinstance(v,(float,int)) and not isinstance(v,bool) and math.isfinite(v) for v in values):raise ValueError()
    if cfg['speed']<0 or not 0<=cfg['tilt']<=180 or (cfg['radius']<0 if cfg.get('controlVersion')==3 else cfg['radius']<=0) or not 1<=cfg['lens']<=1000:raise ValueError()
    if cfg.get('controlVersion')==3:
     if cfg['inherit'] or any(not isinstance(cfg.get(k),(int,float)) or isinstance(cfg.get(k),bool) or not math.isfinite(cfg[k]) for k in ('azimuth','orbitAngle')):raise ValueError()
     if not 0<=cfg['azimuth']<360 or not 0<=cfg['orbitAngle']<=1e6:raise ValueError()
   except (KeyError,ValueError,TypeError):errors.append(c['name']+'：镜头配置无效')
 if export and not errors:
  ev=Evaluator(project)
  for c in project['objects']:
   if c['role']!='CAMERA':continue
   for sid,cfg in c.get('shots',{}).items():
    owner,s=segments[sid]
    try:
     for t in (s['startTime'],(s['startTime']+s['endTime'])/2,s['endTime']):ev.camera(c,t,sid)
    except ValueError as e:errors.append(str(e))
 return errors


def units(o):
 return sorted(edges(o)+[dict(id=n['id'],kind='DWELL',a=n,b=n,startTime=n['time'],endTime=n['time']+n['dwell']) for n in o.get('nodes',[]) if n.get('dwell',0)>0],key=lambda s:s['startTime'])
def current_shot(p):
 for c in p['objects']:
  for sid,cfg in c.get('shots',{}).items():
   owner=next((o for o in p['objects'] if o['id']==cfg['owner']),None)
   unit=next((s for s in units(owner) if s['id']==sid),None) if owner else None
   if unit:return c,owner,unit,cfg
def shot_at(p,c,t,only=None):
 entries=[]
 for sid,cfg in c.get('shots',{}).items():
  owner=next((o for o in p['objects'] if o['id']==cfg['owner']),None)
  unit=next((s for s in units(owner) if s['id']==sid),None) if owner else None
  if unit:entries.append((c,owner,unit,cfg))
 entries.sort(key=lambda e:(e[2]['startTime'],e[2]['id']))
 if only:return next((e for e in entries if e[2]['id']==only),None)
 return next((e for e in entries if e[2]['startTime']<=t<e[2]['endTime']),entries[-1] if entries and t==entries[-1][2]['endTime'] else None)
def shot_range(p):
 return (0,p['settings']['duration'])
