"""Approved fuller slab outlines; regular proportions in the 1's flat base."""
import os
os.environ.setdefault('MPLCONFIGDIR','/tmp/epc-slab-mpl')
import math
import numpy as np
from matplotlib.textpath import TextPath
from matplotlib.font_manager import FontProperties
from matplotlib.transforms import Affine2D
from shapely.geometry import Polygon, box
FONT='/usr/share/fonts/opentype/urw-base35/URWBookman-Demi.otf'

def shape_for(text):
    geometry=Polygon();offset=0
    for digit in text:
        path=TextPath((0,0),digit,size=600,prop=FontProperties(fname=FONT))
        bounds=path.get_extents()
        path=path.transformed(Affine2D().translate(-bounds.xmin,-bounds.ymin).scale(1,-1).translate(offset,bounds.height))
        glyph=Polygon()
        for ring in path.to_polygons():
            if len(ring)>=3:glyph=glyph.symmetric_difference(Polygon(ring).buffer(0))
        geometry=geometry.union(glyph)
        offset+=bounds.width+14
    # Round both convex serif corners and concave joins without creating pointed ends.
    geometry=geometry.buffer(8,quad_segs=12).buffer(-16,quad_segs=12).buffer(8,quad_segs=12)
    return geometry.simplify(.06,preserve_topology=True)

def polygons(g):
    if g.is_empty:return []
    if g.geom_type=='Polygon':return [g]
    return [p for p in g.geoms if p.geom_type=='Polygon']

def aspect(p):
    coords=list(p.minimum_rotated_rectangle.exterior.coords)
    lengths=[math.dist(coords[i],coords[i+1]) for i in range(4)]
    return min(lengths)/max(lengths)

def tile_shape(shape,n):
    minx,miny,maxx,maxy=shape.bounds
    def mesh(pitch):
        cells=[]
        for y in np.arange(miny,maxy,pitch):
            for x in np.arange(minx,maxx,pitch):
                cells.extend(p for p in polygons(shape.intersection(box(round(x,3),round(y,3),round(x+pitch,3),round(y+pitch,3)))) if p.area>1e-5)
        return cells
    for oversample in [1.25,1.45,1.7,2.0]:
        target=math.ceil(n*oversample);low=math.sqrt(shape.area/target)*.7;high=math.sqrt(shape.area/target)*1.7;best=None
        for _ in range(13):
            pitch=(low+high)/2;cells=mesh(pitch)
            if len(cells)>=target:
                if best is None or len(cells)<len(best[1]):best=(pitch,cells)
                low=pitch
            else:high=pitch
        pitch,cells=best
        bounds=[p.bounds for p in cells]
        while len(cells)>n:
            # Small pieces are absorbed into a substantial adjoining tile.
            index=min(range(len(cells)),key=lambda i:cells[i].area)
            p=cells.pop(index);bbox=bounds.pop(index);candidates=[]
            for j,(q,b) in enumerate(zip(cells,bounds)):
                if b[0]>bbox[2]+.001 or b[2]<bbox[0]-.001 or b[1]>bbox[3]+.001 or b[3]<bbox[1]-.001:continue
                shared=p.boundary.intersection(q.boundary).length
                if shared<.001:continue
                merged=p.union(q)
                if merged.geom_type!='Polygon':continue
                # Prefer compact unions with long common borders.
                score=shared*math.sqrt(merged.area)/merged.length
                candidates.append((score,j,merged))
            if not candidates:raise ValueError('No connected neighbour for fragment')
            _,j,merged=max(candidates,key=lambda item:item[0]);cells[j]=merged;bounds[j]=merged.bounds
        areas=np.array([p.area for p in cells]);area_ratio=float(areas.min()/np.median(areas));min_aspect=min(map(aspect,cells))
        if area_ratio>=.35 and min_aspect>=.3:
            assert len(cells)==n
            assert abs(sum(p.area for p in cells)-shape.area)<.1
            assert all(p.is_valid and p.geom_type=='Polygon' for p in cells)
            return cells,pitch,area_ratio,min_aspect
    raise ValueError(f'No acceptable complete-cell mesh for {n}: area {area_ratio}, aspect {min_aspect}')


def balance_one_base(cells,shape):
    one=shape_for('1');right=one.bounds[2];bottom=one.bounds[3]
    typical=float(np.median([p.area for p in cells]))
    def in_base(p):return p.bounds[2]<=right+.01 and p.centroid.y>bottom*.8
    def flat_base(p):return in_base(p) and p.bounds[0]>=20 and p.bounds[2]<=right-20
    corrected=[];split=0
    for p in cells:
        x0,y0,x1,y1=p.bounds
        if flat_base(p) and y1-y0>1.3*(x1-x0):
            mid=(y0+y1)/2
            pieces=[p.intersection(box(x0-1,y0-1,x1+1,mid)),p.intersection(box(x0-1,mid,x1+1,y1+1))]
            assert all(q.geom_type=='Polygon' and q.area>=typical*.35 for q in pieces), 'Foot subdivision would create a small fragment'
            corrected.extend(pieces);split+=1
        else:corrected.append(p)
    # Retain the exact 1,000 values by combining a small number of compact, adjoining
    # tiles elsewhere. No tile in the foot is used for this compensation.
    while len(corrected)>len(cells):
        candidates=[]
        indices=sorted((i for i,p in enumerate(corrected) if not in_base(p)),key=lambda i:corrected[i].area)[:30]
        bounds=[p.bounds for p in corrected]
        for i in indices:
            p=corrected[i];a=bounds[i]
            for j,q in enumerate(corrected):
                if i==j or in_base(q) or p.area+q.area>typical*2.3:continue
                b=bounds[j]
                if b[0]>a[2]+.001 or b[2]<a[0]-.001 or b[1]>a[3]+.001 or b[3]<a[1]-.001:continue
                shared=p.boundary.intersection(q.boundary).length
                if shared<.001:continue
                union=p.union(q)
                if union.geom_type!='Polygon' or aspect(union)<.3:continue
                candidates.append((shared*math.sqrt(union.area)/union.length,i,j,union))
        assert candidates,'No safe count-preserving merge outside the foot'
        _,i,j,merged=max(candidates,key=lambda x:x[0]);corrected[i]=merged;corrected.pop(j)
    assert len(corrected)==len(cells)
    assert abs(sum(p.area for p in corrected)-shape.area)<.1
    flat=[p for p in corrected if flat_base(p)]
    assert flat and all((p.bounds[3]-p.bounds[1])/(p.bounds[2]-p.bounds[0])<=1.3+.001 for p in flat)
    print(f'1 flat base: {split} tall cells subdivided; all {len(flat)} flat-base cells have height/width <= 1.30',flush=True)
    return corrected

def build_slab(level,n):
    shape=shape_for(str(level))
    cells,pitch,area_ratio,min_aspect=tile_shape(shape,n)
    if level==10:cells=balance_one_base(cells,shape)
    areas=np.array([p.area for p in cells]);ratio=float(areas.min()/np.median(areas));aspect_ratio=min(map(aspect,cells))
    assert ratio>=.35 and aspect_ratio>=.3
    print(f'Slab {level}: {len(cells)} tiles; minimum area ratio {ratio:.3f}; minimum aspect {aspect_ratio:.3f}',flush=True)
    return shape,sorted(cells,key=lambda p:(round(p.centroid.y/pitch),p.centroid.x)),pitch
