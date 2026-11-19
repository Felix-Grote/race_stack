"""Exercise real map export, validation and planning through the workspace."""
from pathlib import Path
import shutil
from types import SimpleNamespace

import numpy as np
import pytest

from global_planner.annotation.track_map import AnnotationError, free_mask
from global_planner.operational_centre.generation import generate, provenance
from global_planner.operational_centre.inputs import Track, Vehicle
from global_planner.operational_centre.settings import Worksheet, defaults, validate
from global_planner.operational_centre.workspace import Workspace
from global_planner.route.manifest import load_route

ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def workspace(tmp_path):
    """Copy a real repository map so annotation leaves the originals alone."""
    folder = tmp_path / 'maps' / 'test'
    folder.mkdir(parents=True)
    for suffix in ('png', 'yaml'):
        shutil.copy(ROOT / f'stack_master/maps/test/test.{suffix}', folder)
    car = ROOT / 'stack_master/config/NUC5/car_model.yaml'
    return Workspace(folder.parent, tmp_path / 'workspace', car, 0.05)


def export(workspace):
    """Place a start on the top straight and export through the real editor."""
    workspace.prepare_annotation('open')
    workspace.editor.open('test/test')
    workspace.editor.edit('start_px', [206, 39])
    workspace.editor.export()
    return workspace.editor.track_map.yaml_path


def test_sliver_cleanup_preserves_raster_alignment():
    """The cleaned road is exactly the union of valid 2-by-2 free blocks."""
    occupied = np.ones((7, 7), dtype=bool)
    occupied[2:5, 2:5] = False
    occupied[6, 6] = False
    expected = np.zeros_like(occupied)
    expected[2:5, 2:5] = True
    actual = free_mask(SimpleNamespace(occupied=occupied), [], 5)
    assert np.array_equal(actual != 0, expected)


def test_export_detects_map_calibration_change(workspace):
    """A YAML-only map change makes the canonical export stale."""
    source = export(workspace)
    exported = source.with_name('test_route.json')
    assert load_route(exported).digest == workspace.editor.result['digest']
    assert workspace.state(None, None)['track']['status'] == 'ready'

    receipt = exported.with_suffix('.source.json')
    saved = receipt.read_bytes()
    receipt.unlink()
    assert workspace.state(None, None)['track']['status'] == 'unverified'
    receipt.write_bytes(saved)

    unchanged = exported.read_bytes()
    source.write_text(source.read_text().replace('free_thresh: 0.196', 'free_thresh: 0.2'))
    state = workspace.state(None, None)
    assert state['track']['status'] == 'stale'
    assert state['annotation']['source_changed']
    with pytest.raises(AnnotationError, match='changed on disk'):
        workspace.editor.export()
    assert exported.read_bytes() == unchanged


def test_worksheet_bounds_and_conflicts(tmp_path):
    """A bad value or a stale revision cannot overwrite settings."""
    path = tmp_path / 'optimizer.json'
    values = defaults()
    values['step_m']['value'] = 0.4
    with pytest.raises(ValueError, match='step_m'):
        Worksheet.save(path, values, 'defaults')
    assert not path.exists()
    values['step_m']['value'] = 0.1
    values['max_passes']['value'] = 30
    Worksheet.save(path, values, 'defaults')
    with pytest.raises(ValueError, match='changed on disk'):
        Worksheet.save(path, defaults(), 'defaults')
    assert validate(Worksheet.read(path).parameters).max_passes == 30


def test_category_provenance_and_real_centreline(workspace):
    """Bounds and lap-time-only values do not invalidate unrelated modes."""
    track = Track.read(export(workspace))
    vehicle = Vehicle.read(workspace.car_path, workspace.margin)
    initial = defaults()
    edited = defaults()
    edited['smoothness']['lower'] = 0.05
    edited['smoothness']['value'] = 0.2
    for category in ('centreline', 'curvature'):
        assert provenance(category, track, vehicle, validate(initial)) == provenance(
            category, track, vehicle, validate(edited))
    assert provenance('laptime', track, vehicle, validate(initial)) != provenance(
        'laptime', track, vehicle, validate(edited))
    outcome = generate('centreline', track, vehicle, validate(initial))
    assert 80 < outcome['metrics']['length_m'] < 90
    assert len(outcome['points']) > 500
    assert outcome['speed'] == []
