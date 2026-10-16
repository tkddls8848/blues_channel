"""Native Grease Pencil character animation, with existing illustrated art.

Actual redraws at 12 drawings/sec, bone-space deformation of ink polygons,
explicit weapon swings/contact/recoil, and an editable 35-second Blender file.
No generative services and no 3D mannequin character renders are used.
"""
import argparse
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector, Quaternion, Matrix

ROOT=Path(__file__).resolve().parents[1]
ART=ROOT/'assets'/'gp-animation'
OUT=ROOT/'renders'/'gp-animation'
FPS=24


def mix(a,b,u):
    if isinstance(a,(list,tuple)):return tuple(mix(x,y,u) for x,y in zip(a,b))
    return a+(b-a)*u


def state(x,z,lean,feet,grip,angle,free=None):
    return (x,z,lean,feet[0],feet[1],grip,math.radians(angle),free or (x+.3,z+.28))


def choreography():
    H=[];E=[]
    def key(t,h,e):H.append((t,h));E.append((t,e))
    h0=state(-1.25,.89,.08,[(-1.55,.03),(-.95,.03)],(-.86,1.10),-38)
    e0=state(1.28,.90,-.05,[(.98,.03),(1.58,.03)],(.94,1.23),214,(1.55,1.18))
    key(0,h0,e0);key(13.8,h0,e0)
    key(14.85,state(-1.25,.83,.15,[(-1.55,.03),(-.95,.03)],(-.86,1.28),60),state(1.28,.86,-.08,[(.98,.03),(1.58,.03)],(.95,1.50),105,(1.40,1.27)))
    key(15.04,H[-1][1],E[-1][1])
    key(15.26,state(-1.02,.75,.24,[(-1.55,.03),(-.61,.14)],(-.55,1.24),72),state(.88,.78,-.20,[(.30,.14),(1.45,.03)],(.58,1.83),80,(.81,1.42)))
    key(15.50,state(-.61,.62,.38,[(-1.34,.03),(.10,.03)],(.01,1.29),52),state(.77,.77,-.18,[(.21,.03),(1.32,.03)],(.46,1.56),143,(.57,1.25)))
    key(15.58,H[-1][1],E[-1][1])
    key(15.83,state(-.69,.66,.27,[(-1.34,.03),(.10,.03)],(-.14,1.23),34),state(.95,.80,.07,[(.21,.03),(1.47,.07)],(.49,1.43),116,(.91,1.2)))
    key(16.50,state(-.63,.69,.20,[(-1.23,.06),(.10,.03)],(-.13,1.30),61),state(.96,.85,-.02,[(.40,.07),(1.47,.03)],(.55,1.39),139,(1.14,1.19)))
    key(17.05,H[-1][1],E[-1][1])
    key(17.25,state(-.53,.62,.33,[(-1.23,.03),(.14,.03)],(.08,1.30),35),state(.80,.80,-.18,[(.26,.03),(1.37,.03)],(.46,1.70),225,(.77,1.3)))
    key(17.33,H[-1][1],E[-1][1])
    key(17.60,state(-.68,.63,.20,[(-1.23,.03),(.14,.03)],(-.17,1.17),8),state(.90,.81,.01,[(.26,.03),(1.42,.03)],(.46,1.44),137,(1.12,1.12)))
    key(18.00,H[-1][1],E[-1][1])
    key(18.18,state(-.83,.57,.16,[(-1.36,.03),(-.13,.10)],(-.36,1.17),-5),state(.54,.73,-.26,[(.03,.03),(1.14,.03)],(.03,1.21),178,(.42,1.17)))
    key(18.46,state(-.86,.52,.36,[(-1.36,.03),(-.13,.03)],(-.25,.95),24),state(.43,.72,-.25,[(.03,.03),(1.11,.03)],(-.02,1.16),194,(.47,1.17)))
    key(18.85,state(-.73,.59,.29,[(-1.36,.03),(-.01,.03)],(-.18,1.12),63),state(.63,.76,.03,[(.03,.03),(1.19,.03)],(.23,1.26),135,(.87,1.12)))
    key(19.25,H[-1][1],E[-1][1])
    key(19.55,state(-.55,.54,.34,[(-1.18,.03),(.16,.03)],(.06,.98),-12),state(.55,.78,-.22,[(.03,.03),(1.19,.03)],(.23,1.77),72,(.60,1.25)))
    key(19.78,state(-.29,.52,.36,[(-.94,.12),(.36,.03)],(.25,1.04),35),state(.26,.68,-.25,[(-.25,.03),(.93,.03)],(-.12,1.02),205,(.31,1.08)))
    key(20.12,state(-.15,.60,.25,[(-.79,.03),(.36,.03)],(.28,1.12),58),state(.36,.73,.03,[(-.25,.03),(.93,.03)],(.06,1.21),153,(.58,1.18)))
    key(20.50,state(-.02,.64,.20,[(-.61,.08),(.52,.03)],(.37,1.25),25),state(.63,.79,.20,[(.05,.11),(1.17,.03)],(.24,1.45),177,(.97,1.25)))
    key(20.58,H[-1][1],E[-1][1])
    key(20.88,state(-.18,.66,.14,[(-.61,.03),(.52,.03)],(.18,1.17),-25),state(.82,.82,.15,[(.25,.03),(1.37,.03)],(.38,1.39),146,(1.09,1.14)))
    key(21.55,state(-.36,.74,.06,[(-.80,.03),(.12,.03)],(.04,1.28),52),state(.94,.86,.03,[(.45,.03),(1.44,.03)],(.53,1.31),138,(1.18,1.15)))
    key(23.45,H[-1][1],E[-1][1])
    key(23.70,state(-.28,.63,.26,[(-.89,.03),(.31,.10)],(.19,1.17),8),state(.91,.81,-.14,[(.38,.03),(1.44,.03)],(.47,1.73),98,(.82,1.39)))
    key(24.03,state(-.04,.56,.34,[(-.72,.03),(.55,.03)],(.49,1.18),58),state(.71,.75,-.18,[(.19,.03),(1.32,.03)],(.40,1.52),217,(.72,1.22)))
    key(24.11,H[-1][1],E[-1][1])
    key(24.37,state(.04,.60,.25,[(-.58,.03),(.61,.03)],(.53,1.35),62),state(.92,.80,.22,[(.32,.03),(1.50,.03)],(.70,1.66),110,(1.18,1.13)))
    key(25.10,H[-1][1],E[-1][1])
    key(25.38,state(.20,.56,.33,[(-.44,.03),(.80,.03)],(.70,1.19),-8),state(1.13,.77,.28,[(.54,.03),(1.70,.08)],(.90,1.58),124,(1.38,1.16)))
    key(25.72,state(.38,.61,.24,[(-.24,.10),(.91,.03)],(.82,1.22),54),state(1.25,.81,.22,[(.66,.03),(1.80,.03)],(1.06,1.55),128,(1.46,1.18)))
    key(26.25,H[-1][1],E[-1][1])
    key(26.49,state(.50,.56,.34,[(-.12,.03),(1.13,.03)],(1.00,1.24),52),state(1.27,.77,.12,[(.67,.03),(1.86,.03)],(1.12,1.50),153,(1.53,1.15)))
    key(26.58,H[-1][1],E[-1][1])
    key(26.80,state(.77,.66,.26,[(.18,.12),(1.32,.03)],(1.13,1.14),-7),state(1.43,.70,.29,[(.83,.03),(2.03,.03)],(1.28,1.59),96,(1.73,1.18)))
    key(27.15,state(1.06,.76,.16,[(.53,.03),(1.54,.10)],(1.43,1.10),-34),state(1.46,.65,.13,[(.85,.03),(2.04,.03)],(1.19,1.21),165,(1.72,1.02)))
    key(27.60,state(1.34,.81,.10,[(.86,.10),(1.82,.03)],(1.68,1.02),-31),state(1.42,.60,-.05,[(.85,.03),(2.04,.03)],(1.10,1.06),182,(1.67,.94)))
    key(28.05,state(1.66,.84,.06,[(1.20,.03),(2.05,.10)],(1.98,1.02),-31),E[-1][1])
    key(28.60,state(1.98,.86,.02,[(1.57,.10),(2.34,.03)],(2.30,1.00),-33),E[-1][1])
    key(29.20,state(2.20,.88,.00,[(1.87,.03),(2.51,.03)],(2.50,1.00),-34),E[-1][1])
    key(35,H[-1][1],E[-1][1])
    return H,E


