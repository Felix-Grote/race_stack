"""Numerical tests for deterministic bounded candidate selection.

Runs on plain system python (enumeration, gates, cache, preparation) and,
when executed, also exercises the offline selection entry point: without
the pinned optimizer it must return NO_PASS with a meaningful reason, never
raise and never report strict-valid as PASS.
"""

import json
import math
import os
import sys
import tempfile
import unittest

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
WORKSPACE = os.path.dirname(os.path.dirname(os.path.dirname(TEST_DIR)))
sys.path.insert(0, os.path.join(WORKSPACE, 'planner', 'global_planner'))

from global_planner import route_candidates as rc
from global_planner.route_input import validate_route

CONFIG = os.path.join(WORKSPACE, 'planner', 'global_planner', 'config',
                      'project_a')
RESOLUTION_M = 0.05


def _prov():
    """Synthetic provenance documents; no map or vehicle claims."""
    return {'author': 'wp2-test', 'source': 'synthetic-annulus',
            'revision': '1', 'approval': 'none'}


def make_annulus_payload(radius=10.0, half_width=1.5, step_deg=3.0,
                         occurrences=4, seed_radius=None):
    """Build a strict schema-v1 annular route payload (CCW circle).

    Pure constructor: no map data, no track names, no randomness.
    ``seed_radius`` defaults to the mid radius; hugging a wall exercises
    early rejection when simplification moves that wall inward.
    """
    assert occurrences >= 2 and 360.0 % occurrences == 0
    seed_r = radius if seed_radius is None else seed_radius
    assert radius - half_width < seed_r < radius + half_width
    span = 360.0 / occurrences
    occs, portals, gate_ids = [], [], []
    for k in range(occurrences):
        lo, hi = k * span, (k + 1) * span
        angles = [lo + i * step_deg
                  for i in range(int(round(span / step_deg)) + 1)]
        angles[-1] = hi

        def located(r_m, deg):
            """World point at radius and angle."""
            rad = math.radians(deg)
            return [r_m * math.cos(rad), r_m * math.sin(rad)]

        seed = [located(seed_r, a) for a in angles]
        # CCW travel: right normal points outward, left normal inward.
        right = [located(radius + half_width, a) for a in angles]
        left = [located(radius - half_width, a) for a in angles]
        occs.append({
            'id': 'o%d' % k, 'surface_id': 'ground', 'seed': seed,
            'left': left, 'right': right,
            'caps': [{'at_m': 0, 'max_speed_mps': 2.5}],
            'provenance': _prov()})
    for k in range(occurrences):
        nxt = (k + 1) % occurrences
        gate = [occs[k]['right'][-1], occs[k]['left'][-1]]
        # Support covers the whole radial gate; the seed endpoint only needs
        # strict interior, so center on the gate midpoint (mid radius).
        corner = located(radius, (k + 1) * span)
        half = 2.0
        support = [[corner[0] - half, corner[1] - half],
                   [corner[0] + half, corner[1] - half],
                   [corner[0] + half, corner[1] + half],
                   [corner[0] - half, corner[1] + half]]
        portals.append({
            'id': 't%d' % k, 'from': occs[k]['id'], 'to': occs[nxt]['id'],
            'gate': gate, 'support': support,
            'before_m': 0.5, 'after_m': 0.5, 'continuity': 'shared_endcap',
            'provenance': _prov()})
        gate_ids.append('t%d' % k)
    start = occs[0]['seed'][0]
    payload = {
        'schema_version': 1, 'course_id': 'synthetic-course',
        'route_id': 'synthetic-annulus', 'frame_id': 'map', 'units': 'm',
        'conventions': 'x-forward_y-left_heading-ccw',
        'physical_map': {'sha256': '0' * 64, 'frame_id': 'map',
                         'registration': [0.0, 0.0, 0.0],
                         'coverage': 'unknown', 'provenance': _prov()},
        'provenance': _prov(),
        'surfaces': [{'id': 'ground', 'kind': 'planar',
                      'provenance': _prov()}],
        'occurrences': occs, 'transitions': portals,
        'gate_sequence': gate_ids, 'finish': gate_ids[-1],
        'initialization': {
            'occurrence_id': occs[0]['id'], 'seed_interval_m': [0.5, 2.0],
            'zone': [[start[0] - 1.0, start[1] - 1.0],
                     [start[0] + 1.0, start[1] - 1.0],
                     [start[0], start[1] + 1.0]],
            'heading_interval_rad': [1.0, 2.0]}}
    return validate_route(payload).payload


