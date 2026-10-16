"""35-second locally rendered revision: references define design and pose targets.

Blender invocation: --background --python blender_duel_v2.py -- --preview
The image is a reference only; no reference footage is inserted in the render.
"""
import argparse
import json
import math
import random
import sys
from pathlib import Path

import bpy
from mathutils import Vector, Quaternion
from mathutils.bvhtree import BVHTree

sys.path.insert(0,str(Path(__file__).parent))
import blender_duel as core

OUT=core.ROOT/'renders'/'blender-duel-v2'
BASE_FIGHTER=core.Fighter
BASE_BUILD=core.build
BASE_SAMPLE=core.sample
ACTORS=[]
POSE_CACHE={}
DELAY=312


def stroke_bundle(name, strokes, width, material, parent):
    d=bpy.data.curves.new(name,'CURVE');d.dimensions='3D'
    d.bevel_depth=width;d.bevel_resolution=0;d.resolution_u=1
    for pts in strokes:
        sp=d.splines.new('POLY');sp.points.add(len(pts)-1)
        for p,v in zip(sp.points,pts):p.co=(*v,1)
    ob=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(ob)
    ob.data.materials.append(material);ob.parent=parent
    return ob


def patch_pose_keys(keys):
    hero=keys[0][1][0]<0
    replacements={
        2.35:core.pose(-1.14,.78,.30,[(-1.76,-.12,0),(-.64,.14,.12)],(-.68,-.03,1.28),(.28,0,.96)),
        2.60:core.pose(-.68,.66,.42,[(-1.45,-.12,0),(.10,.15,0)],(.06,-.03,1.35),(.68,0,.73)),
        2.68:core.pose(-.68,.66,.42,[(-1.45,-.12,0),(.10,.15,0)],(.06,-.03,1.35),(.68,0,.73)),
        2.92:core.pose(-.77,.73,.28,[(-1.45,-.12,0),(.10,.15,0)],(-.22,-.08,1.18),(.88,0,.47)),
        3.80:core.pose(-.77,.73,.28,[(-1.45,-.12,0),(.10,.15,0)],(-.22,-.08,1.18),(.88,0,.47)),
        4.12:core.pose(-.60,.68,.42,[(-1.39,-.12,0),(.12,.15,0)],(.10,-.12,1.40),(.90,0,.44)),
        4.20:core.pose(-.60,.68,.42,[(-1.39,-.12,0),(.12,.15,0)],(.10,-.12,1.40),(.90,0,.44)),
        6.42:core.pose(-.70,.55,.43,[(-1.35,-.55,0),(.30,-.55,0)],(.04,-.57,1.00),(.85,0,.52),y=-.55),
        6.68:core.pose(-.45,.62,.35,[(-1.10,-.55,0),(.28,-.55,0)],(.10,-.55,1.03),(.80,0,.60),y=-.55),
        12.12:core.pose(-.18,.60,.42,[(-.90,-.55,0),(.48,-.45,0)],(.32,-.22,1.25),(.65,.10,.75),y=-.30),
        12.20:core.pose(-.18,.60,.42,[(-.90,-.55,0),(.48,-.45,0)],(.32,-.22,1.25),(.65,.10,.75),y=-.30),
        13.55:core.pose(.25,.63,.45,[(-.50,-.55,0),(.88,-.50,0)],(.72,-.16,1.25),(.53,.05,.85),y=-.40),
        13.68:core.pose(.60,.70,.40,[(-.10,-.55,.10),(1.22,-.50,0)],(1.02,-.32,1.18),(.90,-.10,.42),y=-.50),
    } if hero else {
        2.60:core.pose(.95,.90,-.22,[(.35,-.12,0),(1.62,.12,0)],(.70,-.03,1.55),(-.8,0,.60)),
        2.68:core.pose(.95,.90,-.22,[(.35,-.12,0),(1.62,.12,0)],(.70,-.03,1.55),(-.8,0,.60)),
        4.12:core.pose(.93,.88,-.24,[(.30,-.12,0),(1.63,.12,0)],(.65,-.12,1.90),(-.70,0,-.71)),
        4.20:core.pose(.93,.88,-.24,[(.30,-.12,0),(1.63,.12,0)],(.65,-.12,1.90),(-.70,0,-.71)),
        13.55:core.pose(1.13,.88,.30,[(.55,.10,0),(1.83,.15,0)],(1.13,-.12,1.90),(-.30,.10,.95)),
        13.68:core.pose(1.32,.82,.44,[(.55,.10,0),(1.95,.15,0)],(1.20,-.10,1.94),(-.10,.10,.99)),
    }
    fixed=[]
    for t,p in keys:
        p=list(replacements.get(t,p))
        if hero:
            if t in (0,2.05):p[2]=.95
            if t in (2.92,3.80):p[0]=-.67;p[2]=.69
            if t==6.42:p[5]=(.15,-.55,0)
            if t in (4.12,4.20):p[4]=(-1.37,-.12,0)
            if t in (8.10,10.90):p[2]=.84
            if t==14.5:p[2]=.86;p[4]=(.60,-.55,.08)
        else:
            if t in (0,2.05):p[2]=.94
            if t==2.35:p[5]=(1.70,.12,.10)
            if t in (2.60,2.68,4.12,4.20):p[2]=.83;p[4]=(.35,-.12,0);p[5]=(1.55,.12,0)
            if t in (4.12,4.20):p[6]=(.65,-.12,1.76)
            if t in (2.92,3.80):p[2]=.85;p[4]=(.50,-.12,0)
            if t in (4.40,5.80):p[2]=.83;p[4]=(.30,-.12,0);p[5]=(1.50,.12,0)
            if t==6.20:p[2]=.87;p[5]=(1.30,.12,0);p[6]=(.22,0,1.96)
            if t in (6.42,6.68):p[5]=(.92,.12,0)
            if t==7.25:p[4]=(0,-.12,0);p[5]=(1.1,.12,0)
            if t in (8.10,10.90):p[2]=.89;p[6]=(.53,.05,1.38)
            if t in (12.12,12.20):p[6]=(.60,-.18,1.50);p[7]=(-.95,0,-.31)
            if t in (12.45,13.30):p[2]=.86;p[4]=(.30,.10,0);p[6]=(.82,0,1.73)
            if t==13.55:p[2]=.84;p[5]=(1.72,.15,0);p[6]=(1.13,-.12,1.83)
            if t==13.68:p[2]=.79;p[3]=.20;p[4]=(.65,.10,0);p[6]=(1.35,-.10,1.78)
        fixed.append((t,tuple(p)))
    return fixed


