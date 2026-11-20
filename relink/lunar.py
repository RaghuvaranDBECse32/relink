"""Lunar Sun/Earth geometry for the Link Planner.

Method (documented in docs/METHODS.md):
  * Sun: low-precision solar theory (Meeus, Astronomical Algorithms ch.25).
  * Moon: truncated ELP-2000/82 series as tabulated in Meeus ch.47.
  * Lunar body-fixed frame: mean rotation + optical libration (Meeus ch.53 geometry).
    Physical libration (~0.03 deg) is NOT modelled.
  * Horizon: flat horizon plus a user-set uniform mask angle. NOT terrain-aware.
This is NOT JPL SPICE/Horizons output. UTC is used as TT (error ~69 s, negligible here).
"""
from __future__ import annotations
import math
from datetime import datetime, timedelta, timezone
import numpy as np

R_MOON_KM = 1737.4
AU_KM = 149597870.7
R_SUN_KM = 695700.0
I_DEG = 1.54242  # mean inclination of lunar equator to the ecliptic

# (D, M, M', F, sin-coeff 1e-6 deg [longitude], cos-coeff 1e-3 km [distance])
_LR = [
 (0,0,1,0,6288774,-20905355),(2,0,-1,0,1274027,-3699111),(2,0,0,0,658314,-2955968),(0,0,2,0,213618,-569925),
 (0,1,0,0,-185116,48888),(0,0,0,2,-114332,-3149),(2,0,-2,0,58793,246158),(2,-1,-1,0,57066,-152138),
 (2,0,1,0,53322,-170733),(2,-1,0,0,45758,-204586),(0,1,-1,0,-40923,-129620),(1,0,0,0,-34720,108743),
 (0,1,1,0,-30383,104755),(2,0,0,-2,15327,10321),(0,0,1,2,-12528,0),(0,0,1,-2,10980,79661),
 (4,0,-1,0,10675,-34782),(0,0,3,0,10034,-23210),(4,0,-2,0,8548,-21636),(2,1,-1,0,-7888,24208),
 (2,1,0,0,-6766,30824),(1,0,-1,0,-5163,-8379),(1,1,0,0,4987,-16675),(2,-1,1,0,4036,-12831),
 (2,0,2,0,3994,-10445),(4,0,0,0,3861,-11650),(2,0,-3,0,3665,14403),(0,1,-2,0,-2689,-7003),
 (2,0,-1,2,-2602,0),(2,-1,-2,0,2390,10056),(1,0,1,0,-2348,6322),(2,-2,0,0,2236,-9884),
 (0,1,2,0,-2120,5751),(0,2,0,0,-2069,0),(2,-2,-1,0,2048,-4950),(2,0,1,-2,-1773,4130),
 (2,0,0,2,-1595,0),(4,-1,-1,0,1215,0),(0,0,2,2,-1110,0),(3,0,-1,0,-892,0),(2,1,1,0,-810,0),
 (4,-1,-2,0,759,0),(0,2,-1,0,-713,0),(2,2,-1,0,-700,0),(2,1,-2,0,691,0),(2,-1,0,-2,596,0),
 (4,0,1,0,549,0),(0,0,4,0,537,0),(4,-1,0,0,520,0),(1,0,-2,0,-487,0),(2,1,0,-2,-399,0),
 (0,0,2,-2,-381,0),(1,1,1,0,351,0),(3,0,-2,0,-340,0),(4,0,-3,0,330,0),(2,-1,2,0,327,0),
 (0,2,1,0,-323,0),(1,1,-1,0,299,0),(2,0,3,0,294,0)]
