"""Dependency-free path geometry. Coordinates are world metres, time is seconds."""
from bisect import bisect_right
from dataclasses import dataclass
from math import sqrt, isfinite

EPS = 1e-7

def add(a, b): return tuple(x + y for x, y in zip(a, b))
def sub(a, b): return tuple(x - y for x, y in zip(a, b))
def mul(a, n): return tuple(x * n for x in a)
def length(a): return sqrt(sum(x * x for x in a))
def distance(a, b): return length(sub(a, b))
def lerp(a, b, t): return add(a, mul(sub(b, a), t))
def unit(a): return mul(a, 1 / length(a)) if length(a) > EPS else (0., 0., 0.)

@dataclass(frozen=True)
class Node:
    position: tuple
    time: float = 0.
    dwell: float = 0.
    exact: bool = False
    radius: float = .5
    easing: str = 'LINEAR'  # incoming segment

def ease(t, mode):
    t = min(1., max(0., t))
    if mode == 'IN': return t * t
    if mode == 'OUT': return 1 - (1 - t) ** 2
    if mode == 'IN_OUT': return t * t * (3 - 2 * t)
    return t

def validate(nodes, duration=None):
    errors = []
    for i, n in enumerate(nodes):
        if not all(isfinite(v) for v in (*n.position, n.time, n.dwell, n.radius)):
            errors.append(f'P{i} 含无效数值'); continue
        if n.time < 0 or n.dwell < 0 or n.radius < 0:
            errors.append(f'P{i} 时间、停留和圆角不能为负')
        if duration is not None and n.time + n.dwell > duration + EPS:
            errors.append(f'P{i} 超出片段时长')
        if i:
            prev = nodes[i - 1]
            if n.time <= prev.time + prev.dwell + EPS:
                errors.append(f'P{i} 到达时间必须晚于上一点离开时间')
            if sum(abs(a - b) > EPS for a, b in zip(n.position, prev.position)) > 1:
                errors.append(f'P{i-1}→P{i} 不是单轴线段，请执行正交修复')
    return errors

def orthogonalize(nodes, order='XYZ'):
    """Preserve explicit times/dwells; apportion inserted corners by distance."""
    if not nodes: return []
    result = [nodes[0]]
    axes = ['XYZ'.index(a) for a in order]
    for end in nodes[1:]:
        start = result[-1]
        p = list(start.position)
        total = sum(abs(a - b) for a, b in zip(p, end.position))
        if total < EPS:
            result.append(end); continue
        travelled = 0.
        departure = start.time + start.dwell
        for axis in axes:
            d = abs(p[axis] - end.position[axis])
            if d < EPS: continue
            p[axis] = end.position[axis]; travelled += d
            if distance(p, end.position) < EPS:
                result.append(end)
            else:
                result.append(Node(tuple(p), departure + (end.time - departure) * travelled / total,
                                   radius=end.radius, easing=end.easing))
    return result

class Arc:
    def __init__(self, points):
        self.points = points
        self.lengths = [0.]
        for a, b in zip(points, points[1:]):
            self.lengths.append(self.lengths[-1] + distance(a, b))
        self.total = self.lengths[-1]

    def at(self, fraction):
        if self.total < EPS: return self.points[0], (0., 0., 0.)
        d = min(1., max(0., fraction)) * self.total
        idx = min(len(self.points) - 2, max(0, bisect_right(self.lengths, d) - 1))
        width = self.lengths[idx + 1] - self.lengths[idx]
        t = (d - self.lengths[idx]) / width if width > EPS else 0.
        return lerp(self.points[idx], self.points[idx + 1], t), unit(sub(self.points[idx + 1], self.points[idx]))

def bezier(a, b, c, t):
    return add(add(mul(a, (1-t)**2), mul(b, 2*t*(1-t))), mul(c, t*t))

class Motion:
    """Each timed segment owns half of each adjacent rounded corner.

    Non-exact corner arrival time denotes the rounded curve's midpoint.
    Dwell and exact nodes always disable rounding at that node.
    """
    def __init__(self, nodes, smooth=False):
        errors = validate(nodes)
        if errors: raise ValueError('; '.join(errors))
        self.nodes = nodes
        self.corners = {}
        if smooth:
            for i in range(1, len(nodes)-1):
                a, b, c = nodes[i-1].position, nodes[i].position, nodes[i+1].position
                n = nodes[i]
                if n.exact or n.dwell > 0: continue
                u, v = unit(sub(a, b)), unit(sub(c, b))
                # Only genuine orthogonal turns; no loops on reversals or collinear points.
                if abs(sum(x*y for x, y in zip(u, v))) > .001: continue
                r = min(n.radius, distance(a, b)*.49, distance(b, c)*.49)
                if r > EPS: self.corners[i] = (add(b, mul(u, r)), b, add(b, mul(v, r)))
        self.arcs = []
        for i in range(len(nodes)-1):
            points = []
            if i in self.corners:
                points.extend(bezier(*self.corners[i], .5 + j/64) for j in range(33))
            else: points.append(nodes[i].position)
            if i+1 in self.corners:
                points.extend(bezier(*self.corners[i+1], j/64) for j in range(33))
            else: points.append(nodes[i+1].position)
            self.arcs.append(Arc(points))

    def at(self, time):
        if not self.nodes: raise ValueError('无有效路径')
        heading = (0., 0., 0.)
        if time <= self.nodes[0].time + self.nodes[0].dwell:
            return self.nodes[0].position, heading
        for i, arc in enumerate(self.arcs):
            a, b = self.nodes[i:i+2]
            if time <= b.time:
                f = ease((time - a.time - a.dwell)/(b.time-a.time-a.dwell), b.easing)
                p, tangent = arc.at(f)
                return p, tangent if length(tangent) > EPS else heading
            _, tangent = arc.at(1.)
            if length(tangent) > EPS: heading = tangent
            if time <= b.time + b.dwell:
                return b.position, heading
        return self.nodes[-1].position, heading

def key_interval(keys, time):
    if not keys: return None
    if time <= keys[0].time: return keys[0], keys[0], 0.
    for a, b in zip(keys, keys[1:]):
        if time <= b.time:
            return a, b, ease((time-a.time)/(b.time-a.time), b.easing)
    return keys[-1], keys[-1], 0.
