"""Reassemble both CPUs against a frozen, already compiled asset pack."""
import argparse,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from build import command
from sa1_layout import worker_layout,worker_symbols,worker_config

def rebuild(out):
    out=Path(out).resolve()
    def cpu():
        subprocess.run([sys.executable,str(ROOT/'build_campaign.py'),'--pack','master','--out',str(out),'--skip-assets'],cwd=ROOT,check=True)
    cpu()
    (out/'sa1_layout.inc').write_text(worker_layout((ROOT/'src/campaign.s').read_text()))
    symbols=worker_symbols((out/'adofai.lbl').read_text())
    (out/'sa1_symbols.inc').write_text(symbols)
    (out/'sa1_worker.cfg').write_text(worker_config())
    subprocess.run([command('ca65'),'--cpu','65816','-I',str(out),'-I',str(ROOT/'src'),'-g','-o',str(out/'sa1_worker.o'),str(ROOT/'src/sa1_worker.s')],check=True)
    subprocess.run([command('ld65'),'-C',str(out/'sa1_worker.cfg'),'-o',str(out/'sa1_worker.bin'),'-Ln',str(out/'sa1_worker.lbl'),str(out/'sa1_worker.o')],check=True)
    cpu()
    assert symbols==worker_symbols((out/'adofai.lbl').read_text()),'Worker ABI moved during the final link'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--out',type=Path,required=True)
    rebuild(p.parse_args().out)