def sample(keys,t):
    for (a,p),(b,q) in zip(keys,keys[1:]):
        if a<=t<=b:return mix(p,q,(t-a)/(b-a))
    return keys[-1][1]


def joint(a,b,l1,l2,side):
    a=np.asarray(a);b=np.asarray(b);d=b-a;dist=np.linalg.norm(d)
    u=d/max(dist,.00001);r=min(dist,l1+l2-.001)
    along=(l1*l1-l2*l2+r*r)/(2*max(r,.0001));h=math.sqrt(max(0,l1*l1-along*along))
    return a+u*along+np.array([-u[1],u[0]])*h*side


def skeleton(p,hero,t):
    x,z,lean,fl,fr,g,angle,free=p
    hip=np.array([x,z]);chest=hip+np.array([lean,.47])
    breath=.003*math.sin(t*2)
    chest[1]+=breath
    head=chest+np.array([.045 if hero else -.025,.20])
    d=np.array([math.cos(angle),math.sin(angle)])
    joints={'hip':hip,'chest':chest,'head':head}
    for s,foot in [('l',fl),('r',fr)]:
        offset=-.07 if s=='l' else .07
        thigh=hip+np.array([offset,-.025]);ankle=np.array(foot)
        joints['ankle_'+s]=ankle
        joints['knee_'+s]=joint(thigh,ankle,.45,.45,1 if hero else -1)
        shoulder=chest+np.array([-.075 if s=='l' else .065,-.005 if s=='l' else -.035])
        wrist=np.array(g)-d*(.17 if s=='l' else .055)
        if not hero and s=='r':wrist=np.array(free)
        joints['shoulder_'+s]=shoulder
        joints['wrist_'+s]=wrist
        joints['elbow_'+s]=joint(shoulder,wrist,.31,.31,-1 if hero else 1)
    return joints


