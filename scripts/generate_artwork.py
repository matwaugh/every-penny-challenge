"""Generate exact-count vector mosaics. Development-only; no browser dependencies.
Uses approved rounded-slab outlines, NumPy, Matplotlib and Shapely 2.1.2.
"""
import json
import math
import re
from pathlib import Path
import sys
sys.path.append('/workspace/.epc-artwork-tools')
import numpy as np
from shapely.geometry import Polygon, Point
from slab_geometry import build_slab

ROOT=Path(__file__).resolve().parents[1]

def fmt(v): return f'{v:.2f}'.rstrip('0').rstrip('.') or '0'

def polygon_svg(poly, rounding=0):
    if poly.geom_type=='MultiPolygon': return ''.join(polygon_svg(p,rounding) for p in poly.geoms)
    out=[]
    for ring in [poly.exterior,*poly.interiors]:
        points=list(ring.coords)[:-1]
        if len(points)<3:continue
        if not rounding:
            out.append('M'+'L'.join(f'{fmt(x)} {fmt(y)}' for x,y in points)+'Z');continue
        before=[];after=[]
        for i,point in enumerate(points):
            prev=points[i-1];nxt=points[(i+1)%len(points)]
            a=math.dist(point,prev);b=math.dist(point,nxt)
            radius=min(rounding,a*.23,b*.23)
            before.append((point[0]+(prev[0]-point[0])*radius/a,point[1]+(prev[1]-point[1])*radius/a))
            after.append((point[0]+(nxt[0]-point[0])*radius/b,point[1]+(nxt[1]-point[1])*radius/b))
        out.append('M'+f'{fmt(after[-1][0])} {fmt(after[-1][1])}')
        for i,(x,y) in enumerate(points):
            out.append(f'L{fmt(before[i][0])} {fmt(before[i][1])}Q{fmt(x)} {fmt(y)} {fmt(after[i][0])} {fmt(after[i][1])}')
        out.append('Z')
    return ''.join(out)

