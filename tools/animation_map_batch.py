"""Merge adjacent map writes into one SA-1 transfer, preserving write order."""
import struct
from animation_bulk import HEADER, records

def batch(data, chart):
    rows=list(records(data));out=bytearray();mapping={};j=0
    while j<len(rows):
        row=rows[j];start=j;cells=[]
        while j<len(rows) and rows[j][2]==row[2] and rows[j][3] in (0,9,29):
            p,e,t,k,i,v=rows[j]
            if k==0:
                x,y=chart['cell_coordinates'][i];part=[(i,(y&127)*128+(x&127),v)]
            elif k==9:
                x,y=struct.unpack_from('<HH',data,p+7)
                part=[(i+n,(y&127)*128+((x+n)&127),value) for n,value in enumerate(data[p+11:e])]
            else:
                part=[struct.unpack_from('<HHB',data,p+7+5*n) for n in range(i)]
            if len(cells)+len(part)>128:break
            cells.extend(part);j+=1
        if j-start>=2:
            for r in rows[start:j]:mapping[r[0]]=len(out)
            payload=b''.join(struct.pack('<HHB',*c) for c in cells)
            out+=HEADER.pack(row[2],29,len(cells),len(payload))+payload
        else:
            j=start+1;mapping[row[0]]=len(out);out+=data[row[0]:row[1]]
    return bytes(out),mapping
