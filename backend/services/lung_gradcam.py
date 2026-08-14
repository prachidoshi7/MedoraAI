"""Anatomy-aware Grad-CAM++ adapter for the lung CT classifier."""

from services.organ_gradcam import GrayscaleOrganGradCAM


class LungGradCAM(GrayscaleOrganGradCAM):
    def __init__(self, classifier):
        model = classifier.get_model()
        super().__init__(
            classifier,
            [model.bn4, model.bn3],
            input_size=128,
            layer_weights=[0.75, 0.25],
            anatomy_mode="lung_ct",
            region_label="lung_ct_model_attribution",
        )
