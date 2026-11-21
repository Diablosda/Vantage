import math
from backend.segments import video_entries

def export_times(project,scope='all',owner=None,segment=None):
 camera=next((o for o in project['objects'] if o['id']==project.get('activeCamera')),None)
 ranges=[]
 for _,obj,unit,_ in video_entries(project,camera) if camera else []:
  if scope=='all' or obj['id']==owner and unit['id']==segment:ranges.append((unit['startTime'],unit['endTime']))
 if scope not in ('all','current'):raise ValueError('导出范围无效')
 if not ranges:raise ValueError('所选范围没有可导出的视频段')
 merged=[]
 for a,b in sorted(ranges):
  if merged and a<=merged[-1][1]+1e-8:merged[-1]=(merged[-1][0],max(b,merged[-1][1]))
  else:merged.append((a,b))
 fps=project['settings']['fps'];times=[a+i/fps for a,b in merged for i in range(max(1,math.ceil((b-a)*fps-1e-8)))]
 if len(times)>100000:raise ValueError('导出帧数超过 10 万，请缩短范围')
 return times


def clip_times(project, owner, segment, first_frame):
    camera = next((o for o in project['objects'] if o['id'] == project.get('activeCamera')), None)
    entry = next((e for e in video_entries(project, camera) if e[1]['id'] == owner and e[2]['id'] == segment), None) if camera else None
    if not entry:
        raise ValueError('找不到所选轨道片段')
    _, _, unit, shot = entry
    fps = project['settings']['fps']
    start = unit['startTime']
    count = max(1, math.ceil((unit['endTime'] - start) * fps - 1e-8))
    cuts = {math.floor(t * fps + .5) for t in (shot or unit).get('clipCuts', [])}
    bounds = sorted({0, count} | {frame for frame in cuts if 0 < frame < count})
    if type(first_frame) is not int or first_frame not in bounds[:-1]:
        raise ValueError('轨道片段边界已变化，请重新选择')
    end = bounds[bounds.index(first_frame) + 1]
    return [start + i / fps for i in range(first_frame, end)]