def hug_payload(clearance_m=0.005):
    """Annulus whose seed hugs the outer wall at the given clearance."""
    return make_annulus_payload(seed_radius=10.0 + 1.5 - clearance_m)


class CandidatePolicyTests(unittest.TestCase):
    """Bounded deterministic enumeration, gates and offline selection."""

    def setUp(self):
        """Clear shared cache state before each test."""
        rc.cache_clear()

    def test_synthetic_annulus_strict_valid(self):
        """The self-contained fixture passes strict validation."""
        route = validate_route(make_annulus_payload())
        self.assertEqual(len(route.occurrences), 4)

    def test_envelope_rejects_over_ratio(self):
        """Epsilon above 0.6 raster cells fails closed, producing nothing."""
        route = validate_route(make_annulus_payload())
        with self.assertRaises(rc.CandidateError):
            rc.enumerate_candidates(route, resolution_m=RESOLUTION_M,
                                    epsilons=(0.05,))

    def test_enumerate_bound_and_duplicates(self):
        """Candidate count is bounded; duplicates are not candidates."""
        route = validate_route(make_annulus_payload())
        with self.assertRaises(rc.CandidateError):
            rc.enumerate_candidates(route, resolution_m=RESOLUTION_M,
                                    epsilons=(0.0,) * 7)
        with self.assertRaises(rc.CandidateError):
            rc.enumerate_candidates(route, resolution_m=RESOLUTION_M,
                                    epsilons=(0.01, 0.01))

    def test_verbatim_candidate_preserves_identity(self):
        """Epsilon zero yields the bit-identical route and seed pin."""
        route = validate_route(make_annulus_payload())
        (spec,) = rc.enumerate_candidates(route, resolution_m=RESOLUTION_M,
                                          epsilons=(0.0,))
        self.assertFalse(spec.rejected)
        self.assertEqual(spec.stage, 'ENUMERATED')
        self.assertEqual(spec.digest, route.digest)

    def test_determinism_and_cache(self):
        """Repeated enumeration is identical and reuses cached routes."""
        route = validate_route(make_annulus_payload())
        first = rc.enumerate_candidates(route, resolution_m=RESOLUTION_M,
                                        epsilons=(0.0, 0.01, 0.02))
        self.assertTrue(all(not s.rejected for s in first))
        second = rc.enumerate_candidates(route, resolution_m=RESOLUTION_M,
                                         epsilons=(0.0, 0.01, 0.02))
        self.assertEqual([s.digest for s in first],
                         [s.digest for s in second])
        self.assertTrue(all(a.route is b.route
                            for a, b in zip(first, second)))
        self.assertGreaterEqual(rc.cache_info()['hits'], 3)
        pins = {s.seed_digest for s in first}
        self.assertEqual(len(pins), 1)

    def test_wall_hugger_rejected_early(self):
        """A variant that breaks legality rejects before corridor/optimizer."""
        route = validate_route(hug_payload())
        specs = rc.enumerate_candidates(route, resolution_m=RESOLUTION_M,
                                        epsilons=(0.01, 0.02))
        self.assertFalse(specs[0].rejected)
        self.assertTrue(specs[1].rejected)
        self.assertEqual(specs[1].stage, 'REJECTED')
        self.assertTrue(specs[1].reason)

    def test_prepare_never_labels_pass(self):
        """Preparation receipts use PREPARED/REJECTED, never PASS."""
        route = validate_route(make_annulus_payload())
        prepared = rc.prepare_candidates(
            route, resolution_m=RESOLUTION_M, epsilons=(0.0, 0.01, 0.02))
        self.assertEqual(len(prepared.receipts), 3)
        for receipt in prepared.receipts:
            self.assertIn(receipt.stage, ('PREPARED', 'REJECTED'))
            self.assertNotEqual(receipt.status, 'PASS')
            self.assertGreaterEqual(receipt.wall_seconds, 0.0)
            self.assertGreaterEqual(receipt.cpu_seconds, 0.0)
        hugging = validate_route(hug_payload())
        rejected = rc.prepare_candidates(
            hugging, resolution_m=RESOLUTION_M, epsilons=(0.02,))
        self.assertEqual(rejected.receipts[0].stage, 'REJECTED')
        self.assertEqual(rejected.receipts[0].wall_seconds, 0.0)

    def test_no_track_names_or_side_channels(self):
        """The policy module names no track and touches no browser/DB."""
        import re

        source = open(rc.__file__, encoding='utf-8').read().lower()
        for name in ('baku', 'zuri', 'hangar', 'smile', 'test\\.png'):
            self.assertIsNone(re.search(r'\b' + name + r'\b', source),
                              'track reference in policy module: ' + name)
        self.assertIsNone(re.search(r'\bspa\b', source))
        for channel in ('annotation_server', 'browser', 'websocket',
                        'sqlite', 'scheduler', 'subprocess', 'urllib',
                        'http'):
            self.assertIsNone(
                re.search(r'^\s*(import|from)\s+' + channel, source,
                          re.MULTILINE),
                'side-channel import in policy module: ' + channel)
        for mod in list(sys.modules):
            self.assertFalse(mod.startswith('sqlite3'))

    def test_select_candidate_offline_contract(self):
        """Offline selection measures, bounds and never mislabels PASS."""
        from global_planner.cyclic_retime import DynamicsModel
        from global_planner.route_artifact import decode_record
        from global_planner.route_compile import load_policy
        from global_planner.route_validate import Footprint

        package = os.path.join(WORKSPACE, 'planner', 'global_planner')
        if package not in os.environ.get('PYTHONPATH', ''):
            os.environ['PYTHONPATH'] = (
                package + os.pathsep + os.environ.get('PYTHONPATH', ''))
        policies, context, spacing = load_policy(
            os.path.join(CONFIG, 'policies', 'synthetic_policy.json'))
        model_doc = json.load(open(
            os.path.join(CONFIG, 'models', 'synthetic_model.json'),
            encoding='utf-8'))
        model = decode_record(DynamicsModel, model_doc['model'], 'model')
        footprint = decode_record(Footprint, model_doc['footprint'],
                                  'footprint')
        route = validate_route(make_annulus_payload())
        with tempfile.TemporaryDirectory(prefix='wp2-select-') as out:
            result = rc.select_candidate(
                route, model=model, footprint=footprint, policies=policies,
                output_dir=out, resolution_m=RESOLUTION_M,
                retime_spacing_m=spacing, validation_context=context,
                epsilons=(0.0,), provenance={'wp2_test': 'select'})
        self.assertLessEqual(len(result.receipts), rc.MAX_CANDIDATES)
        self.assertEqual(len(result.receipts), 1)
        self.assertGreaterEqual(result.wall_seconds, 0.0)
        self.assertGreaterEqual(result.cpu_seconds, 0.0)
        if result.status == 'PASS':
            self.assertIsNotNone(result.selected)
            self.assertEqual(result.selected.geometry_status, 'PASS')
            self.assertEqual(result.selected.dynamics_status, 'PASS')
            self.assertEqual(len(result.selected.artifact_H or ''), 64)
        else:
            self.assertEqual(result.status, 'NO_PASS')
            self.assertIsNone(result.selected)
            self.assertTrue(all(r.reason for r in result.receipts))
            self.assertTrue(all(r.status != 'PASS' for r in result.receipts))


if __name__ == '__main__':
    unittest.main()
