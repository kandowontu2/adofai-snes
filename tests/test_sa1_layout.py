import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from sa1_layout import HOT_NAMES,PRIVATE_NAMES,worker_layout,worker_symbols


class WorkerLayout(unittest.TestCase):
    def test_private_words_preserve_aliases_and_leave_the_stack_free(self):
        rows=[f'al {0x1800+2*i:06X} .{name}' for i,name in enumerate(HOT_NAMES)]
        rows+=['al 001802 .m7_upload_slots','al 000010 .selected_level','al 001900 .unrelated']
        values={name:int(value,16) for name,value in re.findall(r'(\w+) = \$([0-9A-F]+)',worker_symbols('\n'.join(rows)))}
        self.assertEqual(values['pattern_slot'],values['m7_upload_slots'])
        self.assertEqual(values['selected_level'],0x10)
        self.assertEqual(values['unrelated'],0x1900)
        self.assertEqual(set(values[name] for name in HOT_NAMES),set(range(0x700,0x714,2)))
        self.assertLess(max(values[name] for name in HOT_NAMES)+2,0x780)

    def test_worker_uses_its_internal_ram_mailbox(self):
        source='M7_CACHE_READY=M7_SHARED_BASE+$FC46\n'+'\n'.join(n+'=$410000' for n in PRIVATE_NAMES)
        source+='\n'+'\n'.join(n+'=$410000' for n in ('M7_PATTERN_SELECTED','M7_NEW_VISIBLE','M7_OLD_VISIBLE','M7_LOGICAL_TO_PPU','M7_RESIDENT_HASH'))
        text=worker_layout(source+'\n.segment "ZEROPAGE"\nignored')
        self.assertIn('M7_CACHE_READY=$000784',text)
        self.assertNotIn('ignored',text)


if __name__=='__main__':unittest.main()
