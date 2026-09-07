"""Immutable Q2 performance adapter v002; unchanged pinned Q1 optical kernel.

No numerical work is executed on import except dependency SHA-256 checks.
freeze_design validates all design pairs once. scene_at prepares one time once;
the caller owns scene lifetime, so this module does not retain all sixty times.
All persistent numerical arrays have immutable bytes backing (not only a flag).
Only candidate memoization is mutable and is private to a prepared scene.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from numbers import Integral
import numpy as np

HERE = Path(__file__).resolve().parent
PINNED = {
    'q01_core_v003.py': '7d7e70b8c85b1bc7762efdc08fadc972635d810ceb852bf74bfb2cc318ed1693',
    'q02_eval_v003.py': 'f2d26131fd500c193cc643021815feee5195c5da668144b22a1571e2003b35de',
    'q02_design_v002.py': '92315f1506597508d1d558ea1e58bd18579c4381a56741de929d7b9a48f3b361',
}
for _file, _sha in PINNED.items():
    if hashlib.sha256((HERE / _file).read_bytes()).hexdigest() != _sha:
        raise RuntimeError('FAST_DEPENDENCY_CHANGED: ' + _file)
import q02_eval_v003 as reference
import q02_design_v002 as design_module
c = reference.c
BETA = reference.BETA
RHO = reference.RHO
COUNT_LABELS = ('shadow', 'blocked_after_unshadowed', 'survive', 'capture', 'unknown', 'raw_R')
EVENT_KEYS = ('S', 'B', 'R', 'unknown', 'incoming_object', 'blocking_object', 'receiver_kind')


def _json(value):
    return json.dumps(reference.clean(value), ensure_ascii=False, sort_keys=True,
                      separators=(',', ':'), allow_nan=False)


def _immutable_array(value, dtype=None):
    """Detached immutable bytes prevent both alias writes and setflags(write=True)."""
    arr = np.ascontiguousarray(value, dtype=dtype)
    return np.frombuffer(arr.tobytes(order='C'), dtype=arr.dtype).reshape(arr.shape)


def _index(i, n):
    if isinstance(i, bool) or not isinstance(i, Integral) or not 0 <= i < n:
        raise reference.StateError('INPUT_FAILURE: object index')
    return int(i)


@dataclass(frozen=True, slots=True, eq=False)
class FrozenDesign:
    name: str
    version: str
    tower_xy: tuple
    width: float
    height: float
    installation_height: float
    centers: np.ndarray
    mirror_ids: tuple
    position_keys: tuple
    areas: np.ndarray
    total_area: float
    key: str
    payload_json: str = field(repr=False)
    validation_json: str = field(repr=False)

    @property
    def n(self):
        return len(self.mirror_ids)

    @property
    def validation(self):
        return json.loads(self.validation_json)

    def to_design(self):
        p = json.loads(self.payload_json)
        return design_module.Design(p['name'], p['version'], tuple(p['tower_xy']),
                                    p['width'], p['height'], p['installation_height'],
                                    p['mirrors'], p['metadata'])


def freeze_design(design):
    """Validate a detached snapshot once; never hold caller-owned Design containers."""
    if not isinstance(design, design_module.Design):
        raise reference.StateError('INPUT_FAILURE: expected Design')
    snapshot = copy.deepcopy(design)
    checked = design_module.validate_design(snapshot)
    if not checked['schema_valid']:
        raise reference.StateError('INPUT_FAILURE: ' + _json(checked))
    if not checked['geometry_valid']:
        raise reference.StateError('GEOMETRY_FAILURE: ' + _json(checked))
    if not checked['search_scope_valid']:
        raise reference.StateError('SEARCH_SCOPE_FAILURE: width smaller than height')
    payload = {k: getattr(snapshot, k) for k in
               ('name', 'version', 'tower_xy', 'width', 'height',
                'installation_height', 'mirrors', 'metadata')}
    encoded = _json(payload)
    # Frozen identity follows stable design semantics. Reader provenance belongs
    # in payload_json/to_design, but must not invalidate the same physical design.
    # Include all effective generation metadata; exclude only the two optional
    # per-row provenance fields by explicitly listing physical/identity fields.
    identity = {
        'identity_schema': 'q02-frozen-design-v002',
        'name': snapshot.name, 'version': snapshot.version,
        'tower_xy': [float(v) for v in snapshot.tower_xy],
        'width': float(snapshot.width), 'height': float(snapshot.height),
        'installation_height': float(snapshot.installation_height),
        'mirrors': [{'mirror_id': int(r['mirror_id']),
                     'position_key': r['position_key'],
                     'x': float(r['x']), 'y': float(r['y'])}
                    for r in snapshot.mirrors],
        'metadata': snapshot.metadata,
    }
    identity_encoded = _json(identity)
    centers = _immutable_array([[r['x'], r['y'], snapshot.installation_height]
                                for r in snapshot.mirrors], float)
    ids = tuple(int(r['mirror_id']) for r in snapshot.mirrors)
    keys = tuple(r['position_key'] for r in snapshot.mirrors)
    areas = _immutable_array(np.full(len(ids), snapshot.width * snapshot.height), float)
    return FrozenDesign(snapshot.name, snapshot.version,
                        tuple(float(x) for x in snapshot.tower_xy),
                        float(snapshot.width), float(snapshot.height),
                        float(snapshot.installation_height), centers, ids, keys, areas,
                        float(len(ids) * snapshot.width * snapshot.height),
                        hashlib.sha256(identity_encoded.encode('utf-8')).hexdigest(),
                        encoded, _json(checked))


@dataclass(frozen=True, slots=True, eq=False)
class FrozenMirrors:
    centers: np.ndarray
    normals: np.ndarray
    u: np.ndarray
    v: np.ndarray
    widths: np.ndarray
    heights: np.ndarray
    vertical: np.ndarray
    radii: np.ndarray

    def subset(self, ids):
        # Fancy-index copies are temporary kernel inputs; cannot mutate the parent.
        return c.Mirrors(*(getattr(self, k)[ids] for k in
                           ('centers', 'normals', 'u', 'v', 'widths', 'heights', 'vertical')))


@dataclass(frozen=True, slots=True, eq=False)
class PreparedScene:
    design: FrozenDesign
    mirrors: FrozenMirrors
    s0: np.ndarray
    target: np.ndarray
    receiver: object
    dni: float
    tau: np.ndarray
    cosine: np.ndarray
    beta: float
    tol: object
    key: str
    month: int
    hour: float
    tag_json: str = field(repr=False)
    domain_json: str = field(repr=False)
    _candidate_cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def n(self):
        return self.design.n

    @property
    def areas(self):
        return self.design.areas

    @property
    def tag(self):
        return json.loads(self.tag_json)

    @property
    def domain(self):
        return json.loads(self.domain_json)

    @property
    def total_area(self):
        return self.design.total_area


@dataclass(frozen=True, slots=True, eq=False)
class CandidatePair:
    scene_key: str
    mirror_index: int
    incoming: np.ndarray
    outgoing: np.ndarray


def as_reference(scene):
    """Fresh mutable wrapper over immutable data; editing the wrapper cannot edit scene."""
    if not isinstance(scene, PreparedScene):
        raise reference.StateError('INPUT_FAILURE: expected PreparedScene')
    f = scene.mirrors
    mirrors = c.Mirrors(*(getattr(f, k) for k in
                          ('centers', 'normals', 'u', 'v', 'widths', 'heights', 'vertical')))
    return reference.Scene(mirrors, scene.s0, scene.target, scene.receiver,
                           scene.dni, scene.tau, scene.beta, scene.tol,
                           scene.tag, scene.domain)


def scene_at(frozen, month, hour):
    """One prepared time, one full domain check, one geometry hash; caller releases it."""
    if not isinstance(frozen, FrozenDesign):
        raise reference.StateError('INPUT_FAILURE: expected FrozenDesign')
    sun = c.solar(month, hour)
    receiver = c.Cylinder((frozen.tower_xy[0], frozen.tower_xy[1], 80.), 3.5, 8.)
    target = c.unit(np.asarray(receiver.center) - frozen.centers)
    raw = c.make_mirrors(frozen.centers, c.unit(target + sun['s0']),
                         frozen.width, frozen.height)
    mirrors = FrozenMirrors(*(_immutable_array(getattr(raw, k)) for k in
                              ('centers', 'normals', 'u', 'v', 'widths', 'heights', 'vertical')),
                            _immutable_array(raw.radii))
    tol = c.Tolerance()
    domain = c.check_domain(mirrors, sun['s0'], BETA, receiver, target)
    reflected = c.reflect(-np.broadcast_to(sun['s0'], mirrors.normals.shape), mirrors.normals)
    error = float(np.max(np.abs(reflected - target)))
    if error > 1e-12:
        raise reference.StateError('MODEL_DOMAIN_FAILURE: reflected center direction')
    distance = np.linalg.norm(np.asarray(receiver.center) - frozen.centers, axis=1)
    tau = .99321 - .0001176 * distance + 1.97e-8 * distance ** 2
    domain.update(target_reflection_error=error, distance_min=float(distance.min()),
                  distance_max=float(distance.max()))
    tag = {'design_name': frozen.name, 'design_version': frozen.version,
           'month': int(month), 'hour': float(hour),
           'ids': list(frozen.mirror_ids), 'position_keys': list(frozen.position_keys)}
    s0 = _immutable_array(sun['s0'])
    target = _immutable_array(target)
    tau = _immutable_array(tau)
    # Exactly the reference hash representation; computed only at preparation.
    ref = reference.Scene(mirrors, s0, target, receiver, float(sun['dni']), tau,
                          BETA, tol, tag, domain)
    return PreparedScene(frozen, mirrors, s0, target, receiver, float(sun['dni']), tau,
                         _immutable_array(mirrors.normals @ s0), BETA, tol, ref.key,
                         int(month), float(hour), _json(tag), _json(domain))


def candidate_pair(scene, i):
    """Same necessary-condition formula; share displacement/distance between both axes."""
    i = _index(i, scene.n)
    found = scene._candidate_cache.get(i)
    if found is not None:
        return found
    f = scene.mirrors
    delta = f.centers - f.centers[i]
    distance = np.linalg.norm(delta, axis=1)
    radius_sum = f.radii + f.radii[i]
    angular = math.sin(scene.beta)
    def one(axis):
        axial = delta @ axis
        perpendicular = np.linalg.norm(delta - axial[:, None] * axis, axis=1)
        keep = ((axial >= -radius_sum - scene.tol.length) &
                (perpendicular <= radius_sum + (distance + radius_sum) * angular + scene.tol.length))
        keep[i] = False
        return _immutable_array(np.flatnonzero(keep), np.int64)
    pair = CandidatePair(scene.key, i, one(scene.s0), one(scene.target[i]))
    scene._candidate_cache[i] = pair
    return pair


def _checked_pair(scene, i, pair):
    if not isinstance(pair, CandidatePair) or pair.scene_key != scene.key or pair.mirror_index != i:
        raise reference.StateError('CACHE_INVALID: bound immutable scene or object differs')
    return pair.incoming, pair.outgoing


def trace_same(scene, i, o, s, screen=True, cache=None):
    """Reference source-domain/weight/event behavior without repeated whole-scene work."""
    if not isinstance(scene, PreparedScene):
        raise reference.StateError('INPUT_FAILURE: expected PreparedScene')
    i = _index(i, scene.n)
    o = np.asarray(o, float); s = np.asarray(s, float)
    if (o.shape != s.shape or o.ndim != 2 or o.shape[1] != 3 or len(o) == 0 or
            not np.all(np.isfinite(o)) or not np.all(np.isfinite(s))):
        raise reference.StateError('INPUT_FAILURE: ray array')
    if np.max(np.abs(np.linalg.norm(s, axis=1) - 1)) > 1e-12:
        raise reference.StateError('INPUT_FAILURE: nonunit rays')
    f = scene.mirrors
    if np.any(s @ scene.s0 <= 0) or np.any(s @ f.normals[i] <= 0):
        raise reference.StateError('MODEL_DOMAIN_FAILURE: projection')
    offset = o - f.centers[i]
    plane = np.abs(offset @ f.normals[i])
    mu = f.widths[i] / 2 - np.abs(offset @ f.u[i])
    mv = f.heights[i] / 2 - np.abs(offset @ f.v[i])
    cone_margin = s @ scene.s0 - math.cos(scene.beta)
    if (np.any(plane > scene.tol.length) or np.any(mu < -scene.tol.length) or
            np.any(mv < -scene.tol.length) or np.any(cone_margin < -scene.tol.direction)):
        raise reference.StateError('RAY_DOMAIN_FAILURE: origin outside finite mirror or direction outside bound cone')
    source_uncertain = (mu <= scene.tol.length) | (mv <= scene.tol.length) | (cone_margin < 0)
    pair = None
    if screen:
        pair = _checked_pair(scene, i, candidate_pair(scene, i) if cache is None else cache)
    ev = c.trace(o, s, f, i, scene.s0, scene.target, scene.receiver,
                 scene.beta, scene.tol, screen=screen, candidate_ids=pair)
    ev['unknown'] |= source_uncertain
    ev['scene_sha256'] = scene.key
    ev['mirror_index'] = i
    g = (s @ f.normals[i]) / (s @ scene.s0)
    return g, ev


def sample_stats(scene, i, seedwords_per_batch, n, levels=None):
    """Generate B independent streams, trace B*n once, return L x B raw arrays.

    levels are correlated prefixes. Only the final n level belongs in a final pool.
    Seed identities are checked for duplicates within this call. Cross-call overlap
    must be prevented by the caller's saved stream ledger.
    """
    i = _index(i, scene.n)
    if isinstance(n, bool) or not isinstance(n, Integral) or n <= 0:
        raise reference.StateError('INPUT_FAILURE: positive integer sample size')
    n = int(n)
    levels = (n,) if levels is None else tuple(levels)
    if (not levels or any(isinstance(k, bool) or not isinstance(k, Integral) or k <= 0 or k > n for k in levels)
            or len(set(levels)) != len(levels) or tuple(sorted(levels)) != levels or levels[-1] != n):
        raise reference.StateError('INPUT_FAILURE: unique ordered positive prefixes ending at n required')
    levels = tuple(int(k) for k in levels)
    seeds = tuple(tuple(int(w) for w in words) for words in seedwords_per_batch)
    if not seeds or any(not words or any(w < 0 for w in words) for words in seeds) or len(set(seeds)) != len(seeds):
        raise reference.StateError('INPUT_FAILURE: nonempty distinct seed word vectors required')
    origins = []; directions = []
    for words in seeds:
        o, s = c.random_rays(scene.mirrors, i, scene.s0, scene.beta, n, words)
        origins.append(o); directions.append(s)
    o = np.concatenate(origins); s = np.concatenate(directions)
    pair = candidate_pair(scene, i)
    g, ev = trace_same(scene, i, o, s, cache=pair)
    B = len(seeds); L = len(levels)
    gg = g.reshape(B, n)
    S, BB, R, U = (ev[k].reshape(B, n) for k in ('S', 'B', 'R', 'unknown'))
    survivor = S & BB; capture = survivor & R
    X = np.stack((gg, gg * survivor, gg * capture), axis=-1)
    sums = np.empty((L, B, 3), float); cross = np.empty((L, B, 3, 3), float)
    counts = np.empty((L, B, len(COUNT_LABELS)), np.int64)
    unknown_weights = np.empty((L, B), float); known_capture_weights = np.empty((L, B), float)
    for j, k in enumerate(levels):
        xx = X[:, :k]
        sums[j] = xx.sum(axis=1)
        cross[j] = np.einsum('bni,bnj->bij', xx, xx)
        counts[j] = np.stack(((~S[:, :k]).sum(1), (S[:, :k] & ~BB[:, :k]).sum(1),
                              survivor[:, :k].sum(1), capture[:, :k].sum(1),
                              U[:, :k].sum(1), R[:, :k].sum(1)), axis=-1)
        unknown_weights[j] = (gg[:, :k] * U[:, :k]).sum(1)
        known_capture_weights[j] = (gg[:, :k] * capture[:, :k] * ~U[:, :k]).sum(1)
    bad = np.flatnonzero(ev['unknown'])[:8]
    examples = [{'batch': int(q // n), 'sample': int(q % n), 'point': o[q].tolist(),
                 'sun_direction': s[q].tolist(), 'receiver_kind': str(ev['receiver_kind'][q])}
                for q in bad]
    return {'scene_sha256': scene.key, 'design_sha256': scene.design.key,
            'mirror_index': i, 'mirror_id': scene.design.mirror_ids[i],
            'n': n, 'batches': B, 'levels': np.asarray(levels, np.int64),
            'seed_words': seeds, 'sums': sums, 'cross': cross, 'counts': counts,
            'count_labels': COUNT_LABELS, 'unknown_weights': unknown_weights,
            'known_capture_weights': known_capture_weights,
            'candidate_counts': (len(pair.incoming), len(pair.outgoing)),
            'unique_source_samples': B * n, 'path_evaluations': B * n,
            'abnormal_paths': examples}


def batch_as_reference(result, level_index, batch_index):
    """Convert only one object's batch; never repeats a full scene ID list."""
    j = int(level_index); b = int(batch_index)
    if not 0 <= j < len(result['levels']) or not 0 <= b < result['batches']:
        raise reference.StateError('INPUT_FAILURE: result level/batch index')
    row = result['counts'][j, b]
    return {'scene_sha256': result['scene_sha256'], 'mirror_index': result['mirror_index'],
            'n': int(result['levels'][j]), 'sums': result['sums'][j, b].copy(),
            'cross': result['cross'][j, b].copy(),
            'counts': {k: int(row[q]) for q, k in enumerate(COUNT_LABELS[:-1])},
            'unknown_weight': float(result['unknown_weights'][j, b]),
            'known_capture_weight': float(result['known_capture_weights'][j, b])}

