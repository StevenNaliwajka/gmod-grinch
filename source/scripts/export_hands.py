# blender -b grinch.blend --python export_hands.py -- <player skeleton.json> <c_arms skeleton.json> <outdir>
# First-person hands: the sleeves and hands of the player model, moved from the player
# bind pose into the c_arms bind pose bone by bone (linear blend), with c_arms' skeleton.
import bpy, json, os, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
ps = {b['name']: b for b in json.load(open(argv[0]))}
cs_all = json.load(open(argv[1]))
OUT = argv[2]
cs = [b for b in cs_all if not b['name'].endswith(('Ulna', 'Wrist'))]
keep = {b['name'] for b in cs}
assert all(cs_all[b['parent']]['name'] in keep for b in cs if b['parent'] >= 0)
cidx = {b['name']: i for i, b in enumerate(cs)}
old2new = {i: cidx[b['name']] for i, b in enumerate(cs_all) if b['name'] in cidx}

def m4(b):
    R = b['wR']; t = b['wt']
    return Matrix(((R[0][0], R[0][1], R[0][2], t[0]), (R[1][0], R[1][1], R[1][2], t[1]),
                   (R[2][0], R[2][1], R[2][2], t[2]), (0, 0, 0, 1)))
X = {n: m4(cs_all[[b['name'] for b in cs_all].index(n)]) @ m4(ps[n]).inverted() for n in keep}

PARTS = ('sleeve_', 'wrist_', 'palm_', 'finger_')
os.makedirs(OUT, exist_ok=True)
with open(os.path.join(OUT, 'arms_ref.smd'), 'w') as f:
    f.write('version 1\nnodes\n')
    for i, b in enumerate(cs):
        p = old2new[b['parent']] if b['parent'] >= 0 else -1
        f.write(f'{i} "{b["name"]}" {p}\n')
    f.write('end\nskeleton\ntime 0\n')
    for i, b in enumerate(cs):
        p, r = b['pos'], b['rot']
        f.write(f'{i} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f} {r[0]:.6f} {r[1]:.6f} {r[2]:.6f}\n')
    f.write('end\ntriangles\n')
    n = 0
    for ob in bpy.data.objects:
        if ob.type != 'MESH' or not ob.name.startswith(PARTS):
            continue
        me = ob.data; me.calc_loop_triangles(); cn = me.corner_normals
        gname = {g.index: g.name for g in ob.vertex_groups}
        out = ob.get('outline', 0.0)
        vn = [Vector() for _ in me.vertices]
        for tri in me.loop_triangles:
            for li, vi in zip(tri.loops, tri.vertices):
                vn[vi] += cn[li].vector
        vn = [v.normalized() for v in vn]
        L = []
        for v in me.vertices:
            l = sorted(((gname[g.group], g.weight) for g in v.groups if g.weight > 0.001), key=lambda x: -x[1])[:3]
            t = sum(w for _, w in l); L.append([(nm, w / t) for nm, w in l])
        def xf(vi, co, nrm):
            M = sum((X[nm] * w for nm, w in L[vi]), Matrix(((0,) * 4,) * 4))
            return M @ co, (M.to_3x3() @ nrm).normalized()
        def line(vi, co, nrm):
            c, nn = xf(vi, co, nrm)
            s = ' '.join(f'{cidx[nm]} {w:.6f}' for nm, w in L[vi])
            return f'0 {c.x:.6f} {c.y:.6f} {c.z:.6f} {nn.x:.6f} {nn.y:.6f} {nn.z:.6f} 0.5 0.5 {len(L[vi])} {s}\n'
        for tri in me.loop_triangles:
            f.write(me.materials[0].name + '\n')
            for li, vi in zip(tri.loops, tri.vertices):
                f.write(line(vi, me.vertices[vi].co, cn[li].vector))
            n += 1
            if out > 0:
                f.write('grinch_outline\n')
                for vi in reversed(tri.vertices):
                    f.write(line(vi, me.vertices[vi].co + vn[vi] * out * 0.6, -vn[vi]))
                n += 1
    f.write('end\n')
open(os.path.join(OUT, 'c_arms_grinch.qc'), 'w').write('''$modelname "weapons/burrito/c_arms_grinch.mdl"
$model "arms" "arms_ref.smd"
$cdmaterials "models/player/burrito/grinch_ultimatum/"
$surfaceprop "default"
$contents "solid"
$includemodel "weapons/c_arms_animations.mdl"
$sequence "ragdoll" "arms_ref.smd" activity "ACT_DIERAGDOLL" 1 fps 30
''')
print('hands triangles', n)