BONES=[('hip','chest'),('chest','head'),('hip','knee_l'),('knee_l','ankle_l'),('hip','knee_r'),('knee_r','ankle_r'),('shoulder_l','elbow_l'),('elbow_l','wrist_l'),('shoulder_r','elbow_r'),('elbow_r','wrist_r')]


def gp_material(name,color,fill=True,width=1):
    m=bpy.data.materials.new(name);bpy.data.materials.create_gpencil_data(m)
    m.grease_pencil.show_fill=fill;m.grease_pencil.show_stroke=not fill
    m.grease_pencil.fill_color=(*color,1);m.grease_pencil.color=(*color,1)
    return m


def gp_object(name,palette):
    d=bpy.data.grease_pencils_v3.new(name)
    d.stroke_depth_order='2D'
    ob=bpy.data.objects.new(name,d);bpy.context.collection.objects.link(ob)
    for m in palette:d.materials.append(m)
    layer=d.layers.new('Animated ink drawings',set_active=True);layer.use_lights=False
    return ob,layer


def add_drawing(layer,frame,points,lengths,mats,cyclic=True):
    dr=layer.frames.new(frame).drawing
    dr.add_strokes(lengths.tolist())
    dr.attributes['position'].data.foreach_set('vector',np.asarray(points,dtype=np.float32).ravel())
    for name,typ,values in [('material_index','INT',mats),('cyclic','BOOLEAN',np.full(len(lengths),cyclic))]:
        at=dr.attributes.get(name) or dr.attributes.new(name,typ,'CURVE')
        at.data.foreach_set('value',values)
    return dr