_B = [
 (0,0,0,1,5128122),(0,0,1,1,280602),(0,0,1,-1,277693),(2,0,0,-1,173237),(2,0,-1,1,55413),
 (2,0,-1,-1,46271),(2,0,0,1,32573),(0,0,2,1,17198),(2,0,1,-1,9266),(0,0,2,-1,8822),
 (2,-1,0,-1,8216),(2,0,-2,-1,4324),(2,0,1,1,4200),(2,1,0,-1,-3359),(2,-1,-1,1,2463),
 (2,-1,0,1,2211),(2,-1,-1,-1,2065),(0,1,-1,-1,-1870),(4,0,-1,-1,1828),(0,1,0,1,-1794),
 (0,0,0,3,-1749),(0,1,-1,1,-1565),(1,0,0,1,-1491),(0,1,1,1,-1475),(0,1,1,-1,-1410),
 (0,1,0,-1,-1344),(1,0,0,-1,-1335),(0,0,3,1,1107),(4,0,0,-1,1021),(4,0,-1,1,833)]

def _rad(x): return np.radians(x)

def julian_day(dt: datetime) -> float:
    dt = dt.astimezone(timezone.utc)
    y, m = dt.year, dt.month
    d = dt.day + (dt.hour + (dt.minute + (dt.second + dt.microsecond/1e6)/60)/60)/24
    if m <= 2: y -= 1; m += 12
    a = y // 100; b = 2 - a + a // 4
    return int(365.25*(y+4716)) + int(30.6001*(m+1)) + d + b - 1524.5

def moon_ecliptic(jde):
    """Geocentric (lon deg, lat deg, dist km), mean equinox of date."""
    jde = np.atleast_1d(np.asarray(jde, float)); T = (jde-2451545.0)/36525.0
    Lp = (218.3164477+481267.88123421*T-0.0015786*T**2)%360
    D  = (297.8501921+445267.1114034*T-0.0018819*T**2)%360
    M  = (357.5291092+35999.0502909*T-0.0001536*T**2)%360
    Mp = (134.9633964+477198.8675055*T+0.0087414*T**2)%360
    F  = (93.2720950+483202.0175233*T-0.0036539*T**2)%360
    E = 1-0.002516*T-0.0000074*T**2
    A1=(119.75+131.849*T)%360; A2=(53.09+479264.290*T)%360; A3=(313.45+481266.484*T)%360
    sl=np.zeros_like(T); sr=np.zeros_like(T); sb=np.zeros_like(T)
    for d,m,mp,f,cl,cr in _LR:
        arg=_rad(d*D+m*M+mp*Mp+f*F); ef=E**abs(m)
        sl+=cl*ef*np.sin(arg); sr+=cr*ef*np.cos(arg)
    for d,m,mp,f,cb in _B:
        arg=_rad(d*D+m*M+mp*Mp+f*F); sb+=cb*(E**abs(m))*np.sin(arg)
    sl+=3958*np.sin(_rad(A1))+1962*np.sin(_rad(Lp-F))+318*np.sin(_rad(A2))
    sb+=(-2235*np.sin(_rad(Lp))+382*np.sin(_rad(A3))+175*np.sin(_rad(A1-F))+175*np.sin(_rad(A1+F))
         +127*np.sin(_rad(Lp-Mp))-115*np.sin(_rad(Lp+Mp)))
    return (Lp+sl/1e6)%360, sb/1e6, 385000.56+sr/1e3

def sun_ecliptic(jde):
    """Geocentric (lon deg, dist km); low precision (~0.01 deg)."""
    jde = np.atleast_1d(np.asarray(jde, float)); T=(jde-2451545.0)/36525.0
    L0=280.46646+36000.76983*T+0.0003032*T**2; M=(357.52911+35999.05029*T-0.0001537*T**2)%360
    e=0.016708634-0.000042037*T
    C=((1.914602-0.004817*T-0.000014*T**2)*np.sin(_rad(M))+(0.019993-0.000101*T)*np.sin(_rad(2*M))
       +0.000289*np.sin(_rad(3*M)))
    R=1.000001018*(1-e**2)/(1+e*np.cos(_rad(M+C)))
    return (L0+C)%360, R*AU_KM

