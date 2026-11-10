"""Stroke-following numeral tiles. Every tile is generated whole, never clipped."""
import math
import numpy as np
from shapely.geometry import Polygon
from shapely.ops import unary_union

HALF_WIDTH=28.0

def cubic(start,a,b,end,count=220):
    t=np.linspace(0,1,count,endpoint=False)[:,None]
    return (1-t)**3*np.array(start)+3*(1-t)**2*t*np.array(a)+3*(1-t)*t**2*np.array(b)+t**3*np.array(end)

def centreline(digit):
    if digit=='0':
        angle=np.linspace(-math.pi/2,3*math.pi/2,1200,endpoint=False)
        return np.c_[140+108*np.cos(angle),170+170*np.sin(angle)],True
    if digit=='2':
        segments=[((60,100),(60,45),(105,0),(160,0)),((160,0),(215,0),(260,45),(260,100)),((260,100),(260,175),(110,205),(80,260)),((80,260),(50,315),(60,350),(110,350)),((110,350),(170,350),(220,340),(260,325))]
    elif digit=='5':
        segments=[((245,10),(210,10),(170,10),(130,10)),((130,10),(50,10),(50,50),(50,120)),((50,120),(50,190),(120,190),(170,190)),((170,190),(250,190),(280,235),(245,290)),((245,290),(210,345),(115,350),(60,310))]
    elif digit=='1':
        segments=[((80,90),(110,70),(135,20),(170,20)),((170,20),(250,20),(240,100),(240,170)),((240,170),(240,230),(240,290),(240,350))]
    else:raise ValueError(digit)
    points=np.concatenate([cubic(*s) for s in segments]+[np.array([segments[-1][-1]])])
    if digit=='1':points[:,1]=(points[:,1]-20)*340/330 # Shared cap height and baseline with zero.
    return points,False

def normal_field(points,closed):
    if closed:
        tangent=np.roll(points,-1,axis=0)-np.roll(points,1,axis=0)
    else:tangent=np.gradient(points,axis=0)
    tangent/=np.linalg.norm(tangent,axis=1)[:,None]
    return np.c_[-tangent[:,1],tangent[:,0]],tangent

def sample_map(points,closed,v):
    normals,tangents=normal_field(points,closed)
    shifted=points+normals*v
    if closed:
        shifted=np.vstack([shifted,shifted[0]])
        centre=np.vstack([points,points[0]])
        lengths=np.r_[0,np.cumsum(np.linalg.norm(np.diff(centre,axis=0),axis=1))]
    else:
        extent=0.0
        centre_lengths=np.r_[0,np.cumsum(np.linalg.norm(np.diff(points,axis=0),axis=1))]
        lengths=np.r_[0,centre_lengths+extent,centre_lengths[-1]+2*extent]
        shifted=np.vstack([shifted[0]-tangents[0]*extent,shifted,shifted[-1]+tangents[-1]*extent])
    actual_length=float(np.linalg.norm(np.diff(shifted,axis=0),axis=1).sum())
    keep=np.r_[True,np.diff(lengths)>1e-7]
    shifted=shifted[keep];lengths=lengths[keep]
    return lengths/lengths[-1],shifted,actual_length

def interpolate(mapping,fractions):
    t,points,_=mapping
    return np.c_[np.interp(fractions,t,points[:,0]),np.interp(fractions,t,points[:,1])]

def build_ribbon(level,n):
    glyphs=[];x=0
    for digit in str(level):
        points,closed=centreline(digit)
        minimum=points[:,0].min()-HALF_WIDTH
        points=points+np.array([x-minimum,0])
        glyphs.append((points,closed))
        x=points[:,0].max()+HALF_WIDTH+24
    lengths=[sample_map(p,c,0)[2] for p,c in glyphs]
    pitch=math.sqrt(sum(lengths)*HALF_WIDTH*2/n)
    lane_count=max(3,round(HALF_WIDTH*2/pitch))
    boundaries=np.linspace(-HALF_WIDTH,HALF_WIDTH,lane_count+1)
    lanes=[]
    for points,closed in glyphs:
        maps={}
        for v in boundaries:maps[float(v)]=sample_map(points,closed,float(v))
        for a,b in zip(boundaries[:-1],boundaries[1:]):
            mid=sample_map(points,closed,float((a+b)/2))
            lanes.append({'points':points,'closed':closed,'a':float(a),'b':float(b),'maps':maps,'weight':mid[2]*(b-a)})
    total=sum(l['weight'] for l in lanes)
    cap_count=sum(2 for lane in lanes if not lane['closed'])
    body_count=n-cap_count
    counts=[max(2,round(l['weight']/total*body_count)) for l in lanes]
    while sum(counts)!=body_count:
        delta=1 if sum(counts)<body_count else -1
        i=max(range(len(lanes)),key=lambda i:(lanes[i]['weight']/total*body_count-counts[i])*delta if counts[i]>2 or delta>0 else -1e9)
        counts[i]+=delta
    tiles=[]
    for lane,count in zip(lanes,counts):
        points,closed,a,b=lane['points'],lane['closed'],lane['a'],lane['b']
        # Cache transverse samples of the body; end caps are separate whole bands.
        transverse=np.linspace(a,b,7)
        for v in transverse:
            key=float(v)
            if key not in lane['maps']:lane['maps'][key]=sample_map(points,closed,key)
        for i in range(count):
            start=i/count;end=(i+1)/count
            fractions=np.linspace(start,end,7)
            outer=interpolate(lane['maps'][a],fractions)
            right=np.array([interpolate(lane['maps'][float(v)],[end])[0] for v in transverse[1:]])
            inner=interpolate(lane['maps'][b],fractions[::-1])[1:]
            left=np.array([interpolate(lane['maps'][float(v)],[start])[0] for v in transverse[-2:0:-1]])
            polygon=Polygon(np.vstack([outer,right,inner,left]))
            if not polygon.is_valid:raise ValueError(f'Folded ribbon cell: level {level}, lane {a}, cell {i}')
            tiles.append(polygon)
    # Build each terminal as broad complete bands, not trimmed leftovers from body tiles.
    for lane in lanes:
        if lane['closed']:continue
        points=lane['points'];normals,tangents=normal_field(points,False)
        for end,sign in [(0,-1),(-1,1)]:
            values=np.linspace(lane['a'],lane['b'],18)
            arc=[points[end]+normals[end]*v+tangents[end]*sign*math.sqrt(max(0,HALF_WIDTH**2-v*v)) for v in values]
            inside=[points[end]+normals[end]*lane['b'],points[end]+normals[end]*lane['a']]
            tiles.append(Polygon(np.vstack([arc,inside])).buffer(0))
    assert len(tiles)==n
    areas=np.array([p.area for p in tiles])
    ratios=[]
    for tile in tiles:
        vertices=list(tile.minimum_rotated_rectangle.exterior.coords)
        edges=[math.dist(vertices[i],vertices[i+1]) for i in range(4)]
        ratios.append(min(edges)/max(edges))
    median=float(np.median(areas))
    print(f'Ribbon {level}: {n} whole tiles, min/median area {areas.min()/median:.2f}, min aspect {min(ratios):.2f}',flush=True)
    assert areas.min()/median>.30, 'A ribbon cell is too small'
    assert min(ratios)>.30, 'A ribbon cell is too thin'
    outline=unary_union(tiles)
    return outline,sorted(tiles,key=lambda p:(round(p.centroid.y/pitch),p.centroid.x)),pitch
