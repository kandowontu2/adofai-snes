"""Small-screen presentation adjustments for the playable Overclocked beta."""
from pathlib import Path
import numpy as np
from PIL import Image


def title_actions(actions):
    result=[];headings={'game','game2','game3'}
    for event in actions:
        event=dict(event)
        if event.get('tag') in headings:
            if event['eventType']=='SetText':event['decText']=event['decText'].removeprefix('+ ')
            if event['eventType']=='MoveDecorations' and 'positionOffset' in event:
                x,y=event['positionOffset'];event['positionOffset']=[0 if x is not None else None,y]
        result.append(event)
        if event['eventType']=='SetText' and event.get('tag') in headings and event.get('decText'):
            # Clear the images rather than merely fading them: later paired
            # opacity/position effects must not resurrect the retired title.
            for tag in sorted(headings-{event['tag']}):
                result.append(dict(floor=event['floor'],eventType='SetText',tag=tag,
                                   decText='',angleOffset=event.get('angleOffset',0),
                                   active=event.get('active',True),eventTag=event.get('eventTag','')))
    return result


def shortcut_image(name):
    """Render editable CHR symbols at the shortcut tile's native pixel size."""
    raw=(Path(__file__).resolve().parents[1]/'assets/graphics/campaign/shortcut-symbols.chr').read_bytes()
    tile=0 if name=='triangle.png' else 1
    image=np.zeros((14,24,4),dtype=np.uint8)
    image[:]=[0,0,0,255]
    image[1:-1,1:-1]=[255,152,152,255] if tile==0 else [152,255,180,255]
    for y in range(8):
        for x in range(8):
            value=sum(((raw[tile*16+y*2+plane]>>(7-x))&1)<<plane for plane in range(2))
            if value:image[y+3,x+8]=[0,0,0,255] if value==1 else [255,255,255,255]
    return np.asarray(Image.fromarray(image).resize((345,197),Image.Resampling.NEAREST))