def _vec(lon, lat, dist):
    lo,la=_rad(lon),_rad(lat)
    return np.stack([dist*np.cos(la)*np.cos(lo), dist*np.cos(la)*np.sin(lo), dist*np.sin(la)],axis=-1)

def _unit(v): return v/np.linalg.norm(v,axis=-1,keepdims=True)

def body_frame(jde):
    """Lunar body-fixed axes (ex toward lon 0/lat 0, ey toward 90E, ez = north pole) in ecliptic coords."""
    jde=np.atleast_1d(np.asarray(jde,float)); T=(jde-2451545.0)/36525.0
    Om=_rad((125.0445479-1934.1362891*T+0.0020754*T**2)%360)
    F=_rad((93.2720950+483202.0175233*T-0.0036539*T**2)%360)
    I=_rad(I_DEG); z=np.zeros_like(T)
    Z=np.stack([-np.sin(Om)*np.sin(I), np.cos(Om)*np.sin(I), np.cos(I)+z],-1)
    N=np.stack([np.cos(Om), np.sin(Om), z],-1)
    M=np.cross(Z,N)
    th=F+math.pi  # mean prime-meridian direction measured from the node in the (N,M) plane
    ex=np.cos(th)[:,None]*N+np.sin(th)[:,None]*M
    ey=np.cross(Z,ex)
    return ex,ey,Z

def sub_earth(jde):
    """Optical libration (l, b) in degrees (selenographic lon east-positive / lat of the sub-Earth point)."""
    lon,lat,dist=moon_ecliptic(jde); ex,ey,ez=body_frame(jde)
    e=-_unit(_vec(lon,lat,dist))
    l=np.degrees(np.arctan2((e*ey).sum(-1),(e*ex).sum(-1)))
    b=np.degrees(np.arcsin(np.clip((e*ez).sum(-1),-1,1)))
    return l,b

def site_geometry(jde, lat_deg, lon_deg):
    """Elevation/azimuth (deg) of Sun and Earth centres at a lunar surface site (flat horizon)."""
    jde=np.atleast_1d(np.asarray(jde,float))
    mlon,mlat,mdist=moon_ecliptic(jde); slon,sdist=sun_ecliptic(jde)
    ex,ey,ez=body_frame(jde)
    rm=_vec(mlon,mlat,mdist); rs=_vec(slon,np.zeros_like(slon),sdist)
    to_earth=-rm; to_sun=rs-rm
    la,lo=math.radians(lat_deg),math.radians(lon_deg)
    n=(math.cos(la)*math.cos(lo))*ex+(math.cos(la)*math.sin(lo))*ey+math.sin(la)*ez
    east=(-math.sin(lo))*ex+math.cos(lo)*ey
    north=(-math.sin(la)*math.cos(lo))*ex+(-math.sin(la)*math.sin(lo))*ey+math.cos(la)*ez
    out={}
    for name,vec in (("sun",to_sun),("earth",to_earth)):
        u=_unit(vec-R_MOON_KM*n)
        el=np.degrees(np.arcsin(np.clip((u*n).sum(-1),-1,1)))
        az=np.degrees(np.arctan2((u*east).sum(-1),(u*north).sum(-1)))%360
        out[name]=(el,az)
    out["sun_semidiameter_deg"]=np.degrees(np.arcsin(R_SUN_KM/np.linalg.norm(to_sun,axis=-1)))
    return out

def elongation_deg(jde):
    mlon,mlat,_=moon_ecliptic(jde); slon,_=sun_ecliptic(jde)
    c=np.cos(_rad(mlat))*np.cos(_rad(mlon-slon)); return np.degrees(np.arccos(np.clip(c,-1,1)))

def _windows(times, mask):
    wins=[]; start=None
    for i,v in enumerate(mask):
        if v and start is None: start=i
        if (not v) and start is not None: wins.append((start,i-1)); start=None
    if start is not None: wins.append((start,len(mask)-1))
    return [{"start":times[a].isoformat(),"end":times[b].isoformat(),
             "hours":round((times[b]-times[a]).total_seconds()/3600,2)} for a,b in wins]

