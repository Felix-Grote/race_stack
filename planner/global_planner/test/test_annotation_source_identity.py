# Copyright 2026 ForzaETH
"""Source-drift regression tests: a long-lived server session must not
preview/approve/export against a snapshot whose on-disk source changed."""
import json
import shutil
import sys
from pathlib import Path

import cv2
import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from global_planner.annotation_core import (  # noqa: E402
    AnnotationError, TrackMap, check_source_current, load_session,
    save_session)
from global_planner.route.manifest import load_route  # noqa: E402

MAPS = Path(__file__).parents[3] / 'stack_master' / 'maps'


@pytest.fixture
def live(tmp_path):
    """Server backend opened on a writable copy of the test map."""
    from global_planner import annotation_server as server
    maps = tmp_path / 'maps'
    shutil.copytree(MAPS / 'test', maps / 'test')
    saved = dict(server.STATE)
    server.configure(str(maps), str(tmp_path / 'out'))
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    yield server, maps / 'test'
    server.STATE.clear()
    server.STATE.update(saved)


def _approved(server):
    server.op_open({'map': 'test/test'})
    server.op_suggest({})
    preview = server.op_preview({})
    server.op_approve({'approval_digest': preview['candidate_digest']})
    return preview


def _drift_png(test_dir):
    png = test_dir / 'test.png'
    img = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE)
    img[226, 248] = 0 if img[226, 248] else 255  # binary-preserving flip
    cv2.imwrite(str(png), img)


def test_unchanged_source_exports_and_manifest_matches_disk(live):
    server, test_dir = live
    preview = _approved(server)
    receipt = server.op_export({})
    assert receipt['route_digest'] == preview['route_digest']
    out = Path(server.STATE['out_dir'])
    manifest = json.loads(next(out.glob('*_legal_route.json')).read_text())
    disk_sha = TrackMap(test_dir / 'test.yaml').sha256
    assert manifest['map']['sha256'] == disk_sha
    assert load_route(next(out.glob('*_legal_route.json'))).digest \
        == preview['route_digest']


def test_png_drift_after_approval_blocks_export(live):
    server, test_dir = live
    _approved(server)
    _drift_png(test_dir)
    with pytest.raises(AnnotationError, match='changed on disk'):
        server.op_export({})


def test_png_drift_after_preview_blocks_approve_and_preview(live):
    server, test_dir = live
    server.op_open({'map': 'test/test'})
    server.op_suggest({})
    preview = server.op_preview({})
    _drift_png(test_dir)
    with pytest.raises(AnnotationError, match='changed on disk'):
        server.op_approve({'approval_digest': preview['candidate_digest']})
    with pytest.raises(AnnotationError, match='changed on disk'):
        server.op_preview({})


def test_yaml_resolution_drift_blocks_export(live):
    server, test_dir = live
    _approved(server)
    yaml = test_dir / 'test.yaml'
    yaml.write_text(yaml.read_text().replace('resolution: 0.05',
                                             'resolution: 0.06'))
    with pytest.raises(AnnotationError, match='changed on disk'):
        server.op_export({})


def test_threshold_only_yaml_change_is_harmless(live):
    server, test_dir = live
    _approved(server)
    yaml = test_dir / 'test.yaml'
    text = yaml.read_text()
    assert 'occupied_thresh' in text
    yaml.write_text(text.replace('occupied_thresh: 0.65',
                                 'occupied_thresh: 0.5'))
    assert server.op_export({})['status'] == 'VALIDATED'


def test_restored_identical_bytes_export(live):
    server, test_dir = live
    _approved(server)
    original = (test_dir / 'test.png').read_bytes()
    _drift_png(test_dir)
    (test_dir / 'test.png').write_bytes(original)
    assert server.op_export({})['status'] == 'VALIDATED'


def test_missing_source_blocks_export(live):
    server, test_dir = live
    _approved(server)
    (test_dir / 'test.png').unlink()
    with pytest.raises(AnnotationError):
        server.op_export({})


def test_session_reload_after_drift_fails_closed(live, tmp_path):
    server, test_dir = live
    _approved(server)
    draft = tmp_path / 'draft.json'
    save_session(server.STATE['session'], draft)
    _drift_png(test_dir)
    with pytest.raises(AnnotationError, match='identity mismatch'):
        load_session(draft, TrackMap(test_dir / 'test.yaml'))


def test_cli_export_after_drift_fails_closed(live, tmp_path):
    from global_planner.annotation_tool import main as cli_main
    server, test_dir = live
    _approved(server)
    draft = tmp_path / 'draft.json'
    save_session(server.STATE['session'], draft)
    _drift_png(test_dir)
    rc = cli_main(['export', '--map', str(test_dir / 'test.yaml'),
                   '--session', str(draft), '--out', str(tmp_path / 'cli')])
    assert rc == 1


def test_load_hashes_and_decodes_the_same_bytes(tmp_path, monkeypatch):
    """A file replaced mid-load cannot split pixels and SHA across versions."""
    import hashlib
    shutil.copytree(MAPS / 'test', tmp_path / 'test')
    png = tmp_path / 'test' / 'test.png'
    original_bytes = png.read_bytes()
    other = cv2.imread(str(png), cv2.IMREAD_GRAYSCALE).copy()
    other[226, 248] = 0 if other[226, 248] else 255

    real_read_bytes = Path.read_bytes

    def swapping_read_bytes(self):
        data = real_read_bytes(self)
        if self == png.resolve():
            cv2.imwrite(str(png), other)  # writer races the load
        return data

    monkeypatch.setattr(Path, 'read_bytes', swapping_read_bytes)
    track_map = TrackMap(tmp_path / 'test' / 'test.yaml')
    assert png.read_bytes() != original_bytes  # the swap really happened
    assert track_map.sha256 == hashlib.sha256(original_bytes).hexdigest()
    expected = cv2.imdecode(
        np.frombuffer(original_bytes, dtype=np.uint8),
        cv2.IMREAD_GRAYSCALE)
    assert (track_map.image == expected).all()


def test_unreadable_png_fails_as_before(tmp_path):
    shutil.copytree(MAPS / 'test', tmp_path / 'test')
    png = tmp_path / 'test' / 'test.png'
    png.write_bytes(b'not a png')
    with pytest.raises(AnnotationError, match='cannot read map image'):
        TrackMap(tmp_path / 'test' / 'test.yaml')
    png.unlink()
    with pytest.raises(AnnotationError, match='cannot read map image'):
        TrackMap(tmp_path / 'test' / 'test.yaml')


def test_check_source_current_unit(tmp_path):
    shutil.copytree(MAPS / 'test', tmp_path / 'test')
    track_map = TrackMap(tmp_path / 'test' / 'test.yaml')
    check_source_current(track_map)  # unchanged: passes
    _drift_png(tmp_path / 'test')
    with pytest.raises(AnnotationError, match='changed on disk'):
        check_source_current(track_map)
