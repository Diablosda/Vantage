import test_environment
import os
import importlib.util
import math
from pathlib import Path
import sys
import unittest

spec=importlib.util.spec_from_file_location('geometry',Path(__file__).resolve().parents[1]/'ai_previs'/'geometry.py')
g=importlib.util.module_from_spec(spec);sys.modules['geometry']=g;spec.loader.exec_module(g)

class GeometryTests(unittest.TestCase):
    def test_axis_orders_preserve_schedule(self):
        for order in ('XYZ','XZY','YXZ','YZX','ZXY','ZYX'):
            result=g.orthogonalize([g.Node((-.3,0,1),.2,.3),g.Node((1,2,3),4,.7,True)],order)
            self.assertEqual(len(result),4)
            self.assertEqual(result[-1].time,4)
            self.assertEqual(result[-1].dwell,.7)
            self.assertEqual(g.validate(result),[])

    def test_reject_invalid_schedule_and_diagonal(self):
        self.assertTrue(g.validate([g.Node((0,0,0),0,2),g.Node((0,1,0),1)]))
        self.assertTrue(g.validate([g.Node((0,0,0)),g.Node((1,1,0),1)]))
        self.assertTrue(g.validate([g.Node((math.nan,0,0))]))

    def test_rounding_continuity_and_radius_limit(self):
        path=[g.Node((0,0,0)),g.Node((1.4,0,0),2,radius=500),g.Node((1.4,.6,0),3)]
        motion=g.Motion(path,True)
        self.assertLess(g.distance(motion.arcs[0].points[-1],motion.arcs[1].points[0]),1e-10)
        self.assertGreater(g.distance(motion.at(2)[0],path[1].position),.01)
        before=motion.at(2-1e-6)[0];after=motion.at(2+1e-6)[0]
        self.assertLess(g.distance(before,after),1e-5)

    def test_dwell_and_exact_disable_corner_cutting(self):
        for exact,dwell in ((True,0),(False,.8)):
            path=[g.Node((0,0,0)),g.Node((1.4,0,0),2,dwell,exact),g.Node((1.4,.6,0),4)]
            motion=g.Motion(path,True)
            self.assertEqual(motion.at(2)[0],path[1].position)
            self.assertEqual(motion.at(2+dwell/2)[0],path[1].position)
            self.assertEqual(motion.at(20)[0],path[-1].position)

    def test_constant_arc_length_speed(self):
        motion=g.Motion([g.Node((0,0,0)),g.Node((1.4,0,0),2,radius=.4),g.Node((1.4,2,0),4)],True)
        # Dense Euclidean measurements approximate cumulative arc length.
        points=[motion.at(i*.002)[0] for i in range(1001)]
        speeds=[g.distance(a,b)/.002 for a,b in zip(points,points[1:])]
        self.assertLess(max(speeds)-min(speeds),.002)

    def test_pause_preserves_heading_random_access(self):
        m=g.Motion([g.Node((0,0,0)),g.Node((0,1.3,0),1,.8),g.Node((.5,1.3,0),3)])
        self.assertEqual(m.at(1.4)[1],(0,1,0))
        self.assertEqual(m.at(0)[1],(0,0,0))

    def test_easing_and_stationary_object(self):
        self.assertLess(g.ease(.25,'IN'),.25)
        self.assertGreater(g.ease(.25,'OUT'),.25)
        self.assertEqual(g.ease(.5,'IN_OUT'),.5)
        self.assertEqual(g.Motion([g.Node((3,4,5))]).at(10)[0],(3,4,5))
        self.assertEqual(g.Motion([g.Node((0,0,0)),g.Node((0,0,0),1)]).at(.5)[0],(0,0,0))

if __name__=='__main__':unittest.main(verbosity=2)