def analyse_site(name, lat, lon, start: datetime, hours: float, step_min: float, mask_deg: float = 0.0):
    if not (-90<=lat<=90 and -180<=lon<=360): raise ValueError("latitude/longitude out of range")
    if not (0<hours<=24*60): raise ValueError("hours must be in (0, 1440]")
    if not (1<=step_min<=720): raise ValueError("step_min must be in [1, 720]")
    if not (0<=mask_deg<=30): raise ValueError("mask_deg must be in [0, 30]")
    n=int(hours*60/step_min)+1
    if n>6000: raise ValueError("too many samples; increase step_min or reduce hours")
    times=[start+timedelta(minutes=step_min*i) for i in range(n)]
    jde=np.array([julian_day(t) for t in times])
    g=site_geometry(jde,lat,lon)
    sun_el,sun_az=g["sun"]; ea_el,ea_az=g["earth"]
    sun_up=(sun_el+g["sun_semidiameter_deg"])>mask_deg   # upper limb above mask
    earth_up=ea_el>mask_deg                              # Earth centre above mask
    dt_h=step_min/60
    def stats(m): return {"hours_visible":round(float(m.sum())*dt_h,2),"fraction":round(float(m.mean()),4)}
    rel=np.where(sun_up,np.sin(np.radians(np.maximum(sun_el,0))),0.0)
    return {
      "site":{"name":name,"latitude":lat,"longitude":lon},
      "sun":stats(sun_up),"earth":stats(earth_up),"both":stats(sun_up&earth_up),
      "mean_relative_insolation_horizontal_panel":round(float(rel.mean()),5),
      "sun_windows":_windows(times,sun_up),"earth_windows":_windows(times,earth_up),
      "series":{"t":[t.isoformat() for t in times],
                "sun_el":np.round(sun_el,3).tolist(),"sun_az":np.round(sun_az,2).tolist(),
                "earth_el":np.round(ea_el,3).tolist(),"earth_az":np.round(ea_az,2).tolist()}}

LIMITATIONS=[
 "Flat horizon with a uniform mask angle: real terrain (LOLA DEM) is not modelled, so local shadowing and crater-rim obscuration are not captured.",
 "Earth 'visibility' is geometric line-of-sight to the Earth's centre only; it does not prove a radio link (antenna, power, link budget, terrain, operations).",
 "Ephemerides are analytic series (Sun: Meeus ch.25; Moon: Meeus ch.47; libration good to roughly 0.05 deg), not JPL SPICE/Horizons. Physical libration is omitted.",
 "Insolation is a unit-less geometric proxy (sin of elevation), not watts; it ignores panel orientation, terrain shadows and partial Sun-disk occultation.",
 "IMPORTANT: crater-floor candidates (Shackleton, Haworth, Shoemaker, Faustini, de Gerlache, Cabeus) contain permanently shadowed regions. A flat horizon ignores the crater walls, so it OVERSTATES sunlight there; use rim/massif sites or add real terrain before drawing conclusions.",
 "Candidate-site coordinates are approximate crater-centre values for demonstration, not official landing-site selections."]

SITES=[
 {"name":"Shackleton (approx. centre)","latitude":-89.9,"longitude":0.0},
 {"name":"Haworth (approx.)","latitude":-87.5,"longitude":-5.0},
 {"name":"Malapert Massif (approx.)","latitude":-85.9,"longitude":0.0},
 {"name":"Faustini (approx.)","latitude":-87.3,"longitude":77.0},
 {"name":"Shoemaker (approx.)","latitude":-88.1,"longitude":44.9},
 {"name":"de Gerlache (approx.)","latitude":-88.5,"longitude":-87.1},
 {"name":"Cabeus (approx.)","latitude":-84.9,"longitude":-35.5},
 {"name":"Nobile (approx.)","latitude":-85.2,"longitude":53.3}]