class InkActor:
    def __init__(self,name,spec,palette):
        self.hero=name=='hero'
        raw=np.load(ART/f'{name}-vectors.npz')
        self.points=raw['points'];self.lengths=raw['lengths'];self.mats=raw['materials']
        self.render_indices=np.arange(len(self.points));self.draw_lengths=self.lengths;self.draw_mats=self.mats
        self.ob,self.layer=gp_object('Hero / animated illustrated ink' if self.hero else 'Opponent / animated illustrated ink',palette)
        self.bind={k:np.array(v,dtype=np.float32) for k,v in spec['joints'].items()}
        P=self.points
        distances=[];self.axial=[];self.offset=[]
        for aa,bb in BONES:
            a,b=self.bind[aa],self.bind[bb];v=b-a;length=np.linalg.norm(v);u=v/length
            per=np.array([-u[1],u[0]])
            axial=(P-a)@u/length
            nearest=a+np.clip(axial,0,1)[:,None]*v
            distances.append(np.sum((P-nearest)**2,axis=1))
            self.axial.append(axial);self.offset.append((P-a)@per*.00212)
        distances=np.array(distances).T
        order=np.argsort(distances,axis=1)[:,:2]
        weights=1/(distances+180)**2.2
        keep=np.zeros_like(weights);np.put_along_axis(keep,order,1,axis=1)
        weights*=keep;weights/=weights.sum(axis=1)[:,None]
        weights,cape=blend_head_cape(weights,P,self.hero)
        self.weights=weights.astype(np.float32);self.cape=cape
        self.handmask=(P[:,0]<1104)&(P[:,1]>190)&(P[:,1]<305) if not self.hero else np.zeros(len(P),bool)
        # A traced open hand replaces the released sword hand in the aftermath.
        self.open_points=None
        if not self.hero:
            offsets=np.r_[0,np.cumsum(self.lengths)];ind=[];lens=[];mats=[]
            for i,(a,b) in enumerate(zip(offsets,offsets[1:])):
                pp=P[a:b]
                if np.all((pp[:,0]>1577)&(pp[:,1]>421)&(pp[:,1]<516)):
                    ind.extend(range(a,b));lens.append(b-a);mats.append(self.mats[i])
            if ind:
                self.open_points=P[ind]-np.array([1623,477])
                self.open_lengths=np.array(lens,np.int32);self.open_mats=np.array(mats,np.int32)
                self.open_ob,self.open_layer=gp_object('Opponent / released open hand',palette)
                self.open_layer.frames.new(1)

    def draw(self,p,t,frame):
        target=skeleton(p,self.hero,t);result=np.zeros((len(self.points),2),np.float32)
        for i,(aa,bb) in enumerate(BONES):
            a,b=target[aa],target[bb];v=b-a;length=np.linalg.norm(v);u=v/max(length,.00001)
            per=np.array([u[1],-u[0]])
            mapped=a+self.axial[i][:,None]*v+self.offset[i][:,None]*per
            result+=mapped*self.weights[:,i:i+1]
        # Cape motion trails the body's velocity, with very small wind at rest.
        if self.hero:
            amount=np.clip((610-self.points[:,0])/440,0,1)*self.cape
            wind=.018*math.sin(t*2.3)+(.055 if t>=15 else .005)*math.sin(t*6.1)
            result[:,0]-=amount*(.06 if t>=15 else .01)
            result[:,1]+=amount*wind
        else:
            # Gaze tightens during the reaction insert; head and eyebrows move
            # in their own drawing instead of cutting to a stationary still.
            eye=(self.points[:,0]>1340)&(self.points[:,0]<1455)&(self.points[:,1]>180)&(self.points[:,1]<232)
            alert=max(0,min(1,(t-22.0)/.3)) if 22<=t<23.5 else 0
            result[eye,1]-=.003*alert
            if t>=26.80:
                result[self.handmask]=target['wrist_l']
                if self.open_points is not None:
                    open_xy=self.open_points*np.array([-.0013,-.0013])+target['wrist_l']
                    pts=np.column_stack([open_xy[:,0],np.full(len(open_xy),-.045),open_xy[:,1]])
                    add_drawing(self.open_layer,frame,pts,self.open_lengths,self.open_mats)
        pts=np.column_stack([result[:,0],np.full(len(result),-.03 if self.hero else .03),result[:,1]])
        add_drawing(self.layer,frame,pts[self.render_indices],self.draw_lengths,self.draw_mats)
        return target


