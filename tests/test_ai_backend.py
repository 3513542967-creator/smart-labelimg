import numpy as np

from smart_labelimg.ai_backend import ClassicalVisionBackend, LocateAnythingBackend, MobileSamBackend, mask_to_box


def make_scene():
    image = np.full((240, 360, 3), 245, dtype=np.uint8)
    image[60:120, 40:130] = (40, 40, 220)
    image[150:210, 220:310] = (40, 40, 220)
    image[20:50, 260:330] = (50, 180, 50)
    return image


def test_click_to_box_finds_clicked_object():
    backend = ClassicalVisionBackend()
    boxes = backend.detect_from_click(make_scene(), x=70, y=90, label="car")

    assert boxes
    box = boxes[0]
    assert box.label == "car"
    assert box.x1 <= 45
    assert box.y1 <= 65
    assert box.x2 >= 125
    assert box.y2 >= 115


def test_classical_refine_from_box_tightens_to_colored_component():
    backend = ClassicalVisionBackend()
    image = make_scene()

    boxes = backend.refine_from_box(image, query_box=(20, 40, 160, 140), label="car")

    assert boxes
    box = boxes[0]
    assert box.label == "car"
    assert box.x1 <= 45
    assert box.y1 <= 65
    assert box.x2 >= 125
    assert box.y2 >= 115
    assert box.x1 > 20
    assert box.y1 > 40
    assert box.x2 < 160
    assert box.y2 < 140


def test_mobile_sam_refine_from_box_uses_full_image_and_original_box_coordinates():
    class FakePredictor:
        def __init__(self):
            self.calls = []

        def set_image(self, image):
            self.calls.append(("set_image", image.shape))

        def predict(self, **kwargs):
            self.calls.append(("predict", kwargs))
            mask = np.zeros((100, 120), dtype=bool)
            mask[30:80, 20:70] = True
            return np.array([mask]), np.array([0.93]), None

    backend = object.__new__(MobileSamBackend)
    backend.predictor = FakePredictor()
    image = np.zeros((100, 120, 3), dtype=np.uint8)

    boxes = backend.refine_from_box(image, query_box=(20, 30, 70, 80), label="car")

    assert len(boxes) == 1
    assert (boxes[0].x1, boxes[0].y1, boxes[0].x2, boxes[0].y2) == (20, 30, 69, 79)
    assert boxes[0].label == "car"
    assert boxes[0].score == 0.93
    assert backend.predictor.calls[0] == ("set_image", image.shape)
    predict_kwargs = backend.predictor.calls[-1][1]
    assert np.array_equal(predict_kwargs["box"], np.array([20, 30, 70, 80], dtype=np.float32))


def test_mobile_sam_click_uses_full_image_and_original_point_coordinates():
    class FakePredictor:
        def __init__(self):
            self.calls = []

        def set_image(self, image):
            self.calls.append(("set_image", image.shape))

        def predict(self, **kwargs):
            self.calls.append(("predict", kwargs))
            mask = np.zeros((100, 120), dtype=bool)
            mask[55:65, 48:60] = True
            return np.array([mask]), np.array([0.88]), None

    backend = object.__new__(MobileSamBackend)
    backend.predictor = FakePredictor()
    image = np.zeros((100, 120, 3), dtype=np.uint8)

    boxes = backend.detect_from_click(image, x=50, y=60, label="person")

    assert len(boxes) == 1
    assert boxes[0].label == "person"
    assert (boxes[0].x1, boxes[0].y1, boxes[0].x2, boxes[0].y2) == (48, 55, 59, 64)
    assert backend.predictor.calls[0] == ("set_image", image.shape)
    predict_kwargs = backend.predictor.calls[-1][1]
    assert np.array_equal(predict_kwargs["point_coords"], np.array([[50, 60]], dtype=np.float32))


def test_find_similar_finds_second_matching_object():
    backend = ClassicalVisionBackend()
    image = make_scene()
    boxes = backend.find_similar(image, query_box=(40, 60, 130, 120), label="car")

    assert any(box.x1 <= 225 and box.y1 <= 155 and box.x2 >= 305 and box.y2 >= 205 for box in boxes)


def test_mask_to_box_returns_tight_bounds():
    mask = np.zeros((100, 120), dtype=bool)
    mask[20:80, 10:50] = True

    assert mask_to_box(mask, label="object").normalized() == mask_to_box(mask, label="object")
    box = mask_to_box(mask, label="object")
    assert (box.x1, box.y1, box.x2, box.y2) == (10, 20, 49, 79)


def test_locate_anything_backend_builds_prompt_for_selected_labels():
    backend = LocateAnythingBackend(command="/bin/echo", model_path="model.gguf")

    assert backend.build_prompt(["person", "car"]) == (
        "Locate all the instances that matches the following description: person</c>car."
    )


def test_locate_anything_backend_parses_cli_detections():
    backend = LocateAnythingBackend(command="/bin/echo", model_path="model.gguf")
    payload = '{"detections":[{"label":"car","box":[10,20,50,80],"score":0.91}]}'

    boxes = backend.parse_json_boxes(payload, fallback_label="car")

    assert len(boxes) == 1
    assert boxes[0].label == "car"
    assert boxes[0].x1 == 10
    assert boxes[0].y1 == 20
    assert boxes[0].x2 == 50
    assert boxes[0].y2 == 80
    assert boxes[0].score == 0.91


def test_locate_anything_backend_parses_float_coordinates_from_real_cli():
    backend = LocateAnythingBackend(command="/bin/echo", model_path="model.gguf")
    payload = '{"detections":[{"label":"person","box":[117.21,198.02,1165.64,728.00]}]}'

    boxes = backend.parse_json_boxes(payload, fallback_label="person")

    assert boxes[0].x1 == 117
    assert boxes[0].y1 == 198
    assert boxes[0].x2 == 1166
    assert boxes[0].y2 == 728
