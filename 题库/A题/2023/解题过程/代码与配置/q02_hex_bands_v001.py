"""Q2-A explicit six-sector straight-edge band extension, no binary point selection.
All shells share one triangular lattice: squared distance=d^2(a^2+ab+b^2)>=d^2.
This is a new parameterization, not the prior constant-radius circle generator.
"""
import math,hashlib,json
import q02_design_v002 as d

def make_hex_spec(tower,w,h,z,phi=0.,spacing_margin=.05,name='hex',version='v001'):
 return dict(generator='hex_bands',name=name,version=version,tower_xy=list(tower),width=w,height=h,installation_height=z,phi=phi,spacing_margin=spacing_margin)

def lattice_rows(K):
 directions=[(1,0),(0,1),(-1,1),(-1,0),(0,-1),(1,-1)]
 for k in range(1,K+1):
  for sector in range(6):
   a,b=directions[sector];c,e=directions[(sector+1)%6]
   for j in range(k):yield k,sector,j,(k-j)*a+j*c,(k-j)*b+j*e

def generate_hex_design(generator,name,version,tower_xy,width,height,installation_height,phi,spacing_margin):
 vals=[*tower_xy,width,height,installation_height,phi,spacing_margin]
 if not all(math.isfinite(float(x))for x in vals):raise ValueError('nonfinite hex parameters')
 if generator!='hex_bands'or spacing_margin<=0:raise ValueError('hex generator/margin')
 if not(2<=height<=width<=8 and 2<=installation_height<=6 and installation_height>height/2 and math.hypot(*tower_xy)<=350):raise ValueError('hex parameters outside approved domain')
 step=width+5+spacing_margin;cover=350+math.hypot(*tower_xy)
 K=math.ceil(cover/(math.sqrt(3)/2*step))+1
 ux,uy=step*math.cos(phi),step*math.sin(phi);vx,vy=step*math.cos(phi+math.pi/3),step*math.sin(phi+math.pi/3)
 mirrors=[];outside=excluded=0
 for k,s,j,a,b in lattice_rows(K):
  x=tower_xy[0]+a*ux+b*vx;y=tower_xy[1]+a*uy+b*vy
  if math.hypot(x,y)>350:outside+=1;continue
  if math.hypot(x-tower_xy[0],y-tower_xy[1])<100:excluded+=1;continue
  key=json.dumps(['hex-band',k,s,j],separators=(',',':'))
  mid=int.from_bytes(hashlib.sha256(key.encode()).digest()[:6],'big')
  mirrors.append({'mirror_id':mid,'position_key':key,'x':x,'y':y})
 metadata={'generator':'six-sector-straight-edge-bands-v001','spec':dict(tower_xy=tower_xy,width=width,height=height,installation_height=installation_height,phi=phi,spacing_margin=spacing_margin),'step_m':step,'layer_limit':K,'scope':'common translation/rotation/step and deterministic center clipping; no per-point retention optimization','proof':'integer triangular basis squared distance step^2(a^2+ab+b^2); full coordinates independently checked'}
 des=d.Design(name,version,tuple(tower_xy),width,height,installation_height,mirrors,metadata)
 return des,{'nominal_slots':3*K*(K+1),'outside_field':outside,'excluded_tower':excluded,'actual_n':len(mirrors),'generator':metadata}

def run_tests():
 checks={}
 for K,expected in [(1,6),(2,18),(3,36)]:
  rows=list(lattice_rows(K));points=[(a,b)for k,s,j,a,b in rows]
  ds=[(a-c)**2+(a-c)*(b-e)+(b-e)**2 for i,(a,b)in enumerate(points)for c,e in points[i+1:]]
  checks['shells_%d'%K]=len(rows)==expected and len(set(points))==expected and min(ds)==1
 checks['six_sector_boundary_unique']=len(set((a,b)for k,s,j,a,b in lattice_rows(4)))==60
 return {'checks':checks,'all_pass':all(checks.values()),'scope':'independent exact integer small lattice identities; no optics; final floating geometry separately required'}
