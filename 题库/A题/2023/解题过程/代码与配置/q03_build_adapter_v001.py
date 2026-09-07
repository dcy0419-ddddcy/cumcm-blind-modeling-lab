"""Source-only adaptation of the already verified fast kernel. No model execution."""
from pathlib import Path
P=Path(__file__).resolve().parent
old=(P/'q02_fast_v002.py').read_text(encoding='utf-8-sig')
head=old[:old.index('@dataclass(frozen=True, slots=True, eq=False)\nclass FrozenDesign:')]
head=head.replace('Immutable Q2 performance adapter v002','Q3 heterogeneous performance adapter v001')
head=head.replace('import q02_design_v002 as design_module','import q03_design_v001 as design_module')
middle='''@dataclass(frozen=True, slots=True, eq=False)
class FrozenDesign:
    name: str
    version: str
    tower_xy: tuple
    widths: np.ndarray
    heights: np.ndarray
    installation_heights: np.ndarray
    centers: np.ndarray
    mirror_ids: tuple
    position_keys: tuple
    groups: np.ndarray
    areas: np.ndarray
    total_area: float
    key: str
    payload_json: str = field(repr=False)
    validation_json: str = field(repr=False)
    @property
    def n(self): return len(self.mirror_ids)
    @property
    def validation(self): return json.loads(self.validation_json)
    def to_design(self): return json.loads(self.payload_json)

def freeze_design(design):
    snapshot=copy.deepcopy(design)
    checked=design_module.validate_design(snapshot)
    for key,tag in [('schema_valid','INPUT_FAILURE'),('geometry_valid','GEOMETRY_FAILURE'),('search_scope_valid','SEARCH_SCOPE_FAILURE')]:
        if not checked[key]: raise reference.StateError(tag+': '+_json(checked))
    rows=snapshot['mirrors']
    centers=_immutable_array([[r['x'],r['y'],r['z']]for r in rows],float)
    widths=_immutable_array([r['width']for r in rows],float)
    heights=_immutable_array([r['height']for r in rows],float)
    zs=_immutable_array([r['z']for r in rows],float)
    areas=_immutable_array(widths*heights,float)
    encoded=_json(snapshot)
    return FrozenDesign(snapshot['name'],snapshot['version'],tuple(snapshot['tower_xy']),widths,heights,zs,
        centers,tuple(int(r['mirror_id'])for r in rows),tuple(r['position_key']for r in rows),
        _immutable_array([r['group']for r in rows],int),areas,float(areas.sum()),
        hashlib.sha256(encoded.encode()).hexdigest(),encoded,_json(checked))

'''
tail=old[old.index('@dataclass(frozen=True, slots=True, eq=False)\nclass FrozenMirrors:'):]
tail=tail.replace('def scene_at(frozen, month, hour):','def scene_at(frozen, month, hour, *, beta=BETA, tolerance=None):')
start=tail.index('def scene_at(');end=tail.index('\ndef candidate_pair(',start)
block=tail[start:end].replace('frozen.width, frozen.height','frozen.widths, frozen.heights')
block=block.replace('tol = c.Tolerance()','tol = c.Tolerance() if tolerance is None else tolerance')
# Leave the signature default constant; only pass the explicit beta inside.
block=block.replace('sun[\'s0\'], BETA, receiver','sun[\'s0\'], beta, receiver').replace('BETA, tol, tag, domain','beta, tol, tag, domain').replace('), BETA, tol, ref.key', '), beta, tol, ref.key')
tail=tail[:start]+block+tail[end:]
target=P/'q03_fast_v001.py'
if target.exists():raise RuntimeError('new source already exists')
target.write_text(head+middle+tail,encoding='utf-8')