def sample(keys,t):
    ident=id(keys)
    if ident not in POSE_CACHE:POSE_CACHE[ident]=patch_pose_keys(keys)
    return BASE_SAMPLE(POSE_CACHE[ident],t)


class DetailedFighter(BASE_FIGHTER):
    def __init__(self,name,hero):
        super().__init__(name,hero)
        ACTORS.append(self)
        rr=random.Random(83 if hero else 91)
        # Remove the old marks that floated beyond the narrower sleeve surface.
        for ob in list(bpy.data.objects):
            if ob.name.startswith(name) and ('garment fold' in ob.name or 'torso hatch' in ob.name):
                bpy.data.objects.remove(ob,do_unlink=True)
        self.robe_rest=[[(v.co.x,v.co.y,v.co.z) for v in s.data.vertices] for s in self.skirts]
        self.prev_hip=None
        self.trails=[]
        for side in ('L','R'):
            self.limbs[side+'hand'].hide_render=True
            for limb in ('upper','fore','thigh','shin'):
                ob=self.limbs[side+limb]
                marks=[]
                radius=.108 if limb in ('fore','upper') else .103
                for j in range(22):
                    ang=-math.pi/2+rr.uniform(-.55,.55)
                    a=rr.uniform(.10,.80);b=min(.95,a+rr.uniform(.05,.26))
                    marks.append([(radius*math.cos(ang),radius*math.sin(ang)-.002,a),(radius*math.cos(ang+.08),radius*math.sin(ang+.08)-.002,b)])
                stroke_bundle(name+side+limb+' fine dry folds',marks,.0010,core.PAPER if hero else core.INK,ob)
            # Flat sole, narrow foot straps, and a heel replace the block shoe.
            old=self.limbs[side+'foot']
            data=old.data
            vs=[(xx,yy,zz) for zz,w in [(0,.045),(.08,.055),(.22,.063),(.27,.053)] for xx,yy in [(-.022,-w),(.022,-w),(.022,w),(-.022,w)]]
            fs=[(0,3,2,1),(12,13,14,15)]+[(j*4+i,j*4+(i+1)%4,(j+1)*4+(i+1)%4,(j+1)*4+i) for j in range(3) for i in range(4)]
            data.clear_geometry();data.from_pydata(vs,[],fs);data.update()
            core.curve(name+side+' sandal straps',[(-.027,-.058,.18),(-.04,0,.21),(-.027,.058,.18)],.005,core.PAPER,old)
            # Two gripping hands have four fingers each, attached to the hilt.
            for zc in ((-.19,) if side=='L' else (-.065,)):
                palm=core.tapered(name+side+' wrapped palm',.072,.034,.023,.034,.023,core.SKIN,12)
                palm.parent=self.sword;palm.location=(0,-.032,zc-.036)
                for j in range(4):
                    z=zc-.029+j*.019
                    pts=[]
                    for k in range(7):
                        a=-math.pi*.70+k*math.pi*1.55/6
                        pts.append((math.cos(a)*.031,math.sin(a)*.030,z))
                    core.curve(name+' curled finger',pts,.0075,core.SKIN,self.sword)
        self.replace_sword()
        self.hand_rig=bpy.data.objects.new(name+' hands independent from released sword',None)
        bpy.context.collection.objects.link(self.hand_rig)
        for ob in list(self.sword.children):
            if 'wrapped palm' in ob.name or 'curled finger' in ob.name:ob.parent=self.hand_rig
        if hero:
            self.add_trailing_cloth(rr)
        else:
            # The existing opponent has dark fitted clothing below the armour.
            for ob in list(bpy.data.objects):
                if ob.type=='MESH' and ob.name.startswith(name) and ('sleeve' in ob.name or 'trouser' in ob.name or 'robe panel' in ob.name):
                    ob.data.materials[0]=core.INK
            self.add_armour(rr)
            self.add_helmet()
            self.add_face_detail(rr)

    def replace_sword(self):
        for ob in list(self.sword.children):
            if 'long single edged blade' in ob.name or 'blade bright edge' in ob.name:
                bpy.data.objects.remove(ob,do_unlink=True)
        verts=[]
        # 130 cm cutting length, 25 mm base width, 3 mm thickness, slight curve.
        for y in (-.0015,.0015):
            for z,w in [(0,.0125),(.6,.0105),(1.15,.007),(1.30,0)]:
                center=.026*(z/1.3)**2
                verts.extend([(center-w,y,z),(center+w,y,z)])
        fs=[]
        for j in range(3):
            fs.extend([(j*2,j*2+1,j*2+3,j*2+2),(8+j*2,10+j*2,11+j*2,9+j*2)])
            fs.extend([(j*2,j*2+2,10+j*2,8+j*2),(j*2+1,9+j*2,11+j*2,j*2+3)])
        blade=core.mesh(self.name+' 130cm slim blade',verts,fs,core.INK);blade.parent=self.sword
        core.curve(self.name+' razor spine',[(-.0125,-.002,0),(-.005,-.002,.6),(.013,-.002,1.15),(.026,-.002,1.30)],.0018,core.INK,self.sword)
        core.curve(self.name+' razor edge',[(.0125,-.002,0),(.016,-.002,.6),(.027,-.002,1.15),(.026,-.002,1.30)],.0011,core.INK,self.sword)
        core.curve(self.name+' bright cutting edge',[(.009,-.003,0),(.013,-.003,.6),(.024,-.003,1.15),(.026,-.003,1.30)],.0015,core.PAPER,self.sword)

    def add_trailing_cloth(self,rr):
        for j in range(11):
            # Long narrow strips start behind the shoulder instead of forming
            # a circular skirt around both knees.
            w=rr.uniform(.045,.10);length=rr.uniform(.55,1.1)
            pts=[(-w,-.02,0),(w,-.02,0),(w*.8,.22,-length*.3),(w*.5,.48,-length*.6),(0,.62,-length),(-w*.7,.52,-length*.77),(-w,.25,-length*.35)]
            ob=core.mesh(self.name+' torn mantle '+str(j),pts,[(0,1,2,3,4,5,6)],core.INK)
            self.trails.append((ob,j,w,length))
            core.curve(self.name+' frayed mantle edge',[pts[0],pts[-1],pts[-2],pts[4]],.0015,core.PAPER,ob)
            hatch=[]
            for k in range(8):
                x=rr.uniform(-w*.7,w*.7);z=rr.uniform(-length*.5,-.02)
                hatch.append([(x,.11,z),(x+.012,.16,z-.12)])
            stroke_bundle(self.name+' mantle bristles',hatch,.0012,core.PAPER,ob)

    def add_armour(self,rr):
        for row in range(6):
            z=.055+row*.071
            for j in range(10):
                a=math.tau*j/10
                width=.046
                # Elliptical breast armour follows the torso and leaves the
                # collar open, as in the existing opponent reference.
                x=.188*math.cos(a);y=.145*math.sin(a)
                tang=Vector((-math.sin(a),math.cos(a),0))*width
                c=Vector((x,y,z))
                vs=[c-tang,c+tang,c+tang+Vector((0,0,.065)),c-tang+Vector((0,0,.065))]
                ob=core.mesh(self.name+' lamellar plate',vs,[(0,1,2,3)],core.INK);ob.parent=self.body
                core.curve(self.name+' plate incised rim',[vs[0],vs[1],vs[2]],.0011,core.PAPER,ob)
                if j in (6,7,8,9):
                    core.curve(self.name+' plate lacing',[(x-.012,y-.004,z+.02),(x+.012,y-.004,z+.048)],.0017,core.PAPER,self.body)
        for side in ('L','R'):
            ob=self.limbs[side+'upper']
            for j in range(4):
                z=.05+j*.11
                pts=[(-.105,-.106,z),(-.05,-.129,z+.012),(.05,-.129,z+.012),(.105,-.106,z)]
                core.curve(self.name+' shoulder armour rim',pts,.0035,core.INK,ob)

    def add_helmet(self):
        vs=[];fs=[];rings=7;sides=32
        for j in range(rings):
            a=(j/(rings-1))*math.pi/2
            r=.148*math.cos(a)
            for i in range(sides):
                b=math.tau*i/sides
                vs.append((math.cos(b)*r,-.025+math.sin(b)*r,.074+math.sin(a)*.145))
        for j in range(rings-1):
            for i in range(sides):fs.append((j*sides+i,j*sides+(i+1)%sides,(j+1)*sides+(i+1)%sides,(j+1)*sides+i))
        helm=core.mesh(self.name+' narrow open iron helmet',vs,fs,core.INK);helm.parent=self.head
        band=core.tapered(self.name+' fitted forehead band',.038,.15,.15,.15,.15,core.INK,32)
        band.parent=self.head;band.location=(0,-.025,.038)
        brim=core.mesh(self.name+' low helmet visor',[(-.145,-.12,.044),(.145,-.12,.044),(.125,-.205,.035),(-.125,-.205,.035)],[(0,1,2,3)],core.INK)
        brim.parent=self.head
        rim=[]
        for i in range(41):
            a=math.tau*i/40
            rim.append((math.cos(a)*.151,-.025+math.sin(a)*.151,.071))
        core.curve(self.name+' helmet lower rim',rim,.005,core.PAPER,self.head)
        for i in range(12):
            a=math.tau*i/12
            points=[]
            for j in range(8):
                b=j/7*math.pi/2;r=.150*math.cos(b)
                points.append((r*math.cos(a),-.025+r*math.sin(a),.076+.145*math.sin(b)))
            core.curve(self.name+' helmet etched rib',points,.0018,core.PAPER,self.head)
        for side in (-1,1):
            for j in range(3):
                z=.04-j*.035
                pts=[(side*.14,.02,z),(side*.14,.11,z-.01),(side*.06,.14,z-.01)]
                plate=core.mesh(self.name+' joined neck guard',[pts[0],pts[1],pts[2],(side*.06,.14,z-.042),(side*.14,.11,z-.032),(side*.14,.02,z-.032)],[(0,1,2,3,4,5)],core.INK)
                plate.parent=self.head
                core.curve(self.name+' neck guard lip',pts,.0012,core.PAPER,self.head)
        hair=[]
        for side in (-1,1):
            for j in range(7):
                x=side*(.10+j*.004)
                hair.append([(x,.02,.035),(x+side*.008,.055,-.07),(x+side*.015,.07,-.21),(x+side*.025,.12,-.29-(j%3)*.025)])
        stroke_bundle(self.name+' loose long hair',hair,.0045,core.INK,self.head)

    def add_face_detail(self,rr):
        bvh=BVHTree.FromPolygons([v.co.copy() for v in self.head.data.vertices],[list(p.vertices) for p in self.head.data.polygons])
        marks=[]
        for j in range(170):
            x=rr.uniform(-.084,.084);z=rr.uniform(-.13,-.05)
            if abs(x)<.026 and z>-.105:continue
            pts=[]
            for xx,zz in [(x,z),(x+rr.uniform(-.002,.002),z-.005)]:
                hit=bvh.ray_cast(Vector((xx,-1,zz)),Vector((0,1,0)))[0]
                if hit:pts.append((hit.x,hit.y-.002,hit.z))
            if len(pts)==2:marks.append(pts)
        stroke_bundle(self.name+' short beard etching',marks,.0006,core.INK,self.head)
        for side in (-1,1):
            # Pupils add a definite gaze to the otherwise empty base mesh eyes.
            bpy.ops.mesh.primitive_uv_sphere_add(segments=12,ring_count=6,radius=.005,location=(0,0,0))
            pupil=bpy.context.object;pupil.name=self.name+' focused pupil'
            pupil.data.materials.append(core.INK);pupil.parent=self.head
            pupil.location=(side*.043,-.184,.003);pupil.scale=(.7,.5,.6)

    def pose(self,p,frame):
        x,y,z,lean,lf,rf,grip,direction=p
        t=(frame-1)/24
        hip=Vector((x,y,z));chest=hip+Vector((lean,0,.53))
        # A small counterrotation separates pelvis, shoulders, and gaze.
        drive=max(-.5,min(.5,(grip[0]-x)*.5-.16))
        yaw=(1.02 if self.hero else -1.02)+(drive if self.hero else -drive)
        twist=Quaternion((0,0,1),yaw)
        core.segment(self.body,hip,chest,frame,.55)
        self.body.rotation_quaternion=self.body.rotation_quaternion@twist;core.key(self.body,frame)
        self.hips.location=hip-Vector((0,0,.04));self.hips.rotation_mode='QUATERNION'
        self.hips.rotation_quaternion=Quaternion((0,0,1),yaw*.7);core.key(self.hips,frame)
        head=chest+Vector((lean*.12,0,.22))
        core.place(self.head,head,frame,-lean*.25)
        self.head.rotation_quaternion=self.head.rotation_quaternion@Quaternion((0,0,1),1.10 if self.hero else -1.10)
        core.key(self.head,frame)
        core.place(self.neck,chest,frame)
        d=Vector(direction).normalized();g=Vector(grip)
        core.segment(self.sword,g,g+d,frame)
        core.segment(self.hand_rig,g,g+d,frame)
        for i,ob in enumerate(self.skirts):
            a=math.tau*i/12
            flare=.16+abs(lean)*.75
            ob.location=hip;ob.rotation_mode='QUATERNION'
            ob.rotation_quaternion=Quaternion((0,0,1),yaw*.7)@Quaternion((math.cos(a),math.sin(a),0),flare)
            ob.scale.z=min(1,max(.35,(z-.07)/.63));core.key(ob,frame)
        for ob,j,w,length in self.trails:
            ob.location=chest+Vector((-.1 if self.hero else .1,.07,-.02-j*.025))
            ob.rotation_mode='QUATERNION'
            wind=.08*math.sin(t*3.0-j*.55)+lean*.55
            ob.rotation_quaternion=Quaternion((0,0,1),-.9+j*.06)@Quaternion((1,0,0),-.5-wind)
            core.key(ob,frame)
        for side,foot,sv,off in [('L',lf,-1,-.19),('R',rf,1,-.065)]:
            foot=Vector(foot);ankle=foot+Vector((0,0,.05))
            thigh=hip+Vector((sv*.11,0,-.03))
            knee=core.elbow(thigh,ankle,.45,.46,(.65 if self.hero else -.65,-.5,.1))
            core.segment(self.limbs[side+'thigh'],thigh,knee,frame)
            core.segment(self.limbs[side+'shin'],knee,ankle,frame)
            core.segment(self.limbs[side+'foot'],foot+Vector((-.10,0,.025)),foot+Vector((.16,0,.025)),frame,.27)
            shoulder=chest+twist@Vector((sv*.19,0,-.025))
            wrist=g+d*off
            e=core.elbow(shoulder,wrist,.34,.34,(sv*.2,-1,-.3))
            core.segment(self.limbs[side+'upper'],shoulder,e,frame)
            core.segment(self.limbs[side+'fore'],e,wrist,frame)


