import numpy as np, sys
a=np.fromfile(sys.argv[1],np.float32).astype(float); b=np.fromfile(sys.argv[2],np.float32).astype(float)
n=min(len(a),len(b)); a,b=a[:n],b[:n]; d=a-b
def db(x): return 20*np.log10(max(x,1e-30))
print("samples",n,"max|diff| %.3g"%abs(d).max(),"SNR %.1f dB"%(db(np.sqrt((a**2).mean()))-db(np.sqrt((d**2).mean()))))
seg=int(0.25*44100)
for i in range(0,n-seg+1,seg):
    s=slice(i,i+seg); ra=np.sqrt((a[s]**2).mean()); rd=np.sqrt((d[s]**2).mean())
    # magnitude-spectrum difference (phase-blind)
    A=np.abs(np.fft.rfft(a[s]*np.hanning(seg))); B=np.abs(np.fft.rfft(b[s]*np.hanning(seg)))
    sd=np.sqrt(((A-B)**2).sum()/max((A**2).sum(),1e-30))
    print("%5.2fs  rms %.4f  diff %.2e  SNR %6.1f dB  spectral %6.1f dB"%(i/44100,ra,rd,db(ra)-db(rd) if ra>0 else 0, db(sd)))
