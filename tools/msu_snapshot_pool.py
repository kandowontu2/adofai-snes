"""Share identical immutable poses across charts and VFX variants.

The runtime already follows 32-bit pose references. This changes only file
placement: every due event, glyph, palette selector and native update survives.
Local render caches remain independently decodable for the pixel oracle.
"""
import hashlib
import shutil
import struct
from animation_bulk import HEADER,records


class SnapshotPool:
    def __init__(self,scratch,*,native_lz4=False):
        self.file=scratch;self.seen={};self.size=0;self.before=0;self.segments=[];self.variants=0;self.directory_saved=0
        self.native_lz4=native_lz4
        self.native_saved=0
        self.variant_cache={};self.reused_variants=0
        self.native_stats=dict(native_raw_bytes=0,native_lz4_bytes=0,native_lz4_blocks=0)

    def write_variant(self,data,index,stream,seeds):
        variant_key=hashlib.sha256(index+hashlib.sha256(stream).digest()+hashlib.sha256(seeds).digest()).digest()
        if variant_key in self.variant_cache:
            self.variants+=1;self.reused_variants+=1
            base,seed_base,pose_bytes=self.variant_cache[variant_key]
            self.before+=pose_bytes;self.directory_saved+=(len(index)//8)*512
            return base,seed_base
        refs={};packets={};visited=set()
        for _,_,choice in list(struct.iter_unpack('<HHI',index))[:-1]:
            for j in range(4):
                _,size,offset=struct.unpack_from('<HHI',stream,choice+j*8)
                offset&=0x0fffffff
                while size:
                    length=size&0x7fff
                    if offset not in visited:
                        visited.add(offset)
                        for a,b,t,k,_,v in records(stream[offset:offset+length]):
                            if k!=42:continue
                            at=offset+a+7;pointer=struct.unpack_from('<I',stream,at)[0]
                            assert packets.setdefault(pointer,v)==v
                            refs[at]=pointer
                    if not size&0x8000:break
                    offset+=length;size=struct.unpack_from('<H',stream,offset)[0];offset+=2
        assert packets,'Snapshot stream has no immutable poses'
        # Full snapshots restore through their exact pose references. The
        # legacy directory's 512-byte Mode 7 pattern-tag seed is never read.
        # Retain all four 8-byte choices; relocate every native packet.
        count=len(index)//8;directory=count*544;removed=count*512
        base=data.tell();prefix=bytearray(b''.join(stream[i*544:i*544+32] for i in range(count)))
        prefix+=stream[directory:min(packets)];mapping={}
        for i in range(count):
            for j in range(4):
                at=i*32+j*8
                _,size,offset=struct.unpack_from('<HHI',prefix,at)
                if not size:continue
                target=offset&0x0fffffff
                assert directory<=target<min(packets)
                struct.pack_into('<I',prefix,at+4,(offset&0xf0000000)|(target-removed))
        self.directory_saved+=removed
        for pointer,length in sorted(packets.items()):
            packet=stream[pointer:pointer+length]
            assert len(packet)==length and packet[-7:]==HEADER.pack(65535,255,0,0)
            _,kind,_,size=HEADER.unpack_from(packet)
            assert kind in (41,44,45,46,47,48,49) and size+14==length
            # The referencing k42 owns the due time. A shared packet's
            # decoder guard must be due even for another chart's earlier use.
            packet=bytes(2)+packet[2:];key=hashlib.sha256(packet).digest()
            old=self.seen.get(key)
            if old is None:
                old=(self.size,length);self.seen[key]=old
                self.file.seek(self.size);self.file.write(packet);self.size+=length
                assert self.size<2**32,('Screen poses exceed MSU-1 addressing; run plan_catalog_storage.py on this staged catalog and assemble with --storage-plan',self.size)
            else:
                assert old[1]==length
                self.file.seek(old[0]);assert self.file.read(length)==packet,'Pose hash collision'
            mapping[pointer]=old[0]
        self.before+=len(stream)-min(packets)
        for at,pointer in refs.items():struct.pack_into('<I',prefix,at-removed,mapping[pointer])
        patches=[at-removed for at in refs]
        if self.native_lz4:
            from native_packet_codec import compact_prefix
            original_size=len(prefix)
            prefix,patches,stats=compact_prefix(prefix,count)
            self.native_saved+=original_size-len(prefix)
            for key,value in stats.items():self.native_stats[key]+=value
        self.segments.append((base,base,prefix,patches))
        data.write(prefix);seed_base=data.tell();seed=bytearray(seeds);patches=[]
        count=struct.unpack_from('<I',seed)[0]//4
        for start in struct.unpack_from('<'+str(count)+'I',seed):
            header=struct.unpack_from('<H',seed,start+2)[0]
            at=start+4+(42 if header&0x8000 else 0)
            size,pointer=struct.unpack_from('<HI',seed,at)
            if not size:continue
            assert packets[pointer]==size
            struct.pack_into('<I',seed,at+2,mapping[pointer]);patches.append(at+2)
        self.segments.append((seed_base,base,seed,patches));data.write(seed)
        self.variants+=1
        self.variant_cache[variant_key]=(base,seed_base,len(stream)-min(packets))
        return base,seed_base

    def finish(self,data):
        pool_base=data.tell();end=pool_base+self.size
        assert end<=2**32,('MSU data exceeds 32-bit address capacity',end)
        self.file.seek(0);shutil.copyfileobj(self.file,data,8*1024*1024)
        for at,base,segment,patches in self.segments:
            for p in patches:
                offset=pool_base+struct.unpack_from('<I',segment,p)[0]-base
                assert 0<=offset<2**32
                struct.pack_into('<I',segment,p,offset)
            data.seek(at);data.write(segment)
        data.seek(end)
        return dict(version=4 if self.native_lz4 else 2,native_lz4=self.native_lz4,native_filter_version=2 if self.native_lz4 else 0,
                    **self.native_stats,variants=self.variants,reused_variants=self.reused_variants,pool_base=pool_base,pool_bytes=self.size,
                    unshared_pose_bytes=self.before,directory_saved_bytes=self.directory_saved,
                    native_saved_bytes=self.native_saved,
                    saved_bytes=self.before-self.size+self.directory_saved+self.native_saved,msu_bytes=end)
