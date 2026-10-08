# blender -b grinch.blend --python export_smd.py -- <skeleton.json> <meta.json> <phy> <outdir>
# Writes grinch_ref.smd (mesh + cartoon outline shells), grinch_phys.smd (one box per ragdoll bone) and grinch.qc.
import bpy, json, math, os, re, sys
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index('--') + 1:]
skel = json.load(open(argv[0]))
meta = json.load(open(argv[1]))
phy = open(argv[2], 'rb').read()
OUT = argv[3]
os.makedirs(OUT, exist_ok=True)

bones = skel[:56]  # ValveBiped core; the procedural helper bones (Ulna, Bicep, ...) are left out
assert all(b['parent'] < 56 for b in bones)
index = {b['name']: i for i, b in enumerate(bones)}

def header(f):
    f.write('version 1\nnodes\n')
    for i, b in enumerate(bones):
        f.write(f'{i} "{b["name"]}" {b["parent"]}\n')
    f.write('end\nskeleton\ntime 0\n')
    for i, b in enumerate(bones):
        p, r = b['pos'], b['rot']
        f.write(f'{i} {p[0]:.6f} {p[1]:.6f} {p[2]:.6f} {r[0]:.6f} {r[1]:.6f} {r[2]:.6f}\n')
    f.write('end\n')

def vline(co, n, links):
    s = ' '.join(f'{index[b]} {w:.6f}' for b, w in links)
    return f'0 {co.x:.6f} {co.y:.6f} {co.z:.6f} {n.x:.6f} {n.y:.6f} {n.z:.6f} 0.5 0.5 {len(links)} {s}\n'

dominant = {}  # vertex -> dominant bone, for physics
ntri = 0
with open(os.path.join(OUT, 'grinch_ref.smd'), 'w') as f:
    header(f)
    f.write('triangles\n')
    for ob in bpy.data.objects:
        if ob.type != 'MESH':
            continue
        me = ob.data
        me.calc_loop_triangles()
        cn = me.corner_normals
        gname = {g.index: g.name for g in ob.vertex_groups}
        links = []
        for v in me.vertices:
            l = [(gname[g.group], g.weight) for g in v.groups if g.weight > 0.001]
            l.sort(key=lambda x: -x[1])
            l = l[:3]
            t = sum(w for _, w in l)
            links.append([(n, w / t) for n, w in l])
            dominant.setdefault(ob.name, []).append((v.co.copy(), l[0][0]))
        mat = me.materials[0].name
        out = ob.get('outline', 0.0)
        # smooth normals per vertex for the outline push
        vn = [Vector() for _ in me.vertices]
        for tri in me.loop_triangles:
            for li, vi in zip(tri.loops, tri.vertices):
                vn[vi] += cn[li].vector
        vn = [n.normalized() if n.length > 0 else Vector((0, 0, 1)) for n in vn]
        for tri in me.loop_triangles:
            f.write(mat + '\n')
            for li, vi in zip(tri.loops, tri.vertices):
                f.write(vline(me.vertices[vi].co, cn[li].vector, links[vi]))
            ntri += 1
            if out > 0:
                f.write('grinch_outline\n')
                for vi in reversed(tri.vertices):
                    f.write(vline(me.vertices[vi].co + vn[vi] * out, -vn[vi], links[vi]))
                ntri += 1
    f.write('end\n')
print('ref triangles', ntri)

# ---------------------------------------------------------------- physics
text = phy[phy.index(b'solid {'):].decode('latin1')
blocks = re.findall(r'(\w+) \{(.*?)\}', text, re.S)
solids, constraints, edit = [], [], {}
for kind, body in blocks:
    kv = re.findall(r'"(\w+)" "([^"]*)"', body)
    if kind == 'solid':
        solids.append(dict(kv))
    elif kind == 'ragdollconstraint':
        constraints.append(dict(kv))
    elif kind == 'editparams':
        edit = kv
solid_names = [s['name'] for s in solids]
by_lower = {b['name'].lower(): b['name'] for b in bones}

def solid_for(bone):
    i = index[bone]
    while bones[i]['name'] not in solid_names:
        i = bones[i]['parent']
    return bones[i]['name']

pts = {n: [] for n in solid_names}
for obname, vs in dominant.items():
    for co, b in vs:
        pts[solid_for(b)].append(co)

def rot_of(b):
    R = b['wR']
    return Matrix(((R[0][0], R[0][1], R[0][2]), (R[1][0], R[1][1], R[1][2]), (R[2][0], R[2][1], R[2][2])))

