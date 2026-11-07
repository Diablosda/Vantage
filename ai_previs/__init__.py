bl_info = {
    'name': 'AI Previs Studio',
    'author': 'Camera Control',
    'version': (0,1,0),
    'blender': (5,2,2),
    'location': '3D View > Sidebar > 预演',
    'description': '本地白模调度、正交路径、摄影机 C/T 控制与 MP4 输出',
    'category': 'Animation',
}

from . import properties, runtime, operators, ui, timeline

def register():
    properties.register();runtime.register();operators.register();ui.register();timeline.register()

def unregister():
    timeline.unregister();ui.unregister();operators.unregister();runtime.unregister();properties.unregister()
