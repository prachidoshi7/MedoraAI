"""
MedoraAI — Brain Tumor MRI Classifier
EfficientNetB3 via TensorFlow/Keras, 4-class classification.

Upgraded from the original MobileNetV2 binary classifier to match the
'brain-tumor-mri-90plus-upgraded' notebook pipeline:
  - EfficientNetB3 backbone with progressive 3-phase fine-tuning
  - 4 classes: Glioma, Meningioma, No Tumor, Pituitary
  - 260×260 input with EfficientNet-specific preprocessing
  - Brain contour cropping for noise reduction
  - Optional Test-Time Augmentation (TTA) for higher accuracy
"""

import logging
import os
from dataclasses import dataclass, field
from typing import Optional

import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

# Class labels — must match the training notebook's LABELS list exactly
BRAIN_LABELS = ["Glioma", "Meningioma", "No Tumor", "Pituitary"]
NUM_CLASSES = len(BRAIN_LABELS)
IMG_SIZE = 260  # EfficientNetB3 native resolution


@dataclass
class BrainClassificationResult:
    """Result from brain tumor classification."""
    top_label: str
    confidence: float
    all_scores: dict[str, float]
    severity: str
    tumor_type: str = ""          # specific tumor type for clinical context
    scan_type: str = "brain_mri"


def brain_confidence_to_severity(confidence: float, label: str) -> str:
    """
    Map brain tumor model confidence to clinical severity.

    For specific tumor types, severity accounts for both confidence
    and inherent clinical seriousness of the tumor type.
    """
    if label == "No Tumor":
        return "Normal"

    # Gliomas are inherently more aggressive than pituitary adenomas
    if label == "Glioma":
        if confidence < 0.50:
            return "Moderate"  # Even low-confidence glioma is concerning
        elif confidence < 0.80:
            return "Severe"
        else:
            return "Severe"
    elif label == "Meningioma":
        if confidence < 0.50:
            return "Mild"
        elif confidence < 0.75:
            return "Moderate"
        else:
            return "Severe"
    elif label == "Pituitary":
        if confidence < 0.50:
            return "Mild"
        elif confidence < 0.75:
            return "Moderate"
        else:
            return "Moderate"  # Pituitary tumors are typically less aggressive
    else:
        # Fallback for any unexpected label
        if confidence < 0.50:
            return "Mild"
        elif confidence < 0.75:
            return "Moderate"
        else:
            return "Severe"