with open(os.path.join(OUT, 'grinch_phys.smd'), 'w') as f:
    header(f)
    f.write('triangles\n')
    for name in solid_names:
        b = bones[index[name]]
        R = rot_of(b); T = Vector(b['wt']); Ri = R.transposed()
        loc = [Ri @ (p - T) for p in pts[name]]
        lo = Vector((min(p[k] for p in loc) for k in range(3)))
        hi = Vector((max(p[k] for p in loc) for k in range(3)))
        c = (lo + hi) / 2; h = (hi - lo) / 2 * 0.9
        corners = [c + Vector((sx * h.x, sy * h.y, sz * h.z)) for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)]
        W = [R @ p + T for p in corners]
        faces = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
        for q in faces:
            for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                f.write('phys\n')
                a, bb, cc = (W[i] for i in tri)
                n = (bb - a).cross(cc - a).normalized()
                for i in tri:
                    p = W[i]
                    f.write(f'{index[name]} {p.x:.6f} {p.y:.6f} {p.z:.6f} {n.x:.6f} {n.y:.6f} {n.z:.6f} 0 0 1 {index[name]} 1\n')
    f.write('end\n')

# ---------------------------------------------------------------- qc
def matrix_angles(m):
    fwd = (m[0], m[4], m[8]); left = (m[1], m[5], m[9]); up = (m[2], m[6], m[10])
    xy = math.hypot(fwd[0], fwd[1])
    if xy > 0.001:
        yaw = math.atan2(fwd[1], fwd[0]); pitch = math.atan2(-fwd[2], xy); roll = math.atan2(left[2], up[2])
    else:
        yaw = math.atan2(-left[0], left[1]); pitch = math.atan2(-fwd[2], xy); roll = 0
    return [math.degrees(x) for x in (pitch, yaw, roll)]

q = []
q.append('$modelname "player/burrito/grinch_ultimatum.mdl"')
q.append('$model "body" "grinch_ref.smd"')
q.append('$cdmaterials "models/player/burrito/grinch_ultimatum/"')
q.append(f'$surfaceprop "{meta["surfaceprop"]}"')
q.append('$contents "solid"')
q.append('$eyeposition {:.3f} {:.3f} {:.3f}'.format(*meta['eyepos']))
q.append('$illumposition {:.3f} {:.3f} {:.3f}'.format(*meta['illum']))
for inc in meta['includes']:
    q.append(f'$includemodel "{inc[len("models/"):] if inc.startswith("models/") else inc}"')
for hs in meta['hitboxsets']:
    q.append(f'$hboxset "{hs["name"]}"')
    for h in hs['boxes']:
        mn, mx = h['min'], h['max']
        if h['bone'].endswith('Head1'):  # taller head + tufts
            mx = [mx[0] + 4.0, mx[1], mx[2]]
        q.append('$hbox {} "{}" {:.3f} {:.3f} {:.3f} {:.3f} {:.3f} {:.3f}'.format(h['group'], h['bone'], *mn, *mx))
for a in meta['attachments']:
    m = a['m']
    ang = matrix_angles(m)
    q.append('$attachment "{}" "{}" {:.3f} {:.3f} {:.3f} rotate {:.3f} {:.3f} {:.3f}'.format(
        a['name'], a['bone'], m[3], m[7], m[11], *ang))
for k in meta['ikchains']:
    kn = k['links'][0]['knee']
    q.append('$ikchain "{}" "{}" knee {:.3f} {:.3f} {:.3f}'.format(k['name'], k['links'][-1]['bone'], *kn))
q.append('$sequence "ragdoll" "grinch_ref.smd" activity "ACT_DIERAGDOLL" 1 fps 30')
q.append('$collisionjoints "grinch_phys.smd"')
q.append('{')
ed = dict(edit)
q.append(f'\t$mass {float(ed.get("totalmass", 90)):.1f}')
q.append('\t$inertia 10\n\t$damping 0.01\n\t$rotdamping 1.5')
q.append(f'\t$rootbone "{by_lower.get(ed.get("rootname", ""), "ValveBiped.Bip01_Pelvis")}"')
for c in constraints:
    child = solid_names[int(c['child'])]
    for ax in 'xyz':
        lo, hi, fr = float(c[ax + 'min']), float(c[ax + 'max']), float(c[ax + 'friction'])
        kind = 'limit'
        q.append(f'\t$jointconstrain "{child}" {ax} {kind} {lo:.1f} {hi:.1f} {fr:.1f}')
q.append('\t$animatedfriction 1.000 400.000 0.500 0.300 0.000')
q.append('}')
open(os.path.join(OUT, 'grinch.qc'), 'w').write('\n'.join(q) + '\n')
print('QC lines', len(q))
