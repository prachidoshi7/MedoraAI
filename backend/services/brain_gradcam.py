"""
MedoraAI — Brain Tumor Grad-CAM++ Explainability
TensorFlow/Keras-based Grad-CAM++ for EfficientNetB3 (4-class) using GradientTape.

Upgraded from MobileNetV2 binary to EfficientNetB3 4-class:
  - Targets top_activation (9×9, 1536ch) + block6a_expand_activation (17×17, 816ch)
  - Handles 4-class softmax output (targets predicted class)
  - Model is a flat Functional API (no nested Sequential base model)
  - Multi-scale fusion for spatial accuracy + semantic depth
  - Gaussian smoothing to reduce gradient noise
  - Output at 512×512 for PDF/display quality
"""

import logging

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


class BrainGradCAM:
    """
    Grad-CAM++ explainability for the EfficientNetB3 brain tumor classifier.

    Uses multi-scale Grad-CAM++ to produce spatially accurate heatmaps
    for tumor region localization on brain MRI.

    The model is a flat Functional API model (392 layers), NOT a Sequential
    with a nested base model. All layers are accessed directly from self.model.
    """

    # Output resolution for heatmaps
    HEATMAP_SIZE = 512

    # Target layers — discovered from actual model inspection:
    #   top_activation:              9×9, 1536ch — deepest semantic layer
    #   block6a_expand_activation:  17×17, 816ch — mid-level spatial detail
    #   block4a_expand_activation:  33×33, 288ch — available but too early
    PRIMARY_TARGET = "top_activation"              # 9×9, 1536 channels
    SECONDARY_TARGET = "block6a_expand_activation"  # 17×17, 816 channels

    def __init__(self, classifier):
        """
        Initialize Grad-CAM++ for the EfficientNetB3 brain tumor model.

        Args:
            classifier: BrainTumorClassifier instance
        """
        import tensorflow as tf

        self.tf = tf
        self.model = classifier.get_model()

        if self.model is None:
            logger.warning("BrainGradCAM initialized without a model. Heatmaps will be blank.")
            self._target_layers = []
            return

        # Validate target layers exist in the model
        # EfficientNetB3 Functional model has all layers at top level
        self._target_layers = []

        for target_name in [self.PRIMARY_TARGET, self.SECONDARY_TARGET]:
            try:
                self.model.get_layer(target_name)
                self._target_layers.append(target_name)
            except ValueError:
                logger.warning(f"Target layer '{target_name}' not found in model")

        if not self._target_layers:
            # Fallback: find any conv/activation layer with reasonable spatial dims
            self._target_layers = [self._find_best_conv_layer()]

        logger.info(f"BrainGradCAM++ targeting layers: {self._target_layers}")

    def _find_best_conv_layer(self) -> str:
        """Find the best conv/activation layer for Grad-CAM targeting."""
        best_layer = None
        best_spatial = 0

        for layer in self.model.layers:
            try:
                out = layer.output
                if hasattr(out, 'shape') and len(out.shape) == 4:
                    h = out.shape[1]
                    if h is not None and 4 < h <= 32:
                        if h > best_spatial:
                            best_spatial = h
                            best_layer = layer.name
            except Exception:
                pass

        return best_layer or self.model.layers[-1].name

    def _compute_gradcampp_for_layer(
        self,
        preprocessed_input: np.ndarray,
        target_layer_name: str,
        target_class_idx: int = None,
    ) -> np.ndarray:
        """
        Compute Grad-CAM++ activation map for a single target layer.

        For the 4-class softmax model, we target the predicted class index
        (or a specified class) rather than a single sigmoid output.

        Grad-CAM++ uses second-order and third-order gradients (α weights)
        to produce better localization than standard Grad-CAM:
            α_kc = (∂²y_c/∂A_k²) / (2·(∂²y_c/∂A_k²) + Σ(A_k · ∂³y_c/∂A_k³) + ε)
            w_k = Σ(α_kc · ReLU(∂y_c/∂A_k))

        Args:
            preprocessed_input: (1, 260, 260, 3) numpy array
            target_layer_name: Name of the target layer in the model
            target_class_idx: Which class to compute CAM for (default: argmax)

        Returns:
            Grayscale heatmap (H, W) normalized to [0, 1]
        """
        tf = self.tf

        try:
            conv_layer = self.model.get_layer(target_layer_name)
        except ValueError:
            logger.warning(f"Layer {target_layer_name} not found")
            return np.zeros((9, 9), dtype=np.float32)

        # Build a sub-model: input → [conv_layer_output, final_prediction]
        grad_model = tf.keras.Model(
            inputs=self.model.input,
            outputs=[conv_layer.output, self.model.output],
        )

        # Use persistent tape to compute higher-order gradients
        inputs = tf.cast(preprocessed_input, tf.float32)

        with tf.GradientTape(persistent=True) as tape2:
            with tf.GradientTape(persistent=True) as tape1:
                tape1.watch(inputs)
                conv_outputs, predictions = grad_model(inputs)

                # 4-class softmax: target the predicted class (or specified class)
                if target_class_idx is None:
                    target_class_idx = tf.argmax(predictions[0])
                score = predictions[:, target_class_idx]

            # First-order gradients: ∂score/∂conv_outputs
            grads_1 = tape1.gradient(score, conv_outputs)

        # Second-order gradients: ∂²score/∂conv_outputs²
        grads_2 = tape2.gradient(grads_1, conv_outputs)

        # Clean up persistent tapes
        del tape1, tape2

        if grads_1 is None:
            logger.warning("First-order gradients are None")
            return np.zeros((9, 9), dtype=np.float32)

        # Grad-CAM++ alpha weights computation
        conv_outputs = conv_outputs[0]  # Remove batch dim: (H, W, C)
        grads_1 = grads_1[0]           # (H, W, C)

        if grads_2 is not None:
            grads_2 = grads_2[0]       # (H, W, C)

            # α = grads² / (2·grads² + sum(A·grads³) + ε)
            numerator = grads_2
            denominator = 2.0 * grads_2 + tf.reduce_sum(
                conv_outputs * grads_2 * grads_1, axis=(0, 1), keepdims=True
            ) + 1e-10

            alpha = tf.nn.relu(numerator) / denominator

            # Weighted combination: w_k = Σ_ij(α_kij · ReLU(∂y/∂A_kij))
            weights = tf.reduce_sum(alpha * tf.nn.relu(grads_1), axis=(0, 1))
        else:
            # Fallback to standard Grad-CAM if second-order fails
            weights = tf.reduce_mean(grads_1, axis=(0, 1))

        # Weighted sum of feature maps
        heatmap = tf.reduce_sum(tf.cast(conv_outputs, tf.float32) * tf.cast(weights, tf.float32), axis=-1)

        # Apply ReLU and normalize
        heatmap = tf.maximum(heatmap, 0)
        heatmap_max = tf.reduce_max(heatmap)
        if heatmap_max > 1e-8:
            heatmap = heatmap / heatmap_max

        # Explicit float32 — model trained with mixed_float16 produces float16 tensors,
        # and OpenCV's cv2.resize cannot handle float16 arrays.
        return heatmap.numpy().astype(np.float32)  # (H, W)

    def _fuse_multiscale_cams(
        self,
        preprocessed_input: np.ndarray,
        output_size: int = 260,
        target_class_idx: int = None,
    ) -> np.ndarray:
        """
        Compute Grad-CAM++ from multiple target layers and fuse them.

        Each layer's CAM is resized to a common size and weighted-averaged,
        giving both spatial precision (from higher-res layers) and semantic
        accuracy (from deeper layers).
        """
        cams = []
        weights = []

        for i, layer_name in enumerate(self._target_layers):
            cam = self._compute_gradcampp_for_layer(
                preprocessed_input, layer_name, target_class_idx
            )

            if cam.max() < 1e-6:
                continue

            # Ensure float32 for OpenCV (mixed-precision models may produce float16)
            cam = cam.astype(np.float32)

            # Resize to common size
            cam_resized = cv2.resize(
                cam, (output_size, output_size),
                interpolation=cv2.INTER_CUBIC,
            )

            cams.append(cam_resized)
            # Give more weight to the primary (deeper) layer
            weights.append(0.65 if i == 0 else 0.35)

        if not cams:
            return np.zeros((output_size, output_size), dtype=np.float32)

        # Weighted average
        total_weight = sum(weights)
        fused = sum(c * w for c, w in zip(cams, weights)) / total_weight

        # Normalize to [0, 1]
        fmin, fmax = fused.min(), fused.max()
        if fmax - fmin > 1e-8:
            fused = (fused - fmin) / (fmax - fmin)

        return fused.astype(np.float32)

    @staticmethod
    def _smooth_cam(cam: np.ndarray, sigma: float = 1.5) -> np.ndarray:
        """Apply Gaussian smoothing to reduce gradient noise."""
        ksize = max(3, int(cam.shape[0] * 0.10) | 1)  # Ensure odd
        smoothed = cv2.GaussianBlur(cam, (ksize, ksize), sigma)

        cam_min, cam_max = smoothed.min(), smoothed.max()
        if cam_max - cam_min > 1e-8:
            smoothed = (smoothed - cam_min) / (cam_max - cam_min)
        else:
            smoothed = np.zeros_like(smoothed)

        return smoothed

    def generate_heatmap(
        self,
        image: Image.Image,
        preprocessed_input: np.ndarray,
        target_class_idx: int = None,
    ) -> np.ndarray:
        """
        Generate a Grad-CAM++ heatmap overlay for the brain MRI.

        Uses multi-scale Grad-CAM++ with Gaussian smoothing.

        Args:
            image: Original PIL image (for overlay compositing)
            preprocessed_input: Preprocessed numpy array (1, 260, 260, 3)
            target_class_idx: Which class to visualize (default: predicted class)

        Returns:
            RGB numpy array (HEATMAP_SIZE, HEATMAP_SIZE, 3) uint8.
        """
        if self.model is None:
            return self._blank_overlay(image)

        try:
            # Compute multi-scale fused Grad-CAM++
            heatmap = self._fuse_multiscale_cams(
                preprocessed_input,
                output_size=self.HEATMAP_SIZE,
                target_class_idx=target_class_idx,
            )

            # Apply Gaussian smoothing
            heatmap = self._smooth_cam(heatmap, sigma=2.0)

        except Exception as e:
            logger.warning(f"Grad-CAM++ computation failed: {e}. Returning blank overlay.")
            return self._blank_overlay(image)

        # Convert to JET colormap
        heatmap_colored = cv2.applyColorMap(
            np.uint8(255 * heatmap), cv2.COLORMAP_JET,
        )
        heatmap_colored = cv2.cvtColor(heatmap_colored, cv2.COLOR_BGR2RGB)

        # Prepare original image at output resolution
        sz = self.HEATMAP_SIZE
        img_resized = image.resize((sz, sz)).convert("RGB")
        img_array = np.array(img_resized, dtype=np.float32)

        # Overlay at 40% heatmap / 60% original
        overlay = (0.6 * img_array + 0.4 * heatmap_colored.astype(np.float32))
        overlay = np.clip(overlay, 0, 255).astype(np.uint8)

        logger.info(
            f"Grad-CAM++ generated (max={heatmap.max():.3f}, "
            f"mean={heatmap.mean():.3f}, layers={self._target_layers})"
        )

        return overlay  # (HEATMAP_SIZE, HEATMAP_SIZE, 3) uint8

    def generate_raw_cam(
        self,
        preprocessed_input: np.ndarray,
        target_class_idx: int = None,
    ) -> np.ndarray:
        """
        Return raw Grad-CAM++ activation map (grayscale, 0–1).
        Used for bounding box extraction.
        """
        if self.model is None:
            return np.zeros((260, 260), dtype=np.float32)

        try:
            cam = self._fuse_multiscale_cams(
                preprocessed_input,
                output_size=260,
                target_class_idx=target_class_idx,
            )
            cam = self._smooth_cam(cam, sigma=1.5)
            return cam
        except Exception as e:
            logger.warning(f"Raw CAM generation failed: {e}")
            return np.zeros((260, 260), dtype=np.float32)

    @staticmethod
    def heatmap_to_bboxes(cam: np.ndarray, threshold: float = 0.5) -> list[dict]:
        """Extract bounding boxes from activation map via contour detection."""
        effective_threshold = max(threshold, float(np.quantile(cam, 0.85)))
        binary = (cam > effective_threshold).astype(np.uint8) * 255

        kernel = np.ones((3, 3), np.uint8)
        binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(
            binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE,
        )

        bboxes = []
        image_area = cam.shape[0] * cam.shape[1]
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            box_area = w * h
            if box_area >= max(50, image_area * 0.01) and box_area <= image_area * 0.50:
                bboxes.append({
                    "x1": int(x), "y1": int(y),
                    "x2": int(x + w), "y2": int(y + h),
                    "label": "tumor_region",
                    "confidence": round(float(cam[y:y + h, x:x + w].max()), 4),
                })

        return sorted(bboxes, key=lambda b: b["confidence"], reverse=True)[:5]

    @staticmethod
    def _blank_overlay(image: Image.Image) -> np.ndarray:
        """Return the original image as-is when Grad-CAM++ fails."""
        sz = BrainGradCAM.HEATMAP_SIZE
        img = image.resize((sz, sz)).convert("RGB")
        return np.array(img, dtype=np.uint8)
