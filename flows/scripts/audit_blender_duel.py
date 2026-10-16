"""Audit baked limb lengths in the currently loaded Blender scene."""
import json
from pathlib import Path
import bpy

scene=bpy.context.scene
out=Path(bpy.data.filepath).parent
objects=[]
for ob in bpy.data.objects:
    if ob.name.startswith(('Wanderer','Opponent')):
        if ob.name.endswith('trouser lower'):objects.append((ob,.46))
        if ob.name.endswith('sleeve lower'):objects.append((ob,.34))
values={ob.name:[] for ob,_ in objects}
for f in range(1,scene.frame_end+1):
    scene.frame_set(f)
    for ob,expected in objects:values[ob.name].append((float(ob.scale.z),f))
report=[]
for ob,expected in objects:
    length,frame=max(values[ob.name])
    report.append({'object':ob.name,'expected_m':expected,'max_m':length,'max_at_frame':frame,'extra_m':max(0,length-expected)})
result={'scene':Path(bpy.data.filepath).name,'frames':scene.frame_end,'limbs':report,'max_extra_m':max(row['extra_m'] for row in report)}
result['tolerance_m']=.012
result['status']='passed' if result['max_extra_m']<=result['tolerance_m'] else 'failed'
(out/'limb-audit.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
print(json.dumps(result))
if result['status']=='failed':raise RuntimeError('A baked limb exceeds the allowed reach tolerance')
