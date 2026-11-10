import hashlib
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import ai_previs
from ai_previs import runtime
from ai_previs.geometry import Node
from ai_previs.operators import assign_nodes, edit_batch, activate

ai_previs.register()

class BlenderTests(unittest.TestCase):
    def setUp(self):
        bpy.ops.previs.new();self.scene=bpy.context.scene

    def root(self):
        bpy.ops.previs.primitive(shape='BOX');bpy.ops.previs.root(role='ACTOR')
        return bpy.context.object

    def camera(self):
        bpy.ops.previs.camera();return bpy.context.object

    def test_root_preserves_multiple_parts(self):
        bpy.ops.previs.primitive(shape='CUBE');a=bpy.context.object;a.location=(.4,.7,.2)
        bpy.ops.previs.primitive(shape='CYLINDER');b=bpy.context.object;b.location=(.4,.7,1.1)
        a.select_set(True);bpy.context.view_layer.update()
        before=[o.matrix_world.copy() for o in (a,b)]
        bpy.ops.previs.root(role='ACTOR');root=bpy.context.object
        bpy.context.view_layer.update()
        for o,m in zip((a,b),before):self.assertLess((o.matrix_world.translation-m.translation).length,1e-6)
        delta=Vector((.8,-.4,.2));root.location+=delta;bpy.context.view_layer.update()
        for o,m in zip((a,b),before):self.assertLess((o.matrix_world.translation-m.translation-delta).length,1e-6)

    def test_mode_switch_preserves_composition_and_c_position(self):
        cam=self.camera();q=cam.rotation_euler.to_quaternion();pos=cam.location.copy()
        bpy.ops.previs.camera_mode()
        self.assertLess(q.rotation_difference(cam.rotation_euler.to_quaternion()).angle,1e-5)
        cam.previs.target.location.x+=.8;runtime.evaluate(self.scene)
        self.assertLess((cam.location-pos).length,1e-7)
        q=cam.rotation_euler.to_quaternion();bpy.ops.previs.camera_mode()
        self.assertLess(q.rotation_difference(cam.rotation_euler.to_quaternion()).angle,1e-5)

    def test_switch_with_target_path_preserves_path_shape(self):
        cam=self.camera();target=cam.previs.target
        assign_nodes(target,[Node((0,0,1)),Node((.8,0,1),2)])
        q=cam.rotation_euler.to_quaternion();bpy.ops.previs.camera_mode()
        self.assertLess(q.rotation_difference(cam.rotation_euler.to_quaternion()).angle,1e-5)
        self.assertAlmostEqual(target.previs.nodes[1].position.x-target.previs.nodes[0].position.x,.8,places=5)

    def test_follow_local_offset_and_lens(self):
        actor=self.root();actor.rotation_euler.z=math.pi/2
        assign_nodes(actor,[Node((0,0,0)),Node((1.2,0,0),2)])
        cam=self.camera();bpy.ops.previs.camera_mode();target=cam.previs.target
        with edit_batch():
            target.previs.follow=actor;target.previs.offset=(0,.3,1.2)
            for time,value in ((0,28),(2,63)):
                key=cam.previs.lenses.add();key.time=time;key.value=value
        self.scene.frame_set(25)
        expected=actor.matrix_world@Vector((0,.3,1.2))
        self.assertLess((target.location-expected).length,1e-5)
        self.assertAlmostEqual(cam.data.lens,45.5,places=4)
        direction=(target.location-cam.location).normalized()
        actual=cam.rotation_euler.to_quaternion()@Vector((0,0,-1))
        self.assertLess((direction-actual).length,1e-5)

    def test_live_target_drag_and_orbit(self):
        cam=self.camera();bpy.ops.previs.camera_mode()
        target=cam.previs.target;target.location.y+=.65
        bpy.context.view_layer.update()
        actual=cam.rotation_euler.to_quaternion()@Vector((0,0,-1))
        self.assertLess((actual-(target.location-cam.location).normalized()).length,1e-5)
        origin=target.location.copy();radius=(cam.location-origin).length
        bpy.ops.previs.orbit(angle=.35,elevation=.1)
        self.assertLess((target.location-origin).length,1e-6)
        self.assertAlmostEqual((cam.location-origin).length,radius,places=5)

    def test_independent_manual_rotation_and_position(self):
        obj=self.root();assign_nodes(obj,[Node((0,0,0)),Node((.9,0,0),2)])
        with edit_batch():
            obj.previs.orientation='MANUAL'
            for time,angle in ((0,0),(2,math.pi*.5)):
                key=obj.previs.angles.add();key.time=time;key.rotation=(0,0,angle)
        self.scene.frame_set(25)
        self.assertAlmostEqual(obj.location.x,.45,places=5)
        self.assertAlmostEqual(obj.rotation_euler.z,math.pi/4,places=5)
        self.assertEqual(len(obj.previs.nodes),2)

    def test_target_collision_missing_camera_and_odd_dimensions(self):
        self.assertIn('没有活动摄影机',runtime.validate_scene(self.scene))
        cam=self.camera();bpy.ops.previs.camera_mode();cam.previs.target.location=cam.location
        with self.assertRaisesRegex(ValueError,'重合'):runtime.evaluate(self.scene,strict=True)
        self.scene.previs.width=193
        with self.assertRaisesRegex(ValueError,'偶数'):runtime.configure_render(self.scene)

    def test_ratio_presets(self):
        for ratio,size in [('1:1',(720,720)),('4:3',(960,720)),('3:4',(720,960)),('16:9',(1280,720)),('9:16',(720,1280)),('21:9',(1680,720))]:
            self.scene.previs.ratio=ratio
            self.assertEqual((self.scene.render.resolution_x,self.scene.render.resolution_y),size)

    def test_static_import_and_explicit_animation_snapshot(self):
        # This is an import safety fixture, not a cinematic acceptance example.
        with tempfile.TemporaryDirectory(prefix='.import_test_',dir=ROOT) as tmp:
            source=Path(tmp)/'source.blend'
            self.scene.previs.enabled=False
            bpy.ops.mesh.primitive_cube_add(size=.7,location=(.3,.2,.6));obj=bpy.context.object
            obj.keyframe_insert(data_path='location',frame=1)
            obj.location.x=1.7;obj.keyframe_insert(data_path='location',frame=13)
            self.scene.frame_set(13)
            source_scene=self.scene.name
            bpy.ops.wm.save_as_mainfile(filepath=str(source),copy=True)
            digest=hashlib.sha256(source.read_bytes()).hexdigest()
            with self.assertRaisesRegex(RuntimeError,'检测到动画'):
                bpy.ops.previs.import_scene(filepath=str(source),scene_name=source_scene,snapshot=False)
            bpy.ops.previs.import_scene(filepath=str(source),scene_name=source_scene,snapshot=True,frame=13)
            scene=bpy.context.scene
            meshes=[o for o in scene.objects if o.type=='MESH']
            self.assertEqual(len(meshes),1)
            self.assertAlmostEqual(meshes[0].location.x,1.7,places=5)
            self.assertFalse(runtime.animation_sources(scene))
            with self.assertRaisesRegex(ValueError,'覆盖原始'):runtime.save_project(scene,str(source))
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(),digest)

    def test_persistence_all_metadata(self):
        actor=self.root();assign_nodes(actor,[Node((0,0,0)),Node((.6,0,0),1,.25,True)])
        actor.previs.smooth=True;actor.previs.orientation='PATH'
        cam=self.camera();bpy.ops.previs.camera_mode()
        with edit_batch():
            cam.previs.target.previs.follow=actor
            cam.previs.target.previs.offset=(0,0,1)
            cam.previs.roll_enabled=True;cam.previs.roll=.12
            key=cam.previs.lenses.add();key.time=0;key.value=42
        name=actor.name;camera_name=cam.name
        with tempfile.TemporaryDirectory(prefix='.reload_test_',dir=ROOT) as tmp:
            path=str(Path(tmp)/'project.blend');runtime.save_project(self.scene,path)
            bpy.ops.wm.open_mainfile(filepath=path)
            scene=bpy.context.scene;actor=scene.objects[name];cam=scene.objects[camera_name]
            self.assertEqual(actor.previs.nodes[1].dwell,.25)
            self.assertTrue(actor.previs.nodes[1].exact)
            self.assertEqual(actor.previs.orientation,'PATH')
            self.assertTrue(actor.previs.smooth)
            self.assertEqual(cam.previs.target.previs.follow,actor)
            self.assertAlmostEqual(cam.previs.roll,.12,places=5)
            self.assertEqual(cam.previs.lenses[0].value,42)

suite=unittest.defaultTestLoader.loadTestsFromTestCase(BlenderTests)
result=unittest.TextTestRunner(verbosity=2).run(suite)
ai_previs.unregister()
if not result.wasSuccessful():raise SystemExit(1)
print('BLENDER_INTEGRATION_PASS',flush=True)
