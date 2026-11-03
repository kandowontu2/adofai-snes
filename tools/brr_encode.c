/* Greedy, closed-loop BRR encoder. Input/output are raw little-endian PCM16/BRR.
 * Every candidate is decoded exactly as the DSP before comparing its error.
 * Compile: gcc -O3 tools/brr_encode.c -lm -o .tools/brr_encode.exe
 */
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <math.h>
#include <float.h>

static int predict(int f, int p, int q) {
    if(f==1) return p + ((-p)>>4);
    if(f==2) return p*2 + ((-p*3)>>5) - q + (q>>4);
    if(f==3) return p*2 + ((-p*13)>>6) - q + ((q*3)>>4);
    return 0;
}
int main(int argc,char**argv) {
    if(argc!=3 && argc!=4) return 1;
    FILE *in=fopen(argv[1],"rb"), *out=fopen(argv[2],"wb");
    if(!in || !out) return 2;
    int16_t pcm[16]; int p=0,q=0; unsigned block=0,next_seek=~0u;
    FILE *seeks=argc==4?fopen(argv[3],"r"):NULL;
    if(seeks && fscanf(seeks,"%u",&next_seek)!=1)next_seek=~0u;
    while(1) {
        size_t n=fread(pcm,2,16,in); if(!n) break;
        for(size_t i=n;i<16;i++) pcm[i]=0;
        double best=DBL_MAX; int bp=0,bq=0,bs=0,bf=0,bn[16];
        int seek=block==next_seek;
        if(seek && fscanf(seeks,"%u",&next_seek)!=1)next_seek=~0u;
        /* A seek entry must decode identically with an empty DSP history. */
        for(int f=0;f<(seek?1:4);f++) for(int s=0;s<13;s++) {
            int cp=p,cq=q,ns[16]; double err=0; double scale=(1<<s)*0.5;
            for(int i=0;i<16;i++) {
                int pred=predict(f,cp,cq);
                int v=(int)lround(((pcm[i]>>1)-pred)/scale);
                if(v>7)v=7; if(v< -8)v=-8;
                int r=((v*(1<<s))>>1)+pred;
                if(r>32767)r=32767; if(r< -32768)r=-32768;
                r=(int16_t)(r*2); r>>=1;
                double delta=(pcm[i]>>1)-r;
                err+=delta*delta; cq=cp; cp=r; ns[i]=v&15;
            }
            if(err<best) {
                best=err; bp=cp; bq=cq; bs=s; bf=f;
                for(int i=0;i<16;i++) bn[i]=ns[i];
            }
        }
        /* 3640 BRR blocks form the SPC700's circular streaming buffer. */
        fputc((bs<<4)|(bf<<2)|((block%3640==3639)?3:0),out);
        for(int i=0;i<16;i+=2) fputc((bn[i]<<4)|bn[i+1],out);
        p=bp; q=bq; block++;
    }
    fclose(in); fclose(out); if(seeks)fclose(seeks); printf("Encoded %u BRR blocks (%u bytes).\n",block,block*9);
    return 0;
}