def image_material(name,path):
    m=bpy.data.materials.new(name);m.use_nodes=True
    ns=m.node_tree.nodes;ns.clear();links=m.node_tree.links
    out=ns.new('ShaderNodeOutputMaterial');em=ns.new('ShaderNodeEmission');tex=ns.new('ShaderNodeTexImage')
    tex.image=bpy.data.images.load(str(path),check_existing=True);tex.image.pack()
    links.new(tex.outputs['Color'],em.inputs['Color']);links.new(em.outputs[0],out.inputs['Surface'])
    return m


def blend_head_cape(weights,P,hero):
    if hero:
        head=np.maximum(np.clip((360-P[:,1])/60,0,1)*np.clip((P[:,0]-645)/55,0,1),((P[:,1]<285)&(P[:,0]>550)).astype(float))
        cape=np.clip((650-P[:,0])/100,0,1)*np.clip((550-P[:,1])/100,0,1)*(1-head)
    else:
        head=np.clip((330-P[:,1])/70,0,1)*np.clip((P[:,0]-1300)/40,0,1)
        cape=np.zeros(len(P))
    weights*=1-cape[:,None];weights[:,0]+=cape
    weights*=1-head[:,None];weights[:,1]+=head
    return weights,cape


class PaintedActor(InkActor):
    """Original paper/ink detail on an actual 2D armature plus animated GP ink.

    Keeping the image texture avoids replacing intricate facial hatching with
    coarse posterized fills. The native GP layer carries the darkest marks.
    """
    def __init__(self,name,spec,palette):
        super().__init__(name,spec,palette)
        surface=np.load(ART/f'{name}-surface.npz')['points']
        pp,first,inverse=np.unique(surface,axis=0,return_index=True,return_inverse=True)
        self.unique_points=pp
        self.first_indices=first
        self.rig=bpy.data.objects.new(name+' / editable 2D armature',bpy.data.armatures.new(name+' skeletal controls'))
        bpy.context.collection.objects.link(self.rig)
        bpy.context.view_layer.objects.active=self.rig;self.rig.select_set(True)
        bpy.ops.object.mode_set(mode='EDIT')
        self.rest_lengths=[]
        def xyz(p):return Vector((float(p[0])*.00212,0,-float(p[1])*.00212))
        for i,(aa,bb) in enumerate(BONES):
            b=self.rig.data.edit_bones.new(str(i));b.head=xyz(self.bind[aa]);b.tail=xyz(self.bind[bb]);b.align_roll(Vector((0,-1,0)))
            self.rest_lengths.append((b.tail-b.head).length)
        if not self.hero:
            b=self.rig.data.edit_bones.new('released grip');b.head=xyz(self.bind['elbow_l']);b.tail=xyz(self.bind['wrist_l']);b.align_roll(Vector((0,-1,0)))
        bpy.ops.object.mode_set(mode='OBJECT');self.rig.select_set(False)
        mesh=bpy.data.meshes.new(name+' continuous illustrated surface')
        verts=np.column_stack([pp[:,0]*.00212,np.zeros(len(pp)),-pp[:,1]*.00212])
        mesh.from_pydata(verts,[],inverse.reshape(-1,3));mesh.update()
        self.surface=bpy.data.objects.new(name+' / original illustrated character',mesh);bpy.context.collection.objects.link(self.surface)
        uv=mesh.uv_layers.new(name='Original illustration UV')
        source=surface
        uv.data.foreach_set('uv',np.column_stack([source[:,0]/1672,1-source[:,1]/941]).astype(np.float32).ravel())
        mesh.materials.append(image_material(name+' / preserved ink and paper',ROOT/'assets'/'duel-v2'/'shot-F.png'))
        dd=[]
        for aa,bb in BONES:
            a,b=self.bind[aa],self.bind[bb];v=b-a;u=np.clip(((pp-a)@v)/(v@v),0,1)
            dd.append(np.sum((pp-(a+u[:,None]*v))**2,axis=1))
        distances=np.array(dd).T;order=np.argsort(distances,axis=1)[:,:2]
        weights=1/(distances+180)**2.2;keep=np.zeros_like(weights);np.put_along_axis(keep,order,1,axis=1)
        weights*=keep;weights/=weights.sum(axis=1)[:,None]
        weights,_=blend_head_cape(weights,pp,self.hero)
        hand=(pp[:,0]<1104)&(pp[:,1]>190)&(pp[:,1]<305) if not self.hero else np.zeros(len(pp),bool)
        if not self.hero:weights[hand]=0
        for i in range(len(BONES)):
            vg=self.surface.vertex_groups.new(name=str(i))
            vals=np.round(weights[:,i]*255).astype(np.int32)
            for v in np.unique(vals):
                if v>0:vg.add(np.flatnonzero(vals==v).tolist(),float(v)/255,'REPLACE')
        if not self.hero:
            vg=self.surface.vertex_groups.new(name='released grip');vg.add(np.flatnonzero(hand).tolist(),1,'REPLACE')
        mod=self.surface.modifiers.new('Illustration skeleton deformation','ARMATURE');mod.object=self.rig
        # Dark marks remain real editable animated GP drawings on top of the
        # image-preserving character surface, rather than a static overlay.
        centers=np.add.reduceat(self.points,np.r_[0,np.cumsum(self.lengths)[:-1]],axis=0)/self.lengths[:,None]
        mask=(self.mats==5)&(centers[:,1]>(335 if self.hero else 305))
        self.render_indices=np.flatnonzero(np.repeat(mask,self.lengths))
        self.draw_lengths=self.lengths[mask];self.draw_mats=self.mats[mask]
        self.layer.opacity=.25

    def draw(self,p,t,frame):
        target=super().draw(p,t,frame)
        depth=-.005 if self.hero else .06
        for i,(aa,bb) in enumerate(BONES):
            self.pose_bone(str(i),target[aa],target[bb],self.rest_lengths[i],depth,frame)
        if not self.hero:
            self.pose_bone('released grip',target['elbow_l'],target['wrist_l'],self.rest_lengths[7],depth,frame,small=t>=26.8)
        return target

    def pose_bone(self,name,a,b,rest,depth,frame,small=False):
        v=b-a;length=np.linalg.norm(v);d=v/max(length,.0001);per=np.array([d[1],-d[0]])
        scale=length/rest
        mat=Matrix(((float(per[0]),float(d[0]*scale),0,float(a[0])),(0,0,-1,depth),(float(per[1]),float(d[1]*scale),0,float(a[1])),(0,0,0,1)))
        pb=self.rig.pose.bones[name];pb.rotation_mode='QUATERNION';pb.matrix=mat
        if small:pb.scale*=.001
        for prop in ('location','rotation_quaternion','scale'):pb.keyframe_insert(prop,frame=frame)


