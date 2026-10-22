"""Trusted, finite CPU benchmark: generated fixtures, no training, imports, network or external datasets."""
import hashlib
import json
import math
import random
import sys
from pathlib import Path

GENERATOR_VERSION="smooth-images-1"


def image(seed, sample_id, side, noise_std):
    rng=random.Random(f"{GENERATOR_VERSION}:{seed}:{sample_id}")
    phase=rng.random()*math.pi
    clean=[0.5+0.2*math.sin(x/side*math.pi+phase)+0.15*math.cos(y/side*math.pi-phase) for y in range(side) for x in range(side)]
    noisy=[min(1,max(0,v+rng.gauss(0,noise_std))) for v in clean]
    return clean,noisy


def predict(noisy,side,alpha):
    if alpha==0:return list(noisy)
    out=[]
    for y in range(side):
        for x in range(side):
            values=[noisy[yy*side+xx] for yy in range(max(0,y-1),min(side,y+2)) for xx in range(max(0,x-1),min(side,x+2))]
            out.append((1-alpha)*noisy[y*side+x]+alpha*sum(values)/len(values))
    return out


def metrics(clean,predicted):
    mse=sum((a-b)**2 for a,b in zip(clean,predicted))/len(clean)
    if not math.isfinite(mse) or mse<=0:raise ValueError("Invalid/nonfinite fixture metric")
    return {"mse":mse,"psnr_db":10*math.log10(1/mse)}


def execute(request):
    recipe=request["recipe"];side=recipe["side"]
    rows=[]
    count=recipe[request["split"]+"_count"]
    for seed in request["seeds"]:
        for i in range(count):
            sample_id=request["split"]+":"+str(i)
            clean,noisy=image(seed,sample_id,side,recipe["noise_std"])
            pred=predict(noisy,side,request["alpha"])
            rows.append({"seed":seed,"sample_id":sample_id,"clean":clean,"noisy":noisy,"predicted":pred,**metrics(clean,pred)})
    return {"generator":GENERATOR_VERSION,"split":request["split"],"alpha":request["alpha"],"observations":rows}


if __name__=="__main__":
    request=json.loads(Path(sys.argv[1]).read_text("utf-8"))
    result=execute(request)
    Path(sys.argv[2]).write_text(json.dumps(result,allow_nan=False,separators=(",",":")),"utf-8")
