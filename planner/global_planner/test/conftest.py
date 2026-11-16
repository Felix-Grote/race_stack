# Copyright 2026 ForzaETH
"""Shared fixtures for the annotation editor deployment test suite."""
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

MAPS = Path(__file__).parents[3] / 'stack_master' / 'maps'


def midline_seed(outer, inner, count=120):
    """Crude directed guide: each outer point averaged with nearest inner."""
    step = max(1, len(outer) // count)
    seed = []
    for p in outer[::step]:
        j = int(np.argmin(np.linalg.norm(inner - p, axis=1)))
        seed.append(((p + inner[j]) / 2).tolist())
    return seed


def write_map(tmp_path, image, name='map.png', resolution=0.05,
              origin=(0.0, 0.0, 0.0), negate=0):
    """Write a PNG+YAML fixture pair; return its TrackMap."""
    import cv2

    from global_planner.annotation_core import TrackMap
    cv2.imwrite(str(tmp_path / name), image)
    yaml_path = tmp_path / (Path(name).stem + '.yaml')
    yaml_path.write_text(
        f'image: {name}\nresolution: {resolution}\n'
        f'origin: [{origin[0]}, {origin[1]}, {origin[2]}]\n'
        f'negate: {negate}\noccupied_thresh: 0.65\nfree_thresh: 0.196\n',
        encoding='utf-8')
    return TrackMap(yaml_path)


def annulus_image(size=200):
    """Binary square annulus: white ring, black infield and surround."""
    import cv2
    img = np.zeros((size, size), np.uint8)
    cv2.rectangle(img, (20, 20), (size - 20, size - 20), 255, -1)
    cv2.rectangle(img, (70, 70), (size - 70, size - 70), 0, -1)
    return img


@pytest.fixture
def backend(tmp_path):
    """Configured shared HTTP/ROS backend with STATE restored after."""
    from global_planner import annotation_server as server
    saved = dict(server.STATE)
    server.configure(str(MAPS), str(tmp_path / 'out'))
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    yield server
    server.STATE.clear()
    server.STATE.update(saved)


@pytest.fixture
def syn_backend(tmp_path):
    """Backend serving a synthetic 200x200 square annulus map."""
    import cv2
    maps = tmp_path / 'maps'
    maps.mkdir()
    cv2.imwrite(str(maps / 'syn.png'), annulus_image())
    (maps / 'syn.yaml').write_text(
        'image: syn.png\nresolution: 0.05\norigin: [0, 0, 0]\nnegate: 0\n'
        'occupied_thresh: 0.65\nfree_thresh: 0.196\n', encoding='utf-8')
    from global_planner import annotation_server as server
    saved = dict(server.STATE)
    server.configure(str(maps), str(tmp_path / 'out'))
    server.STATE.update(map=None, session=None, extraction=None,
                        candidate_digest=None)
    yield server
    server.STATE.clear()
    server.STATE.update(saved)
