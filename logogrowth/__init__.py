"""logogrowth — track a SaaS company's customer/partner logo wall over time."""

from .detect import detect_logos, DetectionResult, Logo

__version__ = "0.1.0"
__all__ = ["detect_logos", "DetectionResult", "Logo"]
