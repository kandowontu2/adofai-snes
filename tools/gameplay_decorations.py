"""Separate authored gameplay replacements from optional scene decoration.

Keep the decision shared by normal imports, VFX variants and future standalone
imports. Masks and interactive objects must survive the VFX switch.
"""
import re
from track_motion import enabled

_PIECES=re.compile(r'(?:tile(?!able)|tileable[ _-]+(?:football|soccer)[ _-]+field|floor|platform|portal|midspin|hold|release|twirl|rabbit|snail|'
                   r'checkpoint|connector|indicator|question|answer|keyboard|meteor|'
                   r'deathbar|laser|warning|obstacle|banana|coin|startrigger|hearttrigger)',re.I)


def is_scripted_planet(dec):
    """Recognize native planets and exported, independently animated bodies.

    The exported-body convention uses a color-export image and b/bN actor
    tags. Numbered 1ball/2ball/4ball sheets are separate tile-count cues.
    """
    if dec.get('eventType')=='AddObject' and dec.get('objectType')=='Planet':return True
    image=dec.get('decorationImage','').replace('\\','/').rsplit('/',1)[-1]
    tags=dec.get('tag','').split()
    if (re.fullmatch(r'(?:red|blue|green|yellow)-export\.png',image,re.I)
            and any(re.fullmatch(r'b\d*',tag) for tag in tags)):return True
    return False


def is_gameplay(dec,chart=None):
    if is_scripted_planet(dec):return True
    if re.fullmatch(r'(?:simple)?[1-8]ball\d*\.png',dec.get('decorationImage','').replace('\\','/').rsplit('/',1)[-1],re.I):return True
    if dec.get('maskingType')=='Mask':return True
    kind=dec.get('eventType')
    if kind in ('AddObject','AddText'):return True
    if dec.get('relativeTo') in ('RedPlanet','BluePlanet','GreenPlanet'):return True
    if dec.get('hitbox','None')!='None' or enabled(dec.get('failHitbox',False)):return True
    if any(re.fullmatch(r'(?:input|gameplay|note|floor|tile|counter)\d*',tag,re.I)
           for tag in dec.get('tag','').split()):
        return True
    name=dec.get('decorationImage','')
    if chart and (name in chart.get('decoration_gameplay_images',[]) or
                  name in chart.get('decoration_required_images',[])):return True
    if re.search(r'(?:background|particle|bloom|vignette|texture|curtain|rainbow|blur|spotlight|(?:^|[_ -])bg(?:[_ .\d-]|$))',name,re.I):return False
    return bool(_PIECES.search(name))


def has_replacements(data):
    return any(d.get('eventType')=='AddObject' and d.get('objectType') in ('Floor','Planet')
               or d.get('eventType')=='AddDecoration' and is_gameplay(d)
               for d in data.get('featured_decorations',[]))


def simple_planet_proxies(data):
    if data.get('_core_planets_only') or data.get('live_planet_proxies'):return False
    if not any(a.get('eventType')=='ScalePlanets' and a.get('targetPlanet') in ('All','Both') and a.get('scale')==0
               for a in data.get('featured_actions',[])):return False
    bodies=[d for d in data.get('featured_decorations',[]) if d.get('relativeTo') in ('RedPlanet','BluePlanet')
            and (d.get('objectType')=='Planet' or re.search(r'(?:circle|planet|orb|ball)',d.get('decorationImage',''),re.I))]
    if {d['relativeTo'] for d in bodies}!={'RedPlanet','BluePlanet'}:return False
    tags={t for d in bodies for t in d.get('tag','').split()}
    for d in bodies:
        if any(any(v not in (0,None) for v in (d.get(k) or (0,0))) for k in ('position','pivotOffset','parallaxOffset')):return False
        parallax=d.get('parallax',(0,0))
        if isinstance(parallax,(int,float)):parallax=[parallax,parallax]
        if any(parallax):return False
    return not any(set(a.get('tag','').split()) & tags and
                   any(any(v not in (0,None) for v in (a.get(k) or (0,0))) for k in ('positionOffset','parallaxOffset'))
                   for a in data.get('featured_actions',[]) if a.get('eventType')=='MoveDecorations')