def sword_points(grip,angle):
    g=np.array(grip);d=np.array([math.cos(angle),math.sin(angle)]);n=np.array([-d[1],d[0]])
    paths=[];mats=[]
    def path(points,mat):paths.append(np.array(points));mats.append(mat)
    path([g-d*.25-n*.022,g-d*.25+n*.022,g+n*.022,g-n*.022],5)
    path([g-n*.065-d*.012,g+n*.065-d*.012,g+n*.065+d*.012,g-n*.065+d*.012],5)
    # One long, tapered rigid blade, independent from the sleeve drawings.
    path([g-n*.014,g+n*.014,g+d*1.20+n*.012,g+d*1.32,g+d*1.19-n*.006],5)
    path([g+n*.006,g+n*.011,g+d*1.19+n*.009,g+d*1.29],0)
    return paths,mats


def camera_state(t,H,E):
    h=sample(H,t);e=sample(E,t)
    if t<5:return ((-.1,1.10),6.2-.025*t,0)
    if t<9:return ((h[5][0]-.10,h[5][1]),1.40,-.04)
    if t<13:return ((h[0]+h[2]+.03,h[1]+.71),1.65,.035)
    if t<15:return ((0,1.12),6.2,0)
    if t<17:return ((.02,1.14),5.35,-.085)
    if t<19:return ((.12,1.44),2.45,.07)
    if t<22:return ((.1+(t-19)*.14,1.00),5.35,-.04)
    if t<23.5:return ((e[0]+e[2]-.025,e[1]+.69),1.25,.04)
    if t<26:return ((.45,1.10),3.95,.065)
    if t<28:return ((1.1,1.13),5.10,-.065)
    return ((1.35,1.05),6.3-.025*(t-28),0)


