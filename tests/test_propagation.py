import numpy as np

from smart_labelimg.annotation import Box
from smart_labelimg.propagation import estimate_displacement, propagate_boxes


class FakeBackend:
    def refine_from_box(self, image, query_box, label):
        return []


class RefiningBackend:
    def refine_from_box(self, image, query_box, label):
        x1, y1, x2, y2 = query_box
        return [Box(label, x1 + 1, y1 + 1, x2 - 1, y2 - 1, score=0.95)]


def test_estimate_displacement_tracks_shifted_object():
    previous = np.zeros((100, 140, 3), dtype=np.uint8)
    current = previous.copy()
    previous[30:60, 30:70] = (255, 255, 255)
    current[34:64, 38:78] = (255, 255, 255)

    dx, dy, score = estimate_displacement(previous, current, Box("car", 30, 30, 70, 60))

    assert abs(dx - 8) <= 1
    assert abs(dy - 4) <= 1
    assert score >= 0.9


def test_low_confidence_result_remains_candidate():
    blank = np.zeros((80, 100, 3), dtype=np.uint8)
    noise = np.indices((80, 100)).sum(axis=0).astype(np.uint8)
    noise = np.stack([noise, np.roll(noise, 7, axis=1), np.roll(noise, 13, axis=0)], axis=2)

    result = propagate_boxes(blank, noise, [Box("car", 10, 10, 30, 30)], FakeBackend())

    assert result.committed == ()
    assert len(result.candidates) == 1
    assert result.candidates[0].requires_confirmation


def test_high_confidence_result_commits_immutable_boxes_and_refines():
    previous = np.zeros((100, 140, 3), dtype=np.uint8)
    current = previous.copy()
    previous[30:60, 30:70] = (255, 255, 255)
    current[34:64, 38:78] = (255, 255, 255)
    source = [Box("car", 30, 30, 70, 60)]

    result = propagate_boxes(previous, current, source, RefiningBackend())

    assert result.candidates == ()
    assert result.committed == (Box("car", 39, 35, 77, 63, score=0.95),)
    assert source == [Box("car", 30, 30, 70, 60)]
    assert isinstance(result.committed, tuple)
    assert isinstance(result.candidates, tuple)


def test_propagation_clips_shifted_box_to_current_image():
    previous = np.zeros((60, 60, 3), dtype=np.uint8)
    current = previous.copy()
    previous[10:35, 30:55] = (255, 255, 255)
    current[12:37, 35:60] = (255, 255, 255)

    result = propagate_boxes(previous, current, [Box("car", 30, 10, 55, 35)], FakeBackend())

    assert result.committed
    assert result.committed[0].x2 <= 59
    assert result.committed[0].y2 <= 59
