import math
from backend.segments import units

def export_times(project,scope='all',owner=None,segment=None):
 camera=next((o for o in project['objects'] if o['id']==project.get('activeCamera')),None)
 ranges=[]
 for sid,cfg in (camera or {}).get('shots',{}).items():
  obj=next((o for o in project['objects'] if o['id']==cfg.get('owner')),None)
  unit=next((u for u in units(obj) if u['id']==sid),None) if obj else None
  if unit and (scope=='all' or obj['id']==owner and sid==segment):ranges.append((unit['startTime'],unit['endTime']))
 if scope not in ('all','current'):raise ValueError('导出范围无效')
 if not ranges:raise ValueError('所选范围没有设置镜头，请先设置镜头')
 merged=[]
 for a,b in sorted(ranges):
  if merged and a<=merged[-1][1]+1e-8:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
  else:merged.append((a,b))
 fps=project['settings']['fps'];times=[a+i/fps for a,b in merged for i in range(max(1,math.ceil((b-a)*fps-1e-8)))]
 if len(times)>100000:raise ValueError('导出帧数超过 10 万，请缩短范围')
 return times