def crop_brain_contour(image: np.ndarray) -> np.ndarray:
    """
    Crop MRI to the brain's bounding contour, discarding empty background.
    Ported directly from the training notebook — must match training preprocessing.

    Uses grayscale thresholding + contour extraction to isolate brain anatomy.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (5, 5), 0)

    thresh = cv2.threshold(gray, 45, 255, cv2.THRESH_BINARY)[1]
    thresh = cv2.erode(thresh, None, iterations=2)
    thresh = cv2.dilate(thresh, None, iterations=2)

    cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    cnts = cnts[0] if len(cnts) == 2 else cnts[1]

    if len(cnts) == 0:
        return image  # fall back to original if no contour found

    c = max(cnts, key=cv2.contourArea)

    extLeft = tuple(c[c[:, :, 0].argmin()][0])
    extRight = tuple(c[c[:, :, 0].argmax()][0])
    extTop = tuple(c[c[:, :, 1].argmin()][0])
    extBot = tuple(c[c[:, :, 1].argmax()][0])

    new_image = image[extTop[1]:extBot[1], extLeft[0]:extRight[0]]

    # Safety: if the crop collapsed to nothing (degenerate contour), fall back
    if new_image.size == 0:
        return image

    return new_image


class BrainTumorClassifier:
    """
    EfficientNetB3-based brain tumor 4-class classifier.

    Architecture (from training notebook):
    EfficientNetB3 (ImageNet, 3-phase fine-tuned) → GlobalAvgPool →
    Dense(512, ReLU, L2) → BatchNorm → Dropout(0.4) →
    Dense(128, ReLU, L2) → Dropout(0.3) → Dense(4, softmax)

    Input: 260×260 RGB images, EfficientNet preprocess_input scaling
    Output: 4-class softmax (Glioma, Meningioma, No Tumor, Pituitary)
    """

    def __init__(self, model_path: Optional[str] = None, enable_tta: bool = True):
        """
        Initialize the brain tumor classifier.

        Args:
            model_path: Path to saved .keras model.
            enable_tta: Whether to use Test-Time Augmentation for inference.
        """
        # Suppress TensorFlow info logs
        os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "2")
        import tensorflow as tf
        from tensorflow.keras.applications.efficientnet import preprocess_input

        self.tf = tf
        self.preprocess_fn = preprocess_input
        self.enable_tta = enable_tta
        self.model = None

        logger.info("Loading BrainTumorClassifier (EfficientNetB3, 4-class)...")

        if model_path and os.path.exists(model_path):
            try:
                self.model = tf.keras.models.load_model(model_path)
                logger.info(f"Loaded brain tumor model from {model_path}")
                logger.info(f"  Model input shape: {self.model.input_shape}")
                logger.info(f"  Model output shape: {self.model.output_shape}")
                logger.info(f"  TTA enabled: {self.enable_tta}")
            except Exception as e:
                logger.error(
                    f"CRITICAL: Could not load brain tumor model from {model_path}: {e}. "
                    f"Brain MRI analysis will not work."
                )
        else:
            logger.error(
                f"CRITICAL: Brain tumor model file not found at {model_path}. "
                f"Brain MRI analysis will not work. "
                f"Ensure the .keras model is in the models/ directory."
            )

        if self.model:
            logger.info("BrainTumorClassifier (EfficientNetB3) loaded successfully.")
        else:
            logger.warning("BrainTumorClassifier initialized WITHOUT a trained model.")

    def preprocess(self, image: Image.Image) -> np.ndarray:
        """
        Preprocess a PIL Image for inference.

        Pipeline (matches training notebook exactly):
        1. Convert to RGB numpy array (BGR for OpenCV operations)
        2. Crop brain contour (remove black background)
        3. Resize to 260×260
        4. Convert BGR→RGB
        5. Apply EfficientNet preprocess_input scaling
        6. Expand batch dimension

        Returns numpy array of shape (1, 260, 260, 3).
        """
        # Ensure RGB
        if image.mode != "RGB":
            image = image.convert("RGB")

        # Convert to numpy (OpenCV BGR format for cropping)
        img_array = np.array(image)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)

        # Apply brain contour cropping (same as training)
        img_cropped = crop_brain_contour(img_bgr)

        # Resize to model's expected input size
        img_resized = cv2.resize(img_cropped, (IMG_SIZE, IMG_SIZE))

        # Convert back to RGB (EfficientNet expects RGB)
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

        # Convert to float32 and apply EfficientNet preprocessing
        img_float = img_rgb.astype(np.float32)
        img_preprocessed = self.preprocess_fn(img_float)

        # Add batch dimension
        return np.expand_dims(img_preprocessed, axis=0)

    def _preprocess_raw(self, image: Image.Image) -> np.ndarray:
        """
        Preprocess to uint8 (before EfficientNet scaling) for TTA augmentation.
        Returns numpy array of shape (1, 260, 260, 3) as uint8.
        """
        if image.mode != "RGB":
            image = image.convert("RGB")

        img_array = np.array(image)
        img_bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        img_cropped = crop_brain_contour(img_bgr)
        img_resized = cv2.resize(img_cropped, (IMG_SIZE, IMG_SIZE))
        img_rgb = cv2.cvtColor(img_resized, cv2.COLOR_BGR2RGB)

        return np.expand_dims(img_rgb.astype(np.uint8), axis=0)

    def _tta_predict(self, image: Image.Image, n_variants: int = 5) -> np.ndarray:
        """
        Test-Time Augmentation: average predictions over original + augmented variants.
        Ported from the training notebook's tta_predict function.

        Args:
            image: PIL Image of brain MRI
            n_variants: Total number of prediction variants (including original)

        Returns:
            Averaged softmax probabilities, shape (1, NUM_CLASSES)
        """
        tf = self.tf
        layers = tf.keras.layers

        # Get raw uint8 image for augmentation
        raw = self._preprocess_raw(image)  # (1, 260, 260, 3) uint8
        raw_float = tf.cast(raw, tf.float32)

        preds = []

        # 1. Original (preprocessed, no augmentation)
        base = self.preprocess_fn(raw_float)
        preds.append(self.model.predict(base, verbose=0))

        # 2. Horizontal flip
        flipped = tf.image.flip_left_right(base)
        preds.append(self.model.predict(flipped, verbose=0))

        # 3-5. Small random rotations/zooms
        light_aug = tf.keras.Sequential([
            layers.RandomRotation(factor=0.02),
            layers.RandomZoom(height_factor=(-0.05, 0.05), width_factor=(-0.05, 0.05)),
        ])
        for _ in range(n_variants - 2):
            aug_batch = light_aug(base, training=True)
            preds.append(self.model.predict(aug_batch, verbose=0))

        return np.mean(preds, axis=0)

    def predict(self, image: Image.Image) -> BrainClassificationResult:
        """
        Run inference on a single PIL Image.

        Uses TTA if enabled, otherwise single forward pass.

        Args:
            image: PIL Image of brain MRI

        Returns:
            BrainClassificationResult with top label, confidence, scores, severity
        """
        if self.model is None:
            logger.error("No model loaded — returning default 'No Tumor' result.")
            return BrainClassificationResult(
                top_label="No Tumor",
                confidence=0.0,
                all_scores={label: 0.0 for label in BRAIN_LABELS},
                severity="Normal",
                tumor_type="none",
            )

        if self.enable_tta:
            # TTA: averaged predictions over multiple augmented variants
            probabilities = self._tta_predict(image)
        else:
            # Single forward pass
            preprocessed = self.preprocess(image)
            probabilities = self.model.predict(preprocessed, verbose=0)

        probs = probabilities[0]  # Remove batch dimension → shape (4,)

        # Build scores dict
        all_scores = {
            label: round(float(probs[i]), 4)
            for i, label in enumerate(BRAIN_LABELS)
        }

        # Determine top prediction
        top_idx = int(np.argmax(probs))
        top_label = BRAIN_LABELS[top_idx]
        top_confidence = float(probs[top_idx])

        # Map to severity
        severity = brain_confidence_to_severity(top_confidence, top_label)

        # Tumor type for clinical context
        tumor_type = top_label.lower().replace(" ", "_")

        return BrainClassificationResult(
            top_label=top_label,
            confidence=round(top_confidence, 4),
            all_scores=all_scores,
            severity=severity,
            tumor_type=tumor_type,
            scan_type="brain_mri",
        )

    def get_model(self):
        """Return the underlying Keras model for Grad-CAM access."""
        return self.model
