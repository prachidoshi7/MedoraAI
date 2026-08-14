"""Anatomy-aware Grad-CAM++ adapter for the kidney ultrasound classifier."""

from services.organ_gradcam import GrayscaleOrganGradCAM


class KidneyGradCAM(GrayscaleOrganGradCAM):
    def __init__(self, classifier):
        model = classifier.get_model()
        super().__init__(
            classifier,
            [model.bn3, model.bn2],
            input_size=112,
            layer_weights=[0.75, 0.25],
            anatomy_mode="kidney_ultrasound",
            region_label="kidney_model_attribution",
        )
