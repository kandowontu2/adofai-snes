import bisect,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"tools"))
from track_patterns import cache_patterns,share_palette_patterns

class PatternCache(unittest.TestCase):
    def test_palette_sharing_preserves_colors_and_later_divergence(self):
        tiles=[bytes(64),bytes([32,33])*32,bytes([34,35])*32]
        history={(0,0):[(0,1)],(1,0):[(0,2)]}
        chart=dict(notes=[dict(frame=20)],palette_sharing_threshold=1,track_palette_versions=[
            (0,0,123),(0,1,456),(0,2,123),(0,3,456),(10,2,789)])
        result=share_palette_patterns(chart,tiles,history)
        self.assertEqual(result[0,0][0][1],result[1,0][0][1])
        self.assertEqual(len(result[1,0]),2)
        for frame in range(20):
            palette={32+i:v for f,i,v in chart['track_palette_versions'] if f<=frame}
            for cell,rows in history.items():
                old=next(p for f,p in reversed(rows) if f<=frame)
                new=next(p for f,p in reversed(result[cell]) if f<=frame)
                self.assertEqual([palette[v] for v in tiles[old]],
                                 [palette[v] for v in tiles[new]])

    def test_future_aware_eviction_preserves_every_pixel(self):
        tiles=[bytes([i&255,i>>8])*32 for i in range(601)]
        for cadence,optimal,delta in ((200,False,False),(200,True,False),(200,True,True),(1,True,True)):
            history={cell:[(frame*cadence,1+(frame*70+cell)%600) for frame in range(30)] for cell in range(90)}
            chart=dict(code="TEST",mode7=True,pattern_latency=0,pattern_pinned_limit=8,
                       authored_visibility=True,optimal_pattern_cache=optimal,delta_pattern_cache=delta)
            _,converted=cache_patterns(chart,tiles,history)
            pattern_data=chart["_pattern_data"]
            for cell,rows in converted.items():
                for (frame,slot),(_,raw) in zip(rows,history[cell]):
                    versions=chart["pattern_versions"][slot]
                    index=bisect.bisect_right([t for t,_ in versions],frame)-1
                    pattern=versions[index][1]
                    self.assertEqual(pattern_data[pattern*64:(pattern+1)*64],tiles[raw])
