"""Grad-CAM adapter targeting the kidney CNN's third convolution."""

from services.organ_gradcam import GrayscaleOrganGradCAM


class KidneyGradCAM(GrayscaleOrganGradCAM):
    def __init__(self, classifier):
        super().__init__(classifier, classifier.get_model().conv3, input_size=112)
