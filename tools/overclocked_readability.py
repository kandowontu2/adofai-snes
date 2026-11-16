"""Small-screen presentation adjustments for the playable Overclocked beta."""
from pathlib import Path
import numpy as np
from PIL import Image


def title_actions(actions):
    result=[]
    for event in actions:
        event=dict(event)
        if event['floor']==231 and event.get('tag')=='game2':
            if event['eventType']=='SetText':event['decText']=event['decText'].removeprefix('+ ')
            if event['eventType']=='MoveDecorations' and 'positionOffset' in event:
                event['positionOffset']=[0,event['positionOffset'][1]]
        result.append(event)
    # The original places both long names side by side. At SNES resolution
    # their glyphs overlap; retain the current section's centered title.
    result.append(dict(floor=225,eventType='MoveDecorations',tag='game',duration=0,opacity=0))
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
