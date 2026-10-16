import bpy,json
from pathlib import Path
p=Path(bpy.data.filepath).parent
report={'gp':{},'armatures':[]}
for ob in bpy.context.scene.objects:
 if ob.type=='GREASEPENCIL':report['gp'][ob.name]=sum(len(l.frames) for l in ob.data.layers)
 if ob.type=='ARMATURE':report['armatures'].append({'name':ob.name,'bones':len(ob.data.bones)})
report['frames']=bpy.context.scene.frame_end
(p/'scene-audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
mp=p/'animation-manifest.json'
m=json.loads(mp.read_text());m.pop('total_character_point_positions',None)
m['technique']='Illustrated cutout armatures plus animated native GP ink and weapons'
m['verified_actor_gp_drawings']={n:v for n,v in report['gp'].items() if n.startswith(('Hero /','Opponent / animated'))}
mp.write_text(json.dumps(m,indent=2),encoding='utf-8')
print(json.dumps(report))
