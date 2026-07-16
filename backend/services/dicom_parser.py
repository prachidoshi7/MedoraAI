"""
MedoraAI — DICOM Parser
Converts DICOM (.dcm) medical images to PIL Images and extracts metadata.
"""

import logging
from typing import Optional

import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)


def parse_dicom(file_bytes: bytes) -> tuple[Image.Image, dict]:
    """
    Parse a DICOM file and extract image + metadata.
    
    Args:
        file_bytes: Raw bytes of the .dcm file
        
    Returns:
        Tuple of (PIL Image, metadata dict)
        
    Raises:
        ValueError: If DICOM parsing fails
    """
    try:
        import pydicom
        from io import BytesIO

        ds = pydicom.dcmread(BytesIO(file_bytes))

        # Extract pixel data
        pixel_array = ds.pixel_array

        # Normalize to 0–255 range
        if pixel_array.dtype != np.uint8:
            # Apply windowing if available
            if hasattr(ds, "WindowCenter") and hasattr(ds, "WindowWidth"):
                center = float(ds.WindowCenter) if not isinstance(ds.WindowCenter, pydicom.multival.MultiValue) else float(ds.WindowCenter[0])
                width = float(ds.WindowWidth) if not isinstance(ds.WindowWidth, pydicom.multival.MultiValue) else float(ds.WindowWidth[0])
                lower = center - width / 2
                upper = center + width / 2
                pixel_array = np.clip(pixel_array, lower, upper)

            # Normalize to 0–255
            pixel_min = pixel_array.min()
            pixel_max = pixel_array.max()
            if pixel_max > pixel_min:
                pixel_array = ((pixel_array - pixel_min) / (pixel_max - pixel_min) * 255).astype(np.uint8)
            else:
                pixel_array = np.zeros_like(pixel_array, dtype=np.uint8)

        # Convert to PIL Image
        if pixel_array.ndim == 2:
            image = Image.fromarray(pixel_array, mode="L").convert("RGB")
        elif pixel_array.ndim == 3:
            image = Image.fromarray(pixel_array).convert("RGB")
        else:
            raise ValueError(f"Unexpected pixel array shape: {pixel_array.shape}")

        # Extract metadata
        metadata = {
            "patient_id": str(getattr(ds, "PatientID", "UNKNOWN")),
            "modality": str(getattr(ds, "Modality", "Unknown")),
            "study_date": str(getattr(ds, "StudyDate", "")),
            "study_description": str(getattr(ds, "StudyDescription", "")),
            "series_description": str(getattr(ds, "SeriesDescription", "")),
            "institution": str(getattr(ds, "InstitutionName", "")),
            "rows": int(getattr(ds, "Rows", 0)),
            "columns": int(getattr(ds, "Columns", 0)),
        }

        logger.info(f"DICOM parsed: {metadata['modality']}, {metadata['rows']}x{metadata['columns']}")
        return image, metadata

    except ImportError:
        raise ValueError("pydicom is not installed. Install with: pip install pydicom")
    except Exception as e:
        raise ValueError(f"Failed to parse DICOM file: {str(e)}")
