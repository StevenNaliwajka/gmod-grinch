import struct, sys, json
def cstr(d,o):
    return d[o:d.index(b'\0',o)].decode()
def meta(path):
    d=open(path,'rb').read()
    r={}
    r['eyepos']=struct.unpack_from('<3f',d,80); r['illum']=struct.unpack_from('<3f',d,92)
    r['hull']=struct.unpack_from('<6f',d,104); r['view']=struct.unpack_from('<6f',d,128)
    r['flags']=struct.unpack_from('<i',d,152)[0]
    nb,bi=struct.unpack_from('<ii',d,156)
    bones=[cstr(d,bi+i*216+struct.unpack_from('<i',d,bi+i*216)[0]) for i in range(nb)]
    nhs,hsi=struct.unpack_from('<ii',d,172)
    sets=[]
    for s in range(nhs):
        o=hsi+s*12; ni,nh,hi=struct.unpack_from('<iii',d,o)
        boxes=[]
        for h in range(nh):
            b=o+hi+h*68; bone,grp=struct.unpack_from('<ii',d,b); mn=struct.unpack_from('<3f',d,b+8); mx=struct.unpack_from('<3f',d,b+20)
            boxes.append(dict(bone=bones[bone],group=grp,min=mn,max=mx))
        sets.append(dict(name=cstr(d,o+ni),boxes=boxes))
    r['hitboxsets']=sets
    na,ai=struct.unpack_from('<ii',d,240)
    atts=[]
    for a in range(na):
        o=ai+a*92; ni,fl,lb=struct.unpack_from('<iii',d,o); m=struct.unpack_from('<12f',d,o+12)
        atts.append(dict(name=cstr(d,o+ni),flags=fl,bone=bones[lb],m=m))
    r['attachments']=atts
    r['surfaceprop']=cstr(d,struct.unpack_from('<i',d,308)[0])
    r['mass'],r['contents']=struct.unpack_from('<fi',d,328)
    ni,ii=struct.unpack_from('<ii',d,336)
    r['includes']=[cstr(d,ii+k*8+struct.unpack_from('<i',d,ii+k*8+4)[0]) for k in range(ni)]
    nik,iki=struct.unpack_from('<ii',d,284)
    iks=[]
    for k in range(nik):
        o=iki+k*16; ni,lt,nl,li=struct.unpack_from('<iiii',d,o)
        links=[]
        for l in range(nl):
            lo=o+li+l*28; bone=struct.unpack_from('<i',d,lo)[0]; kd=struct.unpack_from('<3f',d,lo+4); links.append(dict(bone=bones[bone],knee=kd))
        iks.append(dict(name=cstr(d,o+ni),links=links))
    r['ikchains']=iks
    return r
if __name__=='__main__':
    m=meta(sys.argv[1]); print(json.dumps(m,indent=1)[:6000]); json.dump(m,open(sys.argv[2],'w'))
