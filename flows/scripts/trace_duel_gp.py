"""Trace existing approved concept art into native GP polygon data, offline.

This produces vector source assets, not a raster slideshow. The actual stroke
positions are subsequently redrawn by the animation script at 12 drawings/sec.
"""
from pathlib import Path
import json
import sys
import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'assets'/'gp-animation'
OUT.mkdir(exist_ok=True)
sys.path.insert(0,str(ROOT/'.tools'))
import mapbox_earcut
img=cv2.imread(str(ROOT/'assets'/'duel-v2'/'shot-F.png'))
gray=cv2.cvtColor(img,cv2.COLOR_BGR2GRAY)

FIGURES={
 'hero': {
  'outline':[(85,280),(360,227),(510,235),(573,144),(761,112),(817,141),(909,262),(813,292),(852,344),(918,369),(942,445),(891,505),(801,547),(871,643),(1019,922),(896,928),(794,823),(714,734),(591,711),(392,784),(228,850),(139,861),(112,845),(162,797),(292,665),(341,599),(465,523),(332,538),(425,466),(265,484),(325,410),(111,423)],
  'joints':{'hip':(603,591),'chest':(718,365),'head':(755,283),'shoulder_l':(689,371),'shoulder_r':(754,378),'elbow_l':(732,475),'elbow_r':(817,422),'wrist_l':(864,467),'wrist_r':(874,418),'knee_l':(386,723),'knee_r':(788,717),'ankle_l':(181,833),'ankle_r':(954,879)},
  'bounds':(85,105,1024,931),
 },
 'enemy':{
  'outline':[(1002,177),(1115,178),(1261,170),(1323,89),(1400,62),(1471,85),(1522,108),(1555,189),(1500,215),(1574,260),(1585,319),(1641,404),(1671,429),(1671,507),(1635,521),(1579,482),(1523,446),(1495,534),(1546,644),(1568,748),(1578,886),(1533,911),(1450,895),(1417,802),(1321,661),(1248,682),(1183,802),(1186,894),(1102,915),(1048,895),(1057,815),(1061,714),(1119,590),(1193,495),(1179,420),(1163,374),(1110,340),(1056,296),(1005,254)],
  'joints':{'hip':(1323,538),'chest':(1370,306),'head':(1393,192),'shoulder_l':(1294,283),'shoulder_r':(1452,322),'elbow_l':(1175,254),'elbow_r':(1543,408),'wrist_l':(1060,234),'wrist_r':(1623,477),'knee_l':(1160,689),'knee_r':(1457,698),'ankle_l':(1120,880),'ankle_r':(1510,877)},
  'bounds':(990,55,1672,925),
 }
}

def triangulate_regions(g,m,scale,cuts=(245,205,165,120,75,35),area_min=1.1):
    """Disjoint triangles preserve holes and cannot turn into giant GP fills."""
    triangles=[];materials=[]
    for level,upper in enumerate(cuts):
        lower=cuts[level+1] if level+1<len(cuts) else -1
        binary=np.uint8((g<=upper)&(g>lower)&(m>0))*255
        cs,hh=cv2.findContours(binary,cv2.RETR_CCOMP,cv2.CHAIN_APPROX_SIMPLE)
        if hh is None:continue
        for i,c in enumerate(cs):
            if hh[0,i,3]>=0 or cv2.contourArea(c)<area_min:continue
            rings=[]
            outer=cv2.approxPolyDP(c,.40,True).reshape(-1,2)
            if len(outer)<3:continue
            rings.append(outer)
            child=hh[0,i,2]
            while child>=0:
                hole=cv2.approxPolyDP(cs[child],.40,True).reshape(-1,2)
                if len(hole)>=3 and cv2.contourArea(cs[child])>=.7:rings.append(hole)
                child=hh[0,child,0]
            pp=np.concatenate(rings).astype(np.float32)/scale
            ends=np.cumsum([len(r) for r in rings]).astype(np.uint32)
            inds=mapbox_earcut.triangulate_float32(pp,ends).reshape(-1,3)
            for tri in pp[inds]:
                triangles.append(tri);materials.append(level)
    return np.concatenate(triangles),np.full(len(triangles),3,np.int32),np.array(materials,np.int32)