def camera_pose(ob,frame,position,target,roll=0,lens=None):
    ob.location=position
    ob.rotation_mode='QUATERNION'
    ob.rotation_quaternion=(Vector(target)-Vector(position)).to_track_quat('-Z','Y')@Quaternion((0,0,1),roll)
    if lens:ob.data.lens=lens
    core.key(ob,frame)


def build():
    scene=BASE_BUILD()
    # Crisp outer contours remain solid. Only the garment fill receives short
    # object-space dry-brush marks, so ink does not dissolve during motion.
    dry=core.INK.copy();dry.name='Dry brush garment fill'
    ns=dry.node_tree.nodes;links=dry.node_tree.links
    tex=ns.new('ShaderNodeTexCoord');stretch=ns.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY'
    stretch.inputs[1].default_value=(13,13,1)
    links.new(tex.outputs['Generated'],stretch.inputs[0])
    noise=ns.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=6;noise.inputs['Detail'].default_value=2
    links.new(stretch.outputs[0],noise.inputs['Vector'])
    ramp=ns.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='CONSTANT'
    ramp.color_ramp.elements[0].position=.53;ramp.color_ramp.elements[0].color=(.014,.012,.010,1)
    ramp.color_ramp.elements[1].position=.67;ramp.color_ramp.elements[1].color=(.39,.35,.28,1)
    links.new(noise.outputs['Fac'],ramp.inputs[0]);links.new(ramp.outputs[0],next(n for n in ns if n.type=='EMISSION').inputs['Color'])
    for ob in bpy.data.objects:
        if ob.type=='MESH' and any(v in ob.name for v in ('sleeve','trouser','robe torso','robe panel','torn mantle')):
            ob.data.materials[0]=dry
        if ob.parent and 'anatomical head' in ob.parent.name and ('helmet' in ob.name or 'forehead band' in ob.name):
            ob.location.y-=.04
    base_data=json.loads((OUT/'choreography.json').read_text(encoding='utf-8'))
    H=patch_pose_keys(base_data['hero_keys']);E=patch_pose_keys(base_data['opponent_keys'])
    # All baked actions, including the disarmed weapon, move by 13 seconds.
    for act in bpy.data.actions:
        for fc in act.fcurves:
            for kp in fc.keyframe_points:
                kp.co.x+=DELAY;kp.handle_left.x+=DELAY;kp.handle_right.x+=DELAY
    for marker in scene.timeline_markers:marker.frame+=DELAY
    hero,enemy=ACTORS
    for f in range(1,DELAY+49):
        t=(f-1)/24
        h=list(H[0][1]);e=list(E[0][1])
        # Only respiration and a restrained cloth flutter in the quiet section.
        h[2]+=.006*math.sin(t*1.5);e[2]+=.004*math.sin(t*1.3)
        h[6]=(-1.15,-.02,1.06);h[7]=(.8,0,-.6)
        e[6]=(1.25,.02,1.22);e[7]=(-.8,0,-.6)
        if f>DELAY:
            u=(f-DELAY)/49
            h=core.mix(h,H[0][1],u)
            e=core.mix(e,E[0][1],u)
        hero.pose(h,f);enemy.pose(e,f)
    scene.frame_end=840
    # Replace the quiet section's old camera and add a measured insert rhythm.
    for marker in list(scene.timeline_markers):
        if marker.frame==DELAY+1:scene.timeline_markers.remove(marker)
    def add_cam(name,time,pos,target,lens):
        data=bpy.data.cameras.new(name);data.lens=lens
        ob=bpy.data.objects.new(name,data);bpy.context.collection.objects.link(ob)
        camera_pose(ob,round(time*24)+1,pos,target)
        m=scene.timeline_markers.new(name,frame=round(time*24)+1);m.camera=ob
        return ob
    c0=add_cam('00 quiet / the road',0,(-3.8,-8.4,1.15),(.1,0,.9),43)
    camera_pose(c0,120,(-3.5,-8.0,1.15),(.1,0,.9))
    add_cam('00 quiet / the hand',5,(-1.8,-1.15,1.20),(-1.15,-.02,1.00),55)
    add_cam('00 quiet / beneath the hat',9,(-2.4,-1.9,1.57),(-1.32,0,1.58),60)
    add_cam('00 quiet / the distance',12.8,(.1,-6.6,.85),(.1,0,1.00),42)
    cameras={ob.name:ob for ob in bpy.data.objects if ob.type=='CAMERA'}
    low=cameras['02 beside hero weapon'];low.animation_data_clear();low.data.lens=30
    close=cameras['03 hands and blades'];close.animation_data_clear();close.data.lens=28
    wide=cameras['04 whole ground'];wide.animation_data_clear();wide.data.lens=34
    end=cameras['07 crossing the line'];end.animation_data_clear();end.data.lens=34
    for f in range(DELAY+1,841):
        t=(f-DELAY-1)/24
        h=BASE_SAMPLE(H,t);e=BASE_SAMPLE(E,t)
        if 2<=t<4:
            camera_pose(low,f,(-1.75,-3.8,.48),(.12,0,1.16),math.radians(-7))
        if 4<=t<5.8:
            g=Vector(h[6]);camera_pose(close,f,g+Vector((-.15,-.85,.06)),(.48,-.08,1.66),math.radians(5))
        if 5.8<=t<9.5:
            u=(t-5.8)/3.7
            camera_pose(wide,f,(-1.8+u*1.4,-5.5,.72+u*.35),(.15,-.25,.95),math.radians(-4))
        if 13.3<=t<17.1:
            u=(t-13.3)/3.8
            camera_pose(end,f,(.15+u*.5,-4.8,.55),(1.1,-.25,1.02),math.radians(4))
        if t>=13.68:
            u=min(1,(t-13.68)/.70)
            g=Vector((1.35,-.10,1.78)).lerp(Vector((2.4,1.1,.04)),u)
            g.z+=.8*math.sin(math.pi*u)
            angle=u*math.pi*2.25
            d=Vector((math.sin(angle),.15,math.cos(angle))) if u<1 else Vector((.8,.6,.015))
            core.segment(enemy.sword,g,g+d.normalized(),f)
    # Held original poses are retained for the short calm immediately preceding
    # the first step; actual combat starts at output t=15.05 / song 2:50.05.
    ed=scene.sequence_editor
    if ed:
        for strip in list(ed.strips):ed.strips.remove(strip)
    else:ed=scene.sequence_editor_create()
    audio=core.ROOT/'assets'/'audio'/'bakkuo-155-190.wav'
    ed.strips.new_sound('User song 2m35s to 3m10s',str(audio),channel=1,frame_start=1)
    scene['music_source_start_seconds']=155
    scene['project_status']='35-second pose and design revision; procedural 3D, not finished manga art'
    scene['blade_dimensions']='1.30m cutting length, 25mm base width, 3mm thickness'
    scene['contact_frames']='375-377, 412-414, 604-606; release 642'
    scene['references']='Previous video character designs + supplied crouched crossed-blade action image'
    # Keep the key pose immediately visible when opening the project.
    scene.frame_set(375)
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'bakkuo-ink-duel-v2.blend'))
    (OUT/'choreography.json').write_text(json.dumps({'fps':24,'frames':840,'duration':35,'song':[155,190],'combat_starts':15.05,'blade_length_m':1.30,'blade_width_m':.025,'hero_keys':H,'opponent_keys':E,'animation_shift_frames':DELAY,'status':'procedural design and choreography revision'},ensure_ascii=False,indent=2),encoding='utf-8')
    return scene


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--preview',action='store_true')
    p.add_argument('--render',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    core.OUT=OUT;core.Fighter=DetailedFighter;core.sample=sample
    OUT.mkdir(parents=True,exist_ok=True)
    s=build()
    if args.preview:
        for f in (49,157,265,375,413,469,559,605,642,756):
            s.frame_set(f);s.render.filepath=str(OUT/f'preview-{f:04d}.png');bpy.ops.render.render(write_still=True)
    if args.render:
        (OUT/'frames').mkdir(exist_ok=True)
        s.frame_start=1;s.frame_end=840;s.render.filepath=str(OUT/'frames'/'frame-')
        bpy.ops.render.render(animation=True)


if __name__=='__main__':main()
