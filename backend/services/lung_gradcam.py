"""Grad-CAM adapter targeting the lung CNN's fourth convolution."""

from services.organ_gradcam import GrayscaleOrganGradCAM


class LungGradCAM(GrayscaleOrganGradCAM):
    def __init__(self, classifier):
        super().__init__(classifier, classifier.get_model().conv4, input_size=128)