def trace(name,spec):
    coarse=np.zeros(gray.shape,np.uint8)
    cv2.fillPoly(coarse,[np.array(spec['outline'],np.int32)],255)
    # Follow the ink silhouette instead of leaving a polygonal paper border.
    seed=np.uint8((gray<165)&(coarse>0))*255
    connected=cv2.morphologyEx(seed,cv2.MORPH_CLOSE,np.ones((9,9),np.uint8),iterations=1)
    cs,_=cv2.findContours(connected,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    mask=np.zeros_like(coarse)
    for c in cs:
        if cv2.contourArea(c)>500:cv2.drawContours(mask,[c],-1,255,cv2.FILLED)
    mask=cv2.bitwise_and(mask,coarse)
    # Important pale areas of skin and the woven hat remain opaque.
    if name=='hero':
        patches=[[(574,148),(760,114),(907,261),(783,275),(605,215)],[(750,264),(812,281),(794,339),(740,320)],[(805,372),(882,368),(920,446),(853,493),(815,441)]]
    else:
        patches=[[(1335,147),(1444,129),(1490,199),(1445,291),(1381,307),(1321,247)],[(1016,199),(1083,207),(1119,267),(1072,293),(1012,249)],[(1590,418),(1657,430),(1670,488),(1639,513),(1584,470)]]
    for pp in patches:cv2.fillPoly(mask,[np.array(pp,np.int32)],255)
    mask=cv2.bitwise_and(mask,coarse)
    scale=.60
    g=cv2.resize(gray,None,fx=scale,fy=scale,interpolation=cv2.INTER_AREA)
    m=cv2.resize(mask,(g.shape[1],g.shape[0]),interpolation=cv2.INTER_NEAREST)
    points,lengths,mats=triangulate_regions(g,m,scale)
    np.savez_compressed(OUT/f'{name}-vectors.npz',points=points,lengths=lengths,materials=mats)
    # A separate continuous silhouette preserves the original image texture.
    pp,_,_=triangulate_regions(np.zeros(g.shape,np.uint8),m,scale,cuts=(1,),area_min=2)
    stack=list(pp.reshape(-1,3,2));small=[]
    while stack:
        tri=stack.pop()
        lens=np.sum((tri-np.roll(tri,-1,axis=0))**2,axis=1);i=int(np.argmax(lens))
        if lens[i]<=35**2:small.append(tri);continue
        j=(i+1)%3;k=(i+2)%3;mid=(tri[i]+tri[j])*.5
        stack.extend([np.array([tri[i],mid,tri[k]]),np.array([mid,tri[j],tri[k]])])
    np.savez_compressed(OUT/f'{name}-surface.npz',points=np.concatenate(small))
    return {'strokes':len(lengths),'points':len(points),'joints':spec['joints'],'source':'assets/duel-v2/shot-F.png'}

data={name:trace(name,spec) for name,spec in FIGURES.items()}
bg=cv2.imread(str(ROOT/'assets'/'duel-v2'/'shot-C.png'),cv2.IMREAD_GRAYSCALE)
cv2.rectangle(bg,(305,348),(938,770),244,-1)
cv2.rectangle(bg,(970,80),(1455,800),244,-1)
bg=cv2.resize(bg,None,fx=.5,fy=.5,interpolation=cv2.INTER_AREA)
pts,lens,mats=triangulate_regions(bg,np.ones(bg.shape,np.uint8),.5,cuts=(170,105,50),area_min=5)
np.savez_compressed(OUT/'background-vectors.npz',points=pts,lengths=lens,materials=mats+1)
(OUT/'art.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
print(json.dumps({k:{q:v[q] for q in ('strokes','points')} for k,v in data.items()}))
