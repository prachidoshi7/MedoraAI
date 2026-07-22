"""Compact local brain-MRI/chest-radiograph gate coefficients.

The model is a regularized logistic classifier over normalized intensity and
edge-orientation features. It was calibrated with augmentation and evaluated
using group-wise holdout so duplicate uploads never appeared across folds.
"""

FEATURE_COUNT = 281

MODEL_PAYLOAD_B64 = (
    "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"
)


class LocalScanTypeModel:
    """Run the bundled compact brain-vs-chest classifier without network I/O."""

    def __init__(self):
        import base64
        import zlib

        import numpy as np

        values = np.frombuffer(
            zlib.decompress(base64.b64decode(MODEL_PAYLOAD_B64)),
            dtype="<f4",
        )
        expected = FEATURE_COUNT * 3 + 1
        if values.size != expected:
            raise RuntimeError("Invalid local scan-type model payload")
        self.mean = values[:FEATURE_COUNT]
        self.scale = values[FEATURE_COUNT:FEATURE_COUNT * 2]
        self.weights = values[FEATURE_COUNT * 2:FEATURE_COUNT * 3]
        self.intercept = float(values[-1])

    @staticmethod
    def _features(image):
        import cv2
        import numpy as np

        gray_u8 = np.asarray(image.convert("L"), dtype=np.uint8)
        low, high = np.percentile(gray_u8, [1.0, 99.0])
        gray = np.clip(
            (gray_u8.astype(np.float32) - low) / max(float(high - low), 1.0),
            0.0,
            1.0,
        )

        grad_x = cv2.Sobel(gray, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(gray, cv2.CV_32F, 0, 1, ksize=3)
        magnitude, angle = cv2.cartToPolar(
            grad_x, grad_y, angleInDegrees=True
        )
        edge_scale = max(float(np.percentile(magnitude, 99.0)), 1e-6)
        edge_map = cv2.resize(
            np.clip(magnitude / edge_scale, 0.0, 1.0),
            (12, 12),
            interpolation=cv2.INTER_AREA,
        ).reshape(-1)
        intensity_map = cv2.resize(
            gray,
            (16, 8),
            interpolation=cv2.INTER_AREA,
        ).reshape(-1)

        unsigned_angle = np.mod(angle, 180.0)
        bins = np.minimum((unsigned_angle / 22.5).astype(np.int32), 7)
        orientation = np.bincount(
            bins.reshape(-1),
            weights=magnitude.reshape(-1),
            minlength=8,
        ).astype(np.float32)
        orientation /= max(float(np.linalg.norm(orientation)), 1e-6)
        aspect_ratio = np.array(
            [gray_u8.shape[1] / max(float(gray_u8.shape[0]), 1.0)],
            dtype=np.float32,
        )
        features = np.concatenate(
            [edge_map, intensity_map, orientation, aspect_ratio]
        ).astype(np.float32)
        if features.size != FEATURE_COUNT:
            raise RuntimeError("Invalid local scan-type feature vector")
        return features

    def brain_probability(self, image) -> float:
        import numpy as np

        features = self._features(image)
        standardized = (features - self.mean) / np.maximum(self.scale, 1e-4)
        logit = float(standardized @ self.weights + self.intercept)
        logit = float(np.clip(logit, -30.0, 30.0))
        return float(1.0 / (1.0 + np.exp(-logit)))
