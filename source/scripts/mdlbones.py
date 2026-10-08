import struct, math, sys, json
def quat_to_mat(q):
    x,y,z,w=q
    return [[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w)],
            [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w)],
            [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y)]]
def read_bones(path):
    d=open(path,'rb').read()
    numbones,boneindex=struct.unpack_from('<ii',d,156)
    bones=[]
    for i in range(numbones):
        o=boneindex+i*216
        nameidx,parent=struct.unpack_from('<ii',d,o)
        pos=struct.unpack_from('<3f',d,o+32)
        quat=struct.unpack_from('<4f',d,o+44)
        rot=struct.unpack_from('<3f',d,o+60)
        flags=struct.unpack_from('<i',d,o+160)[0]
        e=d.index(b'\0',o+nameidx); name=d[o+nameidx:e].decode()
        bones.append(dict(name=name,parent=parent,pos=pos,quat=quat,rot=rot,flags=flags))
    # world transforms
    for b in bones:
        R=quat_to_mat(b['quat']); t=list(b['pos'])
        if b['parent']>=0:
            P=bones[b['parent']]
            PR,Pt=P['wR'],P['wt']
            R=[[sum(PR[i][k]*R[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
            t=[sum(PR[i][k]*t[k] for k in range(3))+Pt[i] for i in range(3)]
        b['wR'],b['wt']=R,t
    return bones
if __name__=='__main__':
    bs=read_bones(sys.argv[1])
    for i,b in enumerate(bs[:12]): print(i,b['name'],b['parent'],[round(v,2) for v in b['wt']],[round(v,3) for v in b['rot']])
    json.dump([{k:b[k] for k in ('name','parent','pos','quat','rot','wR','wt')} for b in bs],open(sys.argv[2],'w'))
    print(len(bs))
