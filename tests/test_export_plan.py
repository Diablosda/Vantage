import test_environment
import os
import unittest
from backend.export_plan import export_times
class ExportPlanTests(unittest.TestCase):
 def project(self):
  o={'id':'actor','nodes':[{'id':'a','position':[0,0,0],'time':0,'dwell':0},{'id':'b','position':[1,0,0],'time':1,'dwell':1},{'id':'c','position':[2,0,0],'time':3,'dwell':0},{'id':'d','position':[3,0,0],'time':4,'dwell':0}], 'segments':[{'id':'s1','start':'a','end':'b','startTime':0,'endTime':1},{'id':'s2','start':'b','end':'c','startTime':2,'endTime':3},{'id':'s3','start':'c','end':'d','startTime':3,'endTime':4}]}
  c={'id':'cam','shots':{'s1':{'owner':'actor'},'s3':{'owner':'actor'}}}
  return {'activeCamera':'cam','objects':[o,c],'settings':{'fps':2,'duration':8}}
 def test_cuts_unconfigured_gaps_and_trailing_time(self):self.assertEqual(export_times(self.project()),[0,.5,3,3.5])
 def test_current_only(self):self.assertEqual(export_times(self.project(),'current','actor','s3'),[3,3.5])
 def test_unconfigured_current_rejected(self):
  with self.assertRaises(ValueError):export_times(self.project(),'current','actor','s2')
 def test_dwell_and_overlap_union(self):
  p=self.project();p['objects'][1]['shots']['b']={'owner':'actor'};self.assertEqual(export_times(p),[0,.5,1,1.5,3,3.5])