def parts(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type=='Polygon':return [geometry]
    return [p for p in geometry.geoms if p.geom_type=='Polygon']

RAINBOW=['#f45c70','#ff9245','#f3ca3e','#7ec86d','#31b6b4','#508bd8','#9465d4']
FLOWER=['#f9d846','#c7d94d','#6cc67e','#36b7bf','#7380d7','#c975cd','#ee9dbf']
SUN=['#ffe16a','#ffc950','#ffab43','#f48a43','#ed6949']

def colour(stops,t):
    t=max(0,min(1,t));scaled=t*(len(stops)-1);i=min(int(scaled),len(stops)-2);f=scaled-i
    a=[int(stops[i][j:j+2],16) for j in [1,3,5]];b=[int(stops[i+1][j:j+2],16) for j in [1,3,5]]
    return '#'+''.join(f'{round(x+(y-x)*f):02x}' for x,y in zip(a,b))

def radial_shape(kind):
    # A soft twelve-ray sun and six-petal flower; both have continuous curved edges.
    radius=(lambda a:260+32*math.cos(12*(a+math.pi/2))) if kind=='sun' else (lambda a:230+62*math.cos(6*(a+math.pi/2)))
    points=[(310+radius(a)*math.cos(a),310+radius(a)*math.sin(a)) for a in np.linspace(0,2*math.pi,1440,endpoint=False)]
    return Polygon(points),radius

def radial_tiles(shape,radius,n):
    # Circular courses keep the centre calm and the cells almost square.
    # The silhouette clips the outer courses into petals/rays instead of warping every row.
    maxradius=292
    def mesh(pitch):
        result=[]
        result.extend(parts(Point(310,310).buffer(pitch*.5,quad_segs=24).intersection(shape)))
        inner=pitch*.5
        while inner<maxradius:
            outer=inner+pitch;middle=(inner+outer)/2
            count=max(6,round(2*math.pi*middle/pitch))
            for sector in range(count):
                start=-math.pi/2+sector/count*2*math.pi
                end=-math.pi/2+(sector+1)/count*2*math.pi
                angles=np.linspace(start,end,max(5,math.ceil(600/count)))
                outside=[(310+outer*math.cos(a),310+outer*math.sin(a)) for a in angles]
                inside=[(310+inner*math.cos(a),310+inner*math.sin(a)) for a in reversed(angles)]
                result.extend(p for p in parts(Polygon(outside+inside).intersection(shape)) if p.area>1e-5)
            inner=outer
        return result
    low=math.sqrt(shape.area/n)*.65;high=math.sqrt(shape.area/n)*1.6;best=None
    desired=math.ceil(n*1.06)
    for _ in range(16):
        pitch=(low+high)/2;tiles=mesh(pitch)
        if len(tiles)>=desired:
            if best is None or len(tiles)<len(best[1]):best=(pitch,tiles)
            low=pitch
        else:high=pitch
    pitch,tiles=best
    while len(tiles)>n:
        index=min(range(len(tiles)),key=lambda i:tiles[i].area);tile=tiles.pop(index)
        neighbours=[(tile.boundary.intersection(p.boundary).length,i) for i,p in enumerate(tiles) if tile.distance(p)<.02]
        target=max(neighbours)[1] if neighbours else min(range(len(tiles)),key=lambda i:tile.distance(tiles[i]))
        tiles[target]=tiles[target].union(tile).buffer(0)
    assert len(tiles)==n
    return [(tile,min(1,math.hypot(tile.centroid.x-310,tile.centroid.y-310)/292)) for tile in tiles],pitch

def compact_svg(path):
    # Relative coordinates share repeated tile geometry and compress much better.
    # 0.1 view-box unit precision is well below one screen pixel.
    current=(0,0);start=(0,0);result=[]
    def number(v):return f'{v:.1f}'.rstrip('0').rstrip('.') if v else '0'
    for command,body in re.findall(r'([MLQCZ])([^MLQCZ]*)',path):
        if command=='Z':result.append('z');current=start;continue
        values=[round(float(v),1) for v in body.split()]
        points=list(zip(values[::2],values[1::2]))
        if command=='M':
            current=points[0];start=current;result.append('M'+' '.join(number(v) for v in current));continue
        relative=[coordinate-current[index%2] for point in points for index,coordinate in enumerate(point)]
        if all(abs(v)<.01 for v in relative):continue
        result.append(command.lower()+' '.join(number(round(v,1)) for v in relative))
        current=points[-1]
    return ''.join(result)

def build(digits_only=False):
    if digits_only:
        saved=(ROOT/'artwork-data.js').read_text()
        data=json.loads(saved.split('window.PennyArtwork=',1)[1].rsplit(';',1)[0])
    else:data={}
    for level in [2,5,10]:
        n=level*100
        if not digits_only:data[str(level)]={}
        for kind in (['digits'] if digits_only else ['digits','sun','flower']):
            if kind=='digits':
                shape,tiles,pitch=build_slab(level,n);silhouette=polygon_svg(shape)
                minx,miny,maxx,maxy=shape.bounds
                values=[(p,colour(RAINBOW,(p.centroid.y-miny)/(maxy-miny))) for p in tiles]
            else:
                shape,radius=radial_shape(kind);silhouette=polygon_svg(shape)
                raw,pitch=radial_tiles(shape,radius,n)
                values=[(p,colour(SUN if kind=='sun' else FLOWER,t)) for p,t in raw]
                minx,miny,maxx,maxy=shape.bounds
            margin=3 if kind=='digits' else 6
            cells=[]
            for tile,fill in values:
                # An inset creates white gutters; rounded corners soften the mosaic.
                inset=tile.buffer(-pitch*(.03 if kind=='digits' else .035),join_style='mitre' if kind=='digits' else 'round')
                if kind=='digits':
                    assert not inset.is_empty and inset.geom_type=='Polygon', 'A numeral tile collapsed while adding gutters'
                elif inset.is_empty:inset=tile
                cells.append({'d':compact_svg(polygon_svg(inset,pitch*(.12 if kind=='digits' else .11))),'colour':fill})
            entry={'viewBox':[round(minx-margin,2),round(miny-margin,2),round(maxx-minx+margin*2,2),round(maxy-miny+margin*2,2)],'outline':silhouette,'cells':cells}
            data[str(level)][kind]=entry
            print(level,kind,len(cells),flush=True)
    (ROOT/'artwork-data.js').write_text('/* Generated vector geometry: scripts/generate_artwork.py */\nwindow.PennyArtwork='+json.dumps(data,separators=(',',':'))+';\n')

if __name__=='__main__':build(digits_only='--digits-only' in sys.argv)
