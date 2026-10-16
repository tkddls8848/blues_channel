import bpy,numpy as np
from pathlib import Path
r=Path(r'C:/Users/tkddl/orca/blues_channel/flows')
s=bpy.context.scene
for ob in s.objects:
 if ob.type=='GREASEPENCIL':
  who='hero' if ob.name.startswith('Hero') else 'enemy' if ob.name.startswith('Opponent / animated') else None
  if who:
   raw=np.load(r/'assets'/'gp-animation'/f'{who}-vectors.npz');p=raw['points']
   pos=np.column_stack([(p[:,0]-836)*.0024,np.zeros(len(p)),(941-p[:,1])*.0024]).astype('f')
   ob.data.layers[0].frames[0].drawing.attributes['position'].data.foreach_set('vector',pos.ravel())
  else:ob.hide_render=True
s.frame_set(1)
s.camera.location=(0,-10,1.1)
s.camera.data.ortho_scale=4.2
s.render.filepath=str(r/'renders'/'gp-animation'/'trace-qa.png')
bpy.ops.render.render(write_still=True)
