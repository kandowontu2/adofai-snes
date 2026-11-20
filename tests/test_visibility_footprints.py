"""Large animated floors retain their pixels with bounded spatial indexing."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from projected_tracks import Source
from track_visibility import animated_track


class FootprintIndexTests(unittest.TestCase):
    def test_clipping_candidate_index_preserves_every_sampled_pixel(self):
        base=dict(id=20,code='TEST',mode7=True,full_snapshot_source=True,notes=[
            dict(x=72+24*i,y=72,frame=20*i,time=i/3,speed=1,entry_angle=3.14159,
                 exit_angle=0,spin_kind='normal') for i in range(3)],steps=2,last_frame=40,
            motion_bounds=[300,300],render_viewports={0:[0,0,32,24],10:[0,0,34,24]},render_transforms={},
            viewport_center_y=104,viewport_top=16,viewport_bottom=176,
            precise_viewport_cells=True,readability_detail_starts=[0]*3,
            camera_follow_versions=[[0,0,0],[10,8,0]],camera_rotation_versions=[[0,256,0]],
            camera_sampling_versions=[[0,256,0]],camera_world_sampling_versions=[[0,256,0]])
        data=dict(id=20,code='TEST',bpm=120,track_settings=dict(trackColor='ffffff'),track_actions=[
            dict(floor=0,eventType='MoveTrack',startTile=[0,'Start'],endTile=[0,'Start'],
                 scale=[1500,1500],duration=.2)])
        images=[]
        for clip,scope in ((False,False),(True,False),(False,True),(True,True)):
            chart=copy.deepcopy(base);chart['index_render_viewports']=clip;chart['scope_precise_dirty']=scope
            with tempfile.TemporaryDirectory() as directory:
                folder=Path(directory)
                patterns,mapping,timeline=animated_track(chart,[3]*3,{},
                    motion={0:{0:(0,0)},10:{0:(8,0)},15:{0:(16,8)}},color_data=data)
                patterns=chart.pop('_pattern_data',patterns)
                for name,blob in [('patterns',patterns),('track_map',mapping),('timeline',timeline)]:
                    (folder/f'{name}20.bin').write_bytes(blob)
                (folder/'level20.json').write_text(json.dumps(chart))
                source=Source(folder,20)
                images.append([source.screen(frame).copy() for frame in (0,5,10,15,30)])
        self.assertTrue(any(image.any() for image in images[0]))
        for group in images[1:]:
            for left,right in zip(images[0],group):np.testing.assert_array_equal(left,right)