def build(preview=False):
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    s=bpy.context.scene;s.render.engine='BLENDER_EEVEE_NEXT';s.eevee.taa_render_samples=16
    s.render.resolution_x=960;s.render.resolution_y=540;s.render.resolution_percentage=100
    s.render.fps=24;s.frame_start=1;s.frame_end=840;s.render.image_settings.file_format='PNG'
    s.view_settings.view_transform='Standard';s.view_settings.look='None'
    s.world.use_nodes=True
    s.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.58,.505,.38,1)
    s.world.node_tree.nodes['Background'].inputs['Strength'].default_value=1
    palette=[gp_material('Ink value '+str(i),(v,v*.88,v*.71)) for i,v in enumerate((.58,.43,.29,.15,.055,.009))]
    bgpalette=[gp_material('Landscape value '+str(i),(v,v*.88,v*.71)) for i,v in enumerate((.58,.45,.33,.24))]
    bg=np.load(ART/'background-vectors.npz');ob,layer=gp_object('Painted road / static GP landscape',bgpalette)
    pts=bg['points'];pos=np.column_stack([(pts[:,0]-835)*.006,np.full(len(pts),2.5),(750-pts[:,1])*.0045])
    add_drawing(layer,1,pos,bg['lengths'],bg['materials'])
    ob.hide_render=True
    # A clean existing landscape contains no duplicate static combatants.
    bgmesh=bpy.data.meshes.new('Open road background')
    bgmesh.from_pydata([(-5,3,-3),(5,3,-3),(5,3,4),(-5,3,4)],[],[(0,1,2,3)])
    background=bpy.data.objects.new('Painted open road',bgmesh);bpy.context.collection.objects.link(background)
    uv=bgmesh.uv_layers.new();uv.data.foreach_set('uv',np.array([.61,.10,1,.10,1,.95,.61,.95],np.float32))
    bgmesh.materials.append(image_material('Preserved hanji landscape',ROOT/'assets'/'sequence'/'shot-02.png'))
    specs=json.loads((ART/'art.json').read_text());hero=PaintedActor('hero',specs['hero'],palette);enemy=PaintedActor('enemy',specs['enemy'],palette)
    weapons,weapon_layer=gp_object('Animated long narrow swords',palette)
    fxmat=gp_material('Sumi / tapered moving brush line',(.012,.010,.008),fill=False)
    fx,fx_layer=gp_object('GP / timed blade arcs and contact accents',[fxmat])
    data=bpy.data.cameras.new('Ink camera');data.type='ORTHO';data.lens=45
    camera=bpy.data.objects.new('Ink camera',data);bpy.context.collection.objects.link(camera);s.camera=camera
    H,E=choreography()
    times=(0,6,11,14.9,15.25,15.5,15.75,17.25,19.78,22.5,24.1,26.5,27.0,31) if preview else [i/12 for i in range(420)]
    for t in times:
        frame=round(t*24)+1;h=sample(H,t);e=sample(E,t)
        hero.draw(h,t,frame);enemy.draw(e,t,frame)
        paths,mats=sword_points(h[5],h[6])
        if t<26.80:p2,m2=sword_points(e[5],e[6])
        else:
            u=min(1,(t-26.8)/.70);a=math.radians(96)+u*7.0
            g=np.array([1.28,1.59])*(1-u)+np.array([2.65,.07])*u;g[1]+=.55*math.sin(math.pi*u)
            if u>=1:a=.02
            p2,m2=sword_points(g,a)
        paths+=p2;mats+=m2
        lengths=np.array([len(p) for p in paths],np.int32);pp=np.concatenate(paths)
        pos=np.column_stack([pp[:,0],np.full(len(pp),-.10),pp[:,1]])
        add_drawing(weapon_layer,frame,pos,lengths,np.array(mats,np.int32))
        paths=[]
        if t>=15:
            for keys,p in ((H,h),(E,e)):
                old=sample(keys,max(0,t-1/12));delta=p[6]-old[6]
                if abs(delta)>math.radians(7) and t<26.8:
                    grip=np.array(p[5]);arc=[]
                    for u in np.linspace(0,1,14):
                        angle=old[6]+delta*u;q=grip+np.array([math.cos(angle),math.sin(angle)])*1.18
                        arc.append((q[0],-.12,q[1]))
                    paths.append(arc)
            for hit in (15.50,17.25,20.50,24.03,26.49):
                if 0<=t-hit<.09:
                    center=(np.array(h[5])+np.array(e[5]))*.5+np.array([0,.27])
                    for a in (0,.8,1.7,2.5):
                        d=np.array([math.cos(a),math.sin(a)])
                        paths.append([(center[0]+d[0]*r,-.13,center[1]+d[1]*r) for r in (.05,.10,.14)])
        if paths:
            lens=np.array([len(p) for p in paths],np.int32)
            dr=add_drawing(fx_layer,frame,np.concatenate(paths),lens,np.zeros(len(paths),np.int32),cyclic=False)
            for stroke in dr.strokes:
                for i,pt in enumerate(stroke.points):pt.radius=.0015+.004*math.sin(math.pi*i/max(1,len(stroke.points)-1))
        else:fx_layer.frames.new(frame)
        center,scale,roll=camera_state(t,H,E)
        # A brief deterministic camera impulse accompanies the three contacts.
        kick=sum(max(0,1-abs(t-hit)/.10) for hit in (15.50,17.25,20.50,24.03,26.49))
        camera.location=(center[0]+kick*.025,-10,center[1]+kick*.018)
        camera.rotation_mode='QUATERNION'
        camera.rotation_quaternion=Vector((0,1,0)).to_track_quat('-Z','Y')@Quaternion((0,0,1),roll+kick*.006)
        data.ortho_scale=scale
        camera.keyframe_insert('location',frame=frame);camera.keyframe_insert('rotation_quaternion',frame=frame);data.keyframe_insert('ortho_scale',frame=frame)
    for act in bpy.data.actions:
        for fc in act.fcurves:
            for kp in fc.keyframe_points:kp.interpolation='CONSTANT'
    ed=s.sequence_editor_create();ed.strips.new_sound('Gloomy30s / 2m35s to 3m10s',str(ROOT/'assets'/'audio'/'bakkuo-155-190.wav'),channel=1,frame_start=1)
    s['animation']='Illustrated cutout armatures plus native animated GP ink and swords; 12 drawings/sec'
    s['source_art']='Existing project character illustration shot-F, traced to editable polygon drawings'
    s['drawing_count_per_actor']=len(times);s['song_start_seconds']=155
    OUT.mkdir(parents=True,exist_ok=True)
    s.frame_set(373)
    for item in s.objects:item.select_set(False)
    hero.ob.select_set(True);bpy.context.view_layer.objects.active=hero.ob
    bpy.ops.wm.save_as_mainfile(filepath=str(OUT/('gp-preview.blend' if preview else 'bakkuo-gp-animation.blend')),compress=True)
    (OUT/('preview-manifest.json' if preview else 'animation-manifest.json')).write_text(json.dumps({'seconds':35,'fps':24,'drawing_fps':12,'drawing_count_per_actor':len(times),'gp_actor_objects':2,'total_character_ink_point_positions':int((len(hero.render_indices)+len(enemy.render_indices))*len(times)),'technique':'Illustrated cutout armatures plus animated native GP ink and weapons','song_start':155,'additional_api_cost_usd':0,'status':'preview' if preview else 'renderable full animation'},indent=2),encoding='utf-8')
    return s,times


def main():
    p=argparse.ArgumentParser();p.add_argument('--preview',action='store_true');p.add_argument('--render',action='store_true')
    args=p.parse_args(sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [])
    s,times=build(args.preview)
    if args.preview:
        for t in (0,11,15.5,17.25,19.78,22.5,24.1,27.0,31):
            s.frame_set(round(t*24)+1);s.render.filepath=str(OUT/f'preview-{round(t*100):04d}.png');bpy.ops.render.render(write_still=True)
    if args.render:
        (OUT/'frames').mkdir(exist_ok=True)
        for i in range(420):
            s.frame_set(i*2+1);s.render.filepath=str(OUT/'frames'/f'frame-{i+1:04d}.png');bpy.ops.render.render(write_still=True)


if __name__=='__main__':main()
