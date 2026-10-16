"""Build a fully local, editable ink duel animatic. Run with Blender --background.

No network, model API, or external asset dependency. Every frame is baked so
scrubbing and rendering use the same choreography. Output is deliberately an
animation study, not finished hand-drawn character animation.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Quaternion

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'renders' / 'blender-duel'
FPS = 24
random.seed(30)


def material(name, color):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*color, 1)
    if name=='Sumi black':m.use_backface_culling=True
    m.use_nodes=True
    ns=m.node_tree.nodes;ns.clear();links=m.node_tree.links
    out=ns.new('ShaderNodeOutputMaterial')
    emit=ns.new('ShaderNodeEmission')
    links.new(emit.outputs[0],out.inputs['Surface'])
    emit.inputs['Color'].default_value=(*color,1)
    if name in ('Old hanji skin','Dry ink midtone'):
        diffuse=ns.new('ShaderNodeBsdfDiffuse')
        diffuse.inputs['Color'].default_value=(.8,.8,.8,1)
        rgb=ns.new('ShaderNodeShaderToRGB');links.new(diffuse.outputs[0],rgb.inputs[0])
        ramp=ns.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='CONSTANT'
        ramp.color_ramp.elements[0].position=.18
        ramp.color_ramp.elements[0].color=(.025,.022,.018,1)
        ramp.color_ramp.elements[1].position=.48
        ramp.color_ramp.elements[1].color=(*color,1)
        links.new(rgb.outputs[0],ramp.inputs[0]);links.new(ramp.outputs[0],emit.inputs[0])
    return m


def mesh(name, verts, faces, mat):
    data = bpy.data.meshes.new(name)
    data.from_pydata(verts, [], faces)
    data.update()
    ob = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    return ob


def curve(name, pts, width, mat, parent=None):
    data = bpy.data.curves.new(name, 'CURVE')
    data.dimensions = '3D'
    data.resolution_u = 1
    data.bevel_depth = width
    data.bevel_resolution = 0
    sp = data.splines.new('POLY')
    sp.points.add(len(pts)-1)
    for p, xyz in zip(sp.points, pts):
        p.co = (*xyz, 1)
    ob = bpy.data.objects.new(name, data)
    bpy.context.collection.objects.link(ob)
    ob.data.materials.append(mat)
    ob.parent = parent
    return ob


def tapered(name, length, rx0, ry0, rx1, ry1, mat, sides=8):
    vs = []
    for z, rx, ry in [(0, rx0, ry0), (length, rx1, ry1)]:
        for i in range(sides):
            a = 2*math.pi*i/sides
            vs.append((math.cos(a)*rx, math.sin(a)*ry, z))
    fs = [tuple(range(sides-1, -1, -1)), tuple(range(sides, sides*2))]
    fs += [(i,(i+1)%sides,(i+1)%sides+sides,i+sides) for i in range(sides)]
    return mesh(name, vs, fs, mat)


def human_head(name):
    """Extract the CC0 MakeHuman head; no MakeHuman application code is used."""
    points=[];faces=[];group=''
    for line in (ROOT/'assets'/'blender'/'makehuman-base.obj').read_text().splitlines():
        a=line.split()
        if not a:continue
        if a[0]=='v':points.append(tuple(map(float,a[1:4])))
        elif a[0]=='g':group=a[1]
        elif a[0]=='f' and group=='body':
            f=[int(x.split('/')[0])-1 for x in a[1:]]
            if all(points[i][1]>5.95 for i in f):faces.append(f)
    used=sorted({i for f in faces for i in f}); remap={n:i for i,n in enumerate(used)}
    for filename,amount in [('asian-male-young.target',1.0),('male-lean.target',.7)]:
        for line in (ROOT/'assets'/'blender'/filename).read_text().splitlines():
            a=line.split()
            if len(a)==4 and not a[0].startswith('#'):
                n=int(a[0]);points[n]=tuple(points[n][j]+float(a[j+1])*amount for j in range(3))
    pts=[(points[i][0]*.145,-points[i][2]*.145,(points[i][1]-7.0)*.145) for i in used]
    ob=mesh(name,pts,[tuple(remap[i] for i in f) for f in faces],SKIN)
    ob.data.materials.append(INK)
    for poly in ob.data.polygons:
        c=poly.center
        zs=[ob.data.vertices[i].co.z for i in poly.vertices]
        ys=[ob.data.vertices[i].co.y for i in poly.vertices]
        if min(zs)>.105 or (min(zs)>.06 and min(ys)>-.09):poly.material_index=1
    for poly in ob.data.polygons:poly.use_smooth=True
    sub=ob.modifiers.new('Human facial anatomy','SUBSURF');sub.levels=1
    return ob


def sleeve(name, mat, fore=False):
    # Multiple rings produce a weighted fabric sleeve instead of joint blocks.
    rings=[(0,.105,.09),(.15,.12,.10),(.5,.13,.11),(.83,.10,.09),(1,.060,.05)] if fore else [(0,.115,.10),(.25,.125,.105),(.65,.13,.11),(1,.12,.105)]
    vs=[];sides=16
    for z,rx,ry in rings:
        for i in range(sides):
            a=math.tau*i/sides
            fold=1+.07*math.cos(a*5+z*9)
            vs.append((rx*math.cos(a)*fold,ry*math.sin(a)*fold,z))
    fs=[tuple(range(sides-1,-1,-1)),tuple(range((len(rings)-1)*sides,len(rings)*sides))]
    fs += [(j*sides+i,j*sides+(i+1)%sides,(j+1)*sides+(i+1)%sides,(j+1)*sides+i) for j in range(len(rings)-1) for i in range(sides)]
    ob=mesh(name,vs,fs,mat)
    for poly in ob.data.polygons:poly.use_smooth=True
    return ob


def key(ob, frame):
    ob.keyframe_insert('location', frame=frame)
    ob.keyframe_insert('rotation_quaternion', frame=frame)
    ob.keyframe_insert('scale', frame=frame)


def segment(ob, a, b, frame, rest=1):
    a, b = Vector(a), Vector(b)
    ob.location = a
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (b-a).to_track_quat('Z', 'Y')
    ob.scale = (1,1,(b-a).length/rest)
    key(ob, frame)


def place(ob, p, frame, angle=0):
    ob.location = p
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = Vector((0,0,1)).rotation_difference(Vector((math.sin(angle),0,math.cos(angle))))
    key(ob, frame)


def elbow(a, b, l1, l2, pole):
    a,b,pole = Vector(a),Vector(b),Vector(pole)
    delta=b-a
    d=max(.001,min(delta.length,l1+l2-.005))
    u=delta.normalized()
    side=pole-u*pole.dot(u)
    side.normalize()
    c=(l1*l1-l2*l2+d*d)/(2*d)
    h=math.sqrt(max(.0001,l1*l1-c*c))
    return a+u*c+side*h


class Fighter:
    def __init__(self, name, hero):
        self.name,self.hero=name,hero
        bodymat=INK if hero else WASH
        self.body=tapered(name+' robe torso',.55,.17,.12,.23,.145,bodymat,24)
        # Fine seams and exposed lapels remain attached to the articulated torso.
        curve(name+' collar left',[(-.17,-.17,.51),(.10,-.18,.17),(.05,-.16,.03)],.008,PAPER,self.body)
        curve(name+' collar right',[(.15,-.17,.51),(-.06,-.18,.27)],.005,INK if not hero else PAPER,self.body)
        for i in range(13):
            x=random.uniform(-.21,.21)
            curve(name+' torso hatch',[(x,-.165,.04),(x+.035,-.173,.17)],.0025,PAPER if hero else INK,self.body)
        self.hips=tapered(name+' sash',.10,.265,.16,.265,.16,INK)
        self.skirts=[]
        for i in range(12):
            a=math.tau*i/12
            da=.27
            vs=[]
            for z,r in [(0,0),(-.20,.25),(-.43,.65),(-.63,1)]:
                rx=.23+.13*r;ry=.16+.11*r
                for aa in (a-da,a,a+da):
                    vs.append((rx*math.cos(aa),ry*math.sin(aa),z+(.02*math.sin(i*4) if r==1 else 0)))
            s=mesh(name+' split robe panel '+str(i),vs,[(j*3+n,j*3+n+1,(j+1)*3+n+1,(j+1)*3+n) for j in range(3) for n in range(2)],bodymat)
            curve(name+' robe edge',[vs[0],vs[3],vs[6],vs[9]],.0025,INK if not hero else PAPER,s)
            self.skirts.append(s)
        self.limbs={}
        for side in ('L','R'):
            self.limbs[side+'thigh']=tapered(name+side+' trouser upper',1,.13,.13,.12,.12,bodymat)
            self.limbs[side+'shin']=tapered(name+side+' trouser lower',1,.11,.11,.07,.07,bodymat)
            self.limbs[side+'upper']=sleeve(name+side+' sleeve upper',bodymat)
            self.limbs[side+'fore']=sleeve(name+side+' sleeve lower',bodymat,True)
            self.limbs[side+'hand']=tapered(name+side+' hand',1,.045,.035,.035,.028,PAPER)
            self.limbs[side+'foot']=tapered(name+side+' sandal',.26,.065,.045,.095,.045,INK)
            for limb in ('upper','fore','thigh','shin'):
                ob=self.limbs[side+limb]
                for j in range(4):
                    x=(j-1.5)*.035
                    curve(name+' garment fold',[(x,-.151,.15),(x+.025,-.155,.75)],.0027,PAPER if hero else INK,ob)
        self.head=human_head(name+' anatomical head')
        if hero:self.head.data.materials[0]=INK
        self.neck=tapered(name+' neck',.18,.07,.075,.07,.075,SKIN,16)
        from mathutils.bvhtree import BVHTree
        bvh=BVHTree.FromPolygons([v.co.copy() for v in self.head.data.vertices],[list(p.vertices) for p in self.head.data.polygons])
        def skin_line(label,pts,width):
            pp=[]
            for x,z in pts:
                hit=bvh.ray_cast(Vector((x,-1,z)),Vector((0,1,0)))[0]
                if hit is not None:pp.append((hit.x,hit.y-.0015,hit.z))
            if len(pp)>1:curve(name+label,pp,width,INK,self.head)
        for sign in (-1,1):
            skin_line(' heavy brow',[(sign*.020,.027),(sign*.035,.034),(sign*.055,.039),(sign*.073,.034)],.0028)
            skin_line(' upper eyelid',[(sign*.023,.004),(sign*.039,.009),(sign*.056,.010),(sign*.068,.005)],.0015)
            skin_line(' nose bridge',[(sign*.017,-.005),(sign*.020,-.030),(sign*.027,-.047)],.0008)
            for j in range(6):
                x=sign*(.062+j*.003)
                skin_line(' cheek etching',[(x,-.040-j*.001),(x+sign*.004,-.055-j*.001)],.0004)
        hair=tapered(name+' tied topknot',.045,.045,.045,.035,.035,INK,24)
        hair.parent=self.head
        hair.location=(0,-.025,.145)
        if hero:
            hat=tapered(name+' satgat',.18,.39,.39,.04,.04,PAPER,48)
            hat.parent=self.head
            hat.location.z=.005
            for i in range(40):
                a=math.tau*i/40
                curve(name+' hat straw',[(.045*math.cos(a),.045*math.sin(a),.187),(.38*math.cos(a),.38*math.sin(a),.007)],.0012,INK,self.head)
            # A dark under-brim masks eyes and nose in every view.
            shade=tapered(name+' hat shadow',.008,.385,.385,.385,.385,INK,48)
            shade.parent=self.head
            shade.location.z=-.004
            curve(name+' hat cord',[(-.14,-.10,.12),(-.09,-.15,-.24),(.13,-.10,.12)],.005,INK,self.head)
        self.sword=bpy.data.objects.new(name+' sword control',None)
        bpy.context.collection.objects.link(self.sword)
        blade=mesh(name+' long single edged blade',[(-.018,0,.05),(.018,0,.05),(.014,0,1.03),(-.005,0,1.12),(-.014,0,.98),(-.018,.012,.05),(.018,.012,.05),(.014,.012,1.03),(-.005,.012,1.12),(-.014,.012,.98)],[(0,1,2,3,4),(5,9,8,7,6),(0,5,6,1),(1,6,7,2),(2,7,8,3),(3,8,9,4),(4,9,5,0)],INK)
        blade.parent=self.sword
        curve(name+' blade bright edge',[(.019,-.002,.06),(.015,-.002,1.02),(-.005,-.002,1.12)],.003,PAPER,self.sword)
        handle=tapered(name+' sword handle',.25,.023,.023,.023,.023,INK)
        handle.parent=self.sword
        handle.location.z=-.25
        guard=tapered(name+' small guard',.015,.075,.045,.075,.045,INK,12)
        guard.parent=self.sword
        for j in range(8):
            curve(name+' grip wrap',[(-.023,-.025,-.025-j*.027),(.023,-.025,-.05-j*.027)],.003,PAPER,self.sword)

    def pose(self,p,frame):
        x,y,z,lean,lf,rf,grip,direction=p
        hip=Vector((x,y,z))
        chest=hip+Vector((lean,0,.53))
        yaw=1.02 if self.hero else -1.02
        twist=Quaternion((0,0,1),yaw)
        segment(self.body,hip,chest,frame,.55)
        self.body.rotation_quaternion=self.body.rotation_quaternion @ twist
        key(self.body,frame)
        place(self.hips,hip-Vector((0,0,.04)),frame)
        self.hips.rotation_quaternion=twist;key(self.hips,frame)
        for i,s in enumerate(self.skirts):
            s.location=hip
            s.rotation_mode='QUATERNION'
            # Cloth lags behind the torso; its weight remains below the belt.
            s.rotation_quaternion=Vector((0,0,1)).rotation_difference(Vector((-lean*.45,0,1)).normalized()) @ twist
            key(s,frame)
        head=chest+Vector((lean*.20,0,.25))
        place(self.head,head,frame,-lean*.3)
        self.head.rotation_quaternion=self.head.rotation_quaternion @ twist
        key(self.head,frame)
        place(self.neck,chest+Vector((lean*.1,0,.02)),frame)
        d=Vector(direction).normalized()
        g=Vector(grip)
        segment(self.sword,g,g+d,frame)
        shoulders={'L':chest+twist @ Vector((-.19,0,-.03)),'R':chest+twist @ Vector((.19,0,-.03))}
        for side,foot,sideval,offset in [('L',lf,-1,-.17),('R',rf,1,-.055)]:
            ankle=Vector(foot)+Vector((0,0,.07))
            thigh=hip+Vector((sideval*.13,0,-.04))
            knee=elbow(thigh,ankle,.45,.46,(sideval*.45,-.8,.1))
            segment(self.limbs[side+'thigh'],thigh,knee,frame)
            segment(self.limbs[side+'shin'],knee,ankle,frame)
            footob=self.limbs[side+'foot']
            segment(footob,Vector(foot)+Vector((-.10,-.10,.035)),Vector(foot)+Vector((.16,-.10,.035)),frame,.26)
            wrist=g+d*offset
            shoulder=shoulders[side]
            e=elbow(shoulder,wrist,.34,.34,(sideval*.25,-1,-.4))
            segment(self.limbs[side+'upper'],shoulder,e,frame)
            segment(self.limbs[side+'fore'],e,wrist,frame)
            segment(self.limbs[side+'hand'],wrist,g+d*(offset+.08),frame)


def pose(x, z, lean, feet, grip, direction, y=0):
    return (x,y,z,lean,feet[0],feet[1],grip,direction)


def mix(a,b,u):
    if isinstance(a,(tuple,list)):
        return tuple(mix(x,y,u) for x,y in zip(a,b))
    return a+(b-a)*u


def sample(keys,t):
    for i in range(len(keys)-1):
        ta,pa=keys[i];tb,pb=keys[i+1]
        if ta<=t<=tb:
            # Linear baked action preserves fast directional changes and avoids
            # Bezier overshoot at blade contact or planted feet.
            return mix(pa,pb,(t-ta)/(tb-ta))
    return keys[0][1] if t<keys[0][0] else keys[-1][1]


def build():
    global INK,PAPER,WASH,SKIN
    bpy.ops.object.select_all(action='SELECT')
    bpy.ops.object.delete(use_global=False)
    INK=material('Sumi black',(.014,.012,.010))
    PAPER=material('Old hanji',(.72,.67,.55))
    SKIN=material('Old hanji skin',(.72,.67,.55))
    WASH=material('Dry ink midtone',(.28,.26,.22))
    PALE=material('Distant dry brush',(.49,.46,.38))
    s=bpy.context.scene
    s.render.engine='BLENDER_EEVEE_NEXT'
    s.eevee.taa_render_samples=32
    s.render.use_freestyle=False
    s.render.line_thickness=.85
    linestyle=s.view_layers[0].freestyle_settings.linesets[0].linestyle
    linestyle.color=(.014,.012,.010)
    linestyle.thickness=.85
    s.render.resolution_x=960;s.render.resolution_y=540;s.render.resolution_percentage=100
    s.render.fps=FPS;s.frame_start=1;s.frame_end=528
    s.render.image_settings.file_format='PNG'
    s.render.film_transparent=False
    sh=s.display.shading
    sh.light='STUDIO';sh.color_type='MATERIAL';sh.show_shadows=False
    sh.studiolight_rotate_z=.6
    sh.show_cavity=True;sh.cavity_type='WORLD';sh.curvature_ridge_factor=1.3;sh.curvature_valley_factor=1.0
    sh.show_object_outline=True;sh.object_outline_color=(.018,.014,.009)
    sh.background_type='WORLD';s.world.color=(.72,.67,.55)
    s.view_settings.view_transform='Standard'
    s.view_settings.look='None'
    lamp=bpy.data.lights.new('Ink key light','AREA');lamp.energy=700;lamp.size=5
    lampob=bpy.data.objects.new('Ink key light',lamp);bpy.context.collection.objects.link(lampob)
    lampob.location=(-3,-4,7)
    lampob.rotation_euler=(.3,-.5,0)
    s.world.use_nodes=True
    s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.72,.67,.55,1)
    s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.8
    # Sparse ink landscape; no decorative particles cross the action area.
    mesh('hanji ground',[(-90,-90,-.03),(90,-90,-.03),(90,90,-.03),(-90,90,-.03)],[(0,1,2,3)],PAPER)
    for i in range(80):
        x=random.uniform(-18,18);y=random.uniform(3,19)
        z=random.uniform(.25,1.7)
        curve('reed dry stroke',[(x,y,0),(x+.05,y+.04,z*.4),(x+.10,y,z)],.006,PALE)
        if i%2==0:
            curve('reed leaf',[(x+.05,y,z*.4),(x+.25,y,z*.58),(x+.35,y,z*.59)],.008,PALE)
    for i in range(35):
        x=random.uniform(-12,12);y=random.uniform(-3,6)
        curve('earth stroke',[(x,y,.002),(x+random.uniform(.1,.9),y+.04,.002)],.004,PALE)
    for i in range(0):
        y=20+i*8
        curve('distant ridge',[(-40,y,0),(-18,y,2+i),(-8,y,1),(0,y,3+i),(13,y,1),(30,y,4),(45,y,0)],.04,PALE)
    hero=Fighter('Wanderer',True);enemy=Fighter('Opponent',False)
    for ob in list(bpy.context.scene.objects):
        if ob.type=='MESH' and (ob.name.startswith('Wanderer') or ob.name.startswith('Opponent')) and 'blade' not in ob.name and 'guard' not in ob.name and 'hat' not in ob.name:
            ob.data.materials.append(INK)
            outline=ob.modifiers.new('Crisp ink silhouette','SOLIDIFY')
            outline.thickness=.0022;outline.offset=1;outline.use_flip_normals=True
            outline.material_offset=len(ob.data.materials)-1
            outline.material_offset_rim=len(ob.data.materials)-1
    H=[];E=[]
    def k(t,h,e):H.append((t,h));E.append((t,e))
    # Feet are world-space control points. A planted foot retains its position
    # while the pelvis advances; only the explicit step poses lift the foot.
    k(0,pose(-1.5,.96,.10,[(-1.8,-.12,0),(-1.2,.12,0)],(-1.13,0,1.28),(.5,0,.86)),pose(1.65,1.0,-.1,[(1.3,-.12,0),(1.95,.12,0)],(1.25,0,1.46),(-.7,0,.71)))
    k(2.05,H[-1][1],E[-1][1])
    k(2.35,pose(-1.25,.88,.2,[(-1.8,-.12,0),(-.85,.12,.10)],(-.84,0,1.38),(.5,0,.86)),pose(1.12,.90,-.20,[(.55,-.12,.12),(1.95,.12,0)],(.75,.04,1.80),(-.4,0,.92)))
    k(2.60,pose(-.75,.85,.30,[(-1.55,-.12,0),(-.35,.12,0)],(-.28,0,1.40),(.60,0,.80)),pose(.80,.91,-.27,[(.22,-.12,0),(1.50,.12,0)],(.39,.02,1.65),(-.8,-.05,.6)))
    k(2.68,H[-1][1],E[-1][1])
    k(2.92,pose(-.88,.87,.16,[(-1.55,-.12,0),(-.35,.12,0)],(-.48,-.10,1.25),(.78,0,.63)),pose(1.04,.96,.02,[(.22,-.12,0),(1.58,.12,0)],(.63,.16,1.52),(-.5,0,.86)))
    k(3.80,H[-1][1],E[-1][1])
    k(4.12,pose(-.80,.88,.25,[(-1.55,-.12,0),(-.35,.12,0)],(-.28,-.15,1.53),(.91,.05,.42)),pose(.84,.94,-.2,[(.22,-.12,0),(1.58,.12,0)],(.30,-.14,1.95),(-.75,0,-.66)))
    k(4.20,H[-1][1],E[-1][1])
    k(4.40,pose(-.94,.82,.12,[(-1.55,-.12,0),(-.35,.12,0)],(-.49,-.10,1.22),(.9,0,.44)),pose(.90,.93,-.15,[(.22,-.12,0),(1.58,.12,0)],(.39,.02,1.70),(-.7,0,.71)))
    k(5.80,H[-1][1],E[-1][1])
    k(6.20,pose(-1.12,.77,.12,[(-1.65,-.18,0),(-.67,.20,.12)],(-.77,-.40,1.23),(-.55,0,.84),y=-.30),pose(.77,.88,-.3,[(.22,-.12,0),(1.58,.12,0)],(.22,0,2.05),(-.1,0,.99)))
    k(6.42,pose(-.86,.67,.32,[(-1.65,-.55,0),(-.22,-.55,0)],(-.28,-.58,.98),(.85,0,.52),y=-.55),pose(.24,.77,-.42,[(-.35,-.12,0),(1.3,.12,0)],(-.34,.02,1.18),(-.91,0,-.40)))
    k(6.68,pose(-.50,.72,.30,[(-1.3,-.55,0),(.05,-.55,0)],(-.02,-.55,.96),(.8,0,.6),y=-.55),pose(.23,.77,-.38,[(-.35,-.12,0),(1.3,.12,0)],(-.22,.02,.91),(-.91,0,-.4)))
    k(7.25,pose(-.32,.84,.12,[(-.90,-.55,.12),(.05,-.55,0)],(.05,-.43,1.27),(.5,0,.86),y=-.4),pose(.53,.85,.15,[(-.35,-.12,0),(1.3,.12,0)],(.21,.02,1.16),(-.7,0,.71)))
    k(8.10,pose(-.52,.92,.08,[(-.90,-.55,0),(.05,-.55,0)],(-.10,-.40,1.34),(.32,0,.95),y=-.4),pose(.81,.96,.15,[(.35,.10,0),(1.30,.12,0)],(.40,.10,1.36),(-.5,0,.86)))
    k(10.90,H[-1][1],E[-1][1])
    k(11.60,pose(-.58,.80,.20,[(-1.0,-.55,0),(.05,-.55,0)],(-.17,-.4,1.16),(.9,0,.43),y=-.4),pose(.78,.88,-.15,[(.25,.10,0),(1.3,.12,0)],(.35,0,1.91),(-.55,0,.84)))
    k(12.12,pose(-.28,.75,.33,[(-1.0,-.55,0),(.30,-.45,0)],(.24,-.20,1.27),(.65,.10,.75),y=-.3),pose(.69,.83,-.27,[(.10,.1,0),(1.3,.12,0)],(.80,-.18,1.65),(-.9,0,-.44)))
    k(12.20,H[-1][1],E[-1][1])
    k(12.45,pose(-.08,.78,.25,[(-.70,-.55,.1),(.30,-.45,0)],(.41,-.08,1.38),(.65,.08,.75),y=-.3),pose(.86,.89,.25,[(.10,.1,0),(1.3,.12,0)],(.35,.10,1.90),(-.25,.15,.95)))
    k(13.30,pose(-.08,.78,.25,[(-.70,-.55,0),(.30,-.45,0)],(.41,-.08,1.38),(.65,.08,.75),y=-.3),pose(.86,.89,.25,[(.10,.1,0),(1.3,.12,0)],(.35,.10,1.90),(-.25,.15,.95)))
    k(13.55,pose(.15,.76,.32,[(-.70,-.55,0),(.65,-.5,0)],(.63,-.16,1.12),(.55,.05,.83),y=-.4),pose(1.05,.91,.34,[(.1,.1,0),(1.55,.15,.12)],(1.10,-.12,1.83),(-.3,.1,.95)))
    k(13.68,pose(.48,.80,.35,[(-.4,-.55,.12),(.95,-.50,0)],(.85,-.32,1.12),(.9,-.1,.42),y=-.5),pose(1.22,.89,.38,[(.1,.1,0),(1.90,.15,0)],(1.12,-.10,1.90),(-.1,.1,.99)))
    k(14.1,pose(.85,.88,.16,[(.35,-.55,0),(1.35,-.50,.1)],(1.13,-.65,1.1),(.8,0,.6),y=-.6),pose(1.25,.78,.15,[(.7,.1,.12),(1.90,.15,0)],(.94,.06,1.51),(-.5,0,.86)))
    k(14.5,pose(1.10,.91,.10,[(.35,-.55,0),(1.60,-.50,0)],(1.40,-.65,1.04),(.8,0,-.6),y=-.6),E[-1][1])
    k(14.8,pose(1.30,.92,.08,[(.85,-.55,.16),(1.60,-.50,0)],(1.60,-.65,1.03),(.8,0,-.6),y=-.6),E[-1][1])
    k(15.1,pose(1.45,.91,.08,[(1.20,-.55,0),(1.85,-.50,.14)],(1.75,-.65,1.02),(.8,0,-.6),y=-.6),E[-1][1])
    k(15.4,pose(1.60,.92,.08,[(1.2,-.55,0),(1.95,-.50,0)],(1.91,-.63,1.02),(.8,0,-.6),y=-.6),pose(1.20,.66,-.08,[(.7,.1,0),(1.90,.15,0)],(.94,.06,1.35),(-.5,0,.86)))
    k(17.1,pose(2.15,.95,.03,[(1.8,-.55,0),(2.45,-.50,0)],(2.43,-.63,.95),(.8,0,-.6),y=-.6),pose(1.20,.66,-.08,[(.7,.1,0),(1.90,.15,0)],(.94,.06,1.35),(-.5,0,.86)))
    k(21.96,H[-1][1],E[-1][1])
    # Camera cuts share one continuous world and one pair of animated actors.
    cameras=[]
    def cam(name,start,loc,target,lens=42,endloc=None,endtarget=None):
        data=bpy.data.cameras.new(name);data.lens=lens
        ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob)
        ob.rotation_mode='QUATERNION'
        def ck(t,p,q):
            ob.location=p;ob.rotation_quaternion=(Vector(q)-Vector(p)).to_track_quat('-Z','Y');key(ob,round(t*FPS)+1)
        ck(start,loc,target)
        marker=s.timeline_markers.new(name,frame=round(start*FPS)+1);marker.camera=ob
        cameras.append(ob)
        return ob,ck
    cam('01 stillness',0,(-3.4,-6.3,1.45),(.1,0,1.05),43)
    cam('02 beside hero weapon',2.0,(-1.65,-1.5,1.63),(.42,.04,1.48),25)
    cam('03 hands and blades',4.0,(-.35,-1.48,1.60),(.08,0,1.65),38)
    cam('04 whole ground',5.8,(.1,-6.7,2.7),(.0,0,1.0),39)
    ob,ck=cam('05 opponent reads the opening',9.5,(-.10,-1.22,1.89),(.89,.08,1.75),58)
    ck(11.5,(-.06,-1.18,1.85),(.91,.08,1.73))
    cam('06 reverse over opponent',11.6,(.50,1.50,1.65),(-.10,-.30,1.22),31)
    cam('07 crossing the line',13.3,(.5,-4.4,1.0),(1.0,-.2,1.0),35)
    cam('08 aftermath',17.1,(4.6,-5.0,1.18),(1.2,-.1,.98),45)
    s.camera=cameras[0]
    # Disarmed sword is animated independently after the wrist strip.
    for frame in range(1,s.frame_end+1):
        t=(frame-1)/FPS
        hp=sample(H,t);ep=sample(E,t)
        hero.pose(hp,frame);enemy.pose(ep,frame)
        if 2<=t<4:
            eye=Vector(hp[6])+Vector((.18,-.95,-.08))
            target=Vector((ep[0],ep[1],ep[2]+.54))
            cameras[1].location=eye
            cameras[1].rotation_quaternion=(target-eye).to_track_quat('-Z','Y')
            key(cameras[1],frame)
        if t>=13.68:
            u=min(1,(t-13.68)/.70)
            g=Vector((1.12,-.10,1.90)).lerp(Vector((2.4,1.1,.04)),u)
            g.z+=.8*math.sin(math.pi*u)
            angle=u*math.pi*2.25
            d=Vector((math.sin(angle),.15,math.cos(angle))) if u<1 else Vector((.8,.6,.015))
            segment(enemy.sword,g,g+d.normalized(),frame)
    for action in bpy.data.actions:
        # Blender 4.5 exposes legacy fcurves for object actions as well.
        try:
            for fc in action.fcurves:
                for kp in fc.keyframe_points:kp.interpolation='LINEAR'
        except AttributeError:
            pass
    s['project_status']='LOCAL CHOREOGRAPHY STUDY - procedural actors, not finished character art'
    s['music_source_start_seconds']=168
    s['contact_frames']='63-65, 100-102, 292-294; disarm 329'
    # Frozen procedural fibre texture. Static seed avoids grain flickering.
    s.use_nodes=True
    cn=s.node_tree.nodes;cn.clear();cl=s.node_tree.links
    rl=cn.new('CompositorNodeRLayers')
    tex=bpy.data.images.new('Frozen hanji fibre',width=960,height=540)
    rr=random.Random(730);pixels=[]
    for yy in range(540):
        for xx in range(960):
            edge=((xx-480)/560)**2+((yy-270)/400)**2
            value=.985-rr.random()*.045-.045*edge+.008*math.sin(yy*2.31)
            pixels.extend((value,value,value,1))
    tex.pixels.foreach_set(pixels);tex.pack()
    node=cn.new('CompositorNodeImage');node.image=tex
    mult=cn.new('CompositorNodeMixRGB');mult.blend_type='MULTIPLY';mult.inputs[0].default_value=1
    cl.new(rl.outputs['Image'],mult.inputs[1]);cl.new(node.outputs[0],mult.inputs[2])
    comp=cn.new('CompositorNodeComposite');cl.new(mult.outputs[0],comp.inputs[0])
    # Put the supplied soundtrack in the editable scene as well as final MP4.
    audio=ROOT/'assets'/'audio'/'bakkuo-168-190.wav'
    if audio.exists():
        ed=s.sequence_editor_create()
        ed.strips.new_sound('Gloomy30s - user provided song excerpt',str(audio),channel=1,frame_start=1)
    for area in bpy.context.screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.region_3d.view_perspective='CAMERA'
    s.frame_set(64)
    OUT.mkdir(parents=True,exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bakkuo-ink-duel.blend'))
    (OUT/'choreography.json').write_text(json.dumps({'fps':FPS,'frames':528,'duration':22,'song':[168,190],'hero_keys':H,'opponent_keys':E,'status':'procedural choreography study'},ensure_ascii=False,indent=2),encoding='utf-8')
    return s


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--preview',action='store_true')
    p.add_argument('--preview-frames',default='25,63,101,157,247,293,330,444')
    p.add_argument('--render',action='store_true')
    p.add_argument('--start',type=int,default=1)
    p.add_argument('--end',type=int,default=528)
    p.add_argument('--ranges',default='')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    s=build()
    if args.preview:
        for f in map(int,args.preview_frames.split(',')):
            s.frame_set(f);s.render.filepath=str(OUT/f'preview-{f:04d}.png');bpy.ops.render.render(write_still=True)
    if args.render:
        (OUT/'frames').mkdir(exist_ok=True)
        s.render.filepath=str(OUT/'frames'/'frame-')
        ranges=[tuple(map(int,r.split(':'))) for r in args.ranges.split(',')] if args.ranges else [(args.start,args.end)]
        for start,end in ranges:
            if not 1<=start<=end<=528:raise ValueError('Render range outside the 528-frame scene')
            s.frame_start=start;s.frame_end=end
            s.frame_set(start)
            bpy.ops.render.render(animation=True)


if __name__=='__main__':main()
