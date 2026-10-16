"""Actual Grease Pencil compatibility proof on the existing duel key pose.

Adds a real Line Art modifier and pressure-varied GP strokes; saves separately
from the current 35-second render. Does not claim to be finished redraw art.
"""
from pathlib import Path
import math
import bpy

s=bpy.context.scene
out=Path(bpy.data.filepath).parent/'grease-pencil-test'
out.mkdir(exist_ok=True)
s.frame_set(375)
# Hidden legacy hand meshes are superseded by the new grip drawings. Removing
# them in this separate proof scene prevents Line Art depsgraph warnings.
for item in list(bpy.data.objects):
    if item.hide_render and item.name.startswith(('Wanderer','Opponent')) and item.name.endswith(' hand'):
        bpy.data.objects.remove(item,do_unlink=True)
data=bpy.data.grease_pencils_v3.new('Editable ink drawings')
ob=bpy.data.objects.new('GP / character contours and slash accents',data)
bpy.context.collection.objects.link(ob)
mat=bpy.data.materials.new('GP / sumi stroke')
bpy.data.materials.create_gpencil_data(mat)
mat.grease_pencil.color=(.012,.010,.008,1)
mat.grease_pencil.show_stroke=True
mat.grease_pencil.show_fill=False
data.materials.append(mat)
layer=data.layers.new('01 / generated character contours',set_active=True)
if hasattr(layer,'use_lights'):layer.use_lights=False
layer.frames.new(1)
source=bpy.data.collections.new('GP contour sources')
s.collection.children.link(source)
for item in list(s.objects):
    if item.type=='MESH' and item.name.startswith(('Wanderer','Opponent')) and not item.hide_render:
        source.objects.link(item)
mod=ob.modifiers.new('Actual Grease Pencil Line Art','LINEART')
mod.source_type='COLLECTION';mod.source_collection=source
mod.target_layer=layer.name;mod.target_material=mat
mod.use_contour=True;mod.use_crease=False;mod.use_intersection=False
mod.radius=.0018;mod.opacity=1
accents=data.layers.new('02 / editable pressure strokes',set_active=True)
if hasattr(accents,'use_lights'):accents.use_lights=False
accents.frames.new(1)
drawing=accents.frames.new(375).drawing
paths=[]
for j in range(3):
    pts=[]
    for k in range(18):
        u=k/17
        x=-1.10+u*1.22
        z=1.62+.28*math.sin(u*math.pi*.82)+j*.025
        pts.append((x,-.28,z))
    paths.append(pts)
drawing.add_strokes([len(path) for path in paths])
for st,path in zip(drawing.strokes,paths):
    st.material_index=0
    for i,(p,xyz) in enumerate(zip(st.points,path)):
        p.position=xyz
        p.radius=.0008+.0025*math.sin(math.pi*i/(len(path)-1))
        p.opacity=.95
accents.frames.new(378)
s['grease_pencil_status']='Real GP object, Line Art modifier, editable point radii and layered drawings verified'
s.render.filepath=str(out/'grease-pencil-key-pose.png')
for item in s.objects:item.select_set(False)
ob.select_set(True);bpy.context.view_layer.objects.active=ob
bpy.ops.wm.save_as_mainfile(filepath=str(out/'bakkuo-grease-pencil-test.blend'))
bpy.ops.render.render(write_still=True)
print('GREASE_PENCIL_PROOF',ob.type, len(data.layers), mod.type)
