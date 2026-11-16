"""Convert timed Neo tap/release requests into real fresh controller edges."""
from itertools import groupby

def chords(events):
    result=[];previous=0
    for frame,group in groupby(sorted(events),key=lambda row:row[0]):
        group=list(group)
        count=sum(bool(row[1]) for row in group)
        available=[1<<i for i in range(6) if not previous&(1<<i)]
        if count>len(available):
            raise ValueError(('More simultaneous fresh buttons than the controller can supply',frame,count))
        mask=sum(available[:count]);previous=mask
        result.append((frame,mask,max(row[2] for row in group)))
    return result
