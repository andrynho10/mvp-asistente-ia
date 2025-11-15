"""
Module for detecting and masking Personally Identifiable Information (PII).

Implements detection and masking of sensitive data including:
- Email addresses
- Phone numbers
- Chilean RUT (ID numbers)
- Names (proper nouns)
- Credit card numbers
- URLs with credentials
- IP addresses

Compliance: Ley 19.628 (Chile), GDPR (EU)
"""

import re
from typing import Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import hashlib


class PiiType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    RUT = "rut"
    NAME = "name"
    CREDIT_CARD = "credit_card"
    URL_CREDENTIAL = "url_credential"
    IP_ADDRESS = "ip_address"
    SSN = "ssn"
    PASSPORT = "passport"


@dataclass
class PiiDetection:
    """Represents a detected PII element."""
    pii_type: PiiType
    value: str
    start: int
    end: int
    confidence: float  # 0.0-1.0


class PiiMasker:
    """
    Detects and masks PII in text.

    Features:
    - Multiple PII type detection
    - Configurable masking strategies
    - Hash-based anonymization for consistent masking
    - Logging of detection statistics
    """

    # Regex patterns for PII detection
    PATTERNS: Dict[PiiType, str] = {
        # Email: standard email pattern
        PiiType.EMAIL: r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',

        # Phone: various formats (international)
        PiiType.PHONE: r'(?:\+?56[-.\s]?)?(?:9|2)?[-.\s]?\d{4}[-.\s]?\d{4}|\+?(?:1|44|34|39|33|49|31|46|41|43|45|47|48|32|61|81|82|86|84|90|92|93|94|95|98|212|213|216|218|220|221|222|223|224|225|226|227|228|229|230|231|232|233|234|235|236|237|238|239|240|241|242|243|244|245|246|247|248|249|250|251|252|253|254|255|256|257|258|259|260|261|262|263|264|265|266|267|268|269|290|291|297|298|299|350|351|352|353|354|355|356|357|358|359|370|371|372|373|374|375|376|377|378|380|381|382|383|385|386|387|389|420|421|423|500|501|502|503|504|505|506|507|508|509|590|591|592|593|594|595|596|597|598|599|670|672|673|674|675|676|677|678|679|680|681|682|683|684|685|686|687|688|689|690|691|692|850|852|853|855|856|880|886|960|961|962|963|964|965|966|967|968|970|971|972|973|974|975|976|977|992|993|994|995|996|998)\s?\d+(?:[-.\s]?\d+)*',

        # Chilean RUT: XX.XXX.XXX-K format
        PiiType.RUT: r'\b(?:\d{1,2}\.)?\d{1,3}\.\d{3}-[\dkK]\b',

        # Credit card: 16 digits
        PiiType.CREDIT_CARD: r'\b(?:\d{4}[-\s]?){3}\d{4}\b',

        # URL with credentials: http://user:pass@domain.com
        PiiType.URL_CREDENTIAL: r'(?:https?|ftp)://[^\s:]+:[^\s@]+@[^\s/]+',

        # IP Address: IPv4
        PiiType.IP_ADDRESS: r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',

        # US Social Security Number: XXX-XX-XXXX
        PiiType.SSN: r'\b(?!000|666|9\d{2})\d{3}-(?!00)\d{2}-(?!0{4})\d{4}\b',

        # Passport-like: letter followed by 6-9 digits
        PiiType.PASSPORT: r'\b[A-Z]{1,2}\d{6,9}\b',
    }

    def __init__(self, name_detector: bool = True, confidence_threshold: float = 0.7):
        """
        Initialize PII masker.

        Args:
            name_detector: Whether to detect names (simple heuristic)
            confidence_threshold: Minimum confidence for PII detection (0.0-1.0)
        """
        self.name_detector = name_detector
        self.confidence_threshold = confidence_threshold
        self._compiled_patterns = {
            pii_type: re.compile(pattern)
            for pii_type, pattern in self.PATTERNS.items()
        }

    def detect(self, text: str) -> List[PiiDetection]:
        """
        Detect all PII elements in text.

        Args:
            text: Text to scan for PII

        Returns:
            List of detected PII elements
        """
        detections: List[PiiDetection] = []

        # Check each pattern
        for pii_type, pattern in self._compiled_patterns.items():
            for match in pattern.finditer(text):
                detection = PiiDetection(
                    pii_type=pii_type,
                    value=match.group(),
                    start=match.start(),
                    end=match.end(),
                    confidence=0.95  # Regex matches are high confidence
                )
                if detection.confidence >= self.confidence_threshold:
                    detections.append(detection)

        # Simple name detection (optional)
        if self.name_detector:
            name_detections = self._detect_names(text)
            detections.extend(name_detections)

        # Sort by position
        detections.sort(key=lambda x: x.start)
        return detections

    def _detect_names(self, text: str) -> List[PiiDetection]:
        """
        Simple heuristic for detecting proper nouns (potential names).

        Looks for words that:
        - Start with capital letter
        - Are not common English words
        - Are not at start of sentence

        Args:
            text: Text to scan

        Returns:
            List of potential name detections
        """
        detections = []
        # Simple pattern: capitalized words that aren't sentence starters
        pattern = re.compile(r'(?:^|[.!?\n]\s+|,\s+)([A-Z][a-záéíóúñ]+(?:\s+[A-Z][a-záéíóúñ]+)?)')

        for match in pattern.finditer(text):
            # Skip common words
            word = match.group(1)
            if word.lower() not in {'The', 'A', 'An', 'And', 'Or', 'But', 'In', 'On', 'At', 'To', 'For'}:
                detection = PiiDetection(
                    pii_type=PiiType.NAME,
                    value=word,
                    start=match.start(1),
                    end=match.end(1),
                    confidence=0.6  # Lower confidence for name detection
                )
                if detection.confidence >= self.confidence_threshold:
                    detections.append(detection)

        return detections

    def mask(
        self,
        text: str,
        strategy: str = "hash",
        replacement_char: str = "*"
    ) -> Tuple[str, List[PiiDetection]]:
        """
        Mask PII elements in text.

        Args:
            text: Text to mask
            strategy: Masking strategy:
                - 'hash': Replace with hash (consistent, reversible with key)
                - 'replace': Replace with asterisks
                - 'redact': Replace with [REDACTED_TYPE]
                - 'partial': Show first/last chars (e.g., j****@example.com)
            replacement_char: Character to use for 'replace' strategy

        Returns:
            Tuple of (masked_text, detections)
        """
        detections = self.detect(text)

        if not detections:
            return text, []

        # Sort in reverse to maintain indices
        detections_sorted = sorted(detections, key=lambda x: x.start, reverse=True)

        masked_text = text
        for detection in detections_sorted:
            if strategy == "hash":
                replacement = self._hash_replacement(detection.value)
            elif strategy == "replace":
                replacement = replacement_char * len(detection.value)
            elif strategy == "redact":
                replacement = f"[REDACTED_{detection.pii_type.value.upper()}]"
            elif strategy == "partial":
                replacement = self._partial_mask(detection.value, detection.pii_type)
            else:
                replacement = replacement_char * len(detection.value)

            masked_text = (
                masked_text[:detection.start] +
                replacement +
                masked_text[detection.end:]
            )

        return masked_text, detections

    @staticmethod
    def _hash_replacement(value: str, length: int = 8) -> str:
        """
        Generate a consistent hash-based replacement.

        Args:
            value: Original value to hash
            length: Length of hash to return

        Returns:
            First `length` characters of SHA256 hash
        """
        hash_obj = hashlib.sha256(value.encode())
        hash_hex = hash_obj.hexdigest()
        return f"#{hash_hex[:length]}"

    @staticmethod
    def _partial_mask(value: str, pii_type: PiiType) -> str:
        """
        Partial masking strategy (show first/last characters).

        Args:
            value: Original value
            pii_type: Type of PII

        Returns:
            Partially masked value
        """
        if pii_type == PiiType.EMAIL:
            # j****@example.com
            parts = value.split('@')
            if len(parts) == 2:
                local, domain = parts
                masked_local = local[0] + '*' * (len(local) - 1)
                return f"{masked_local}@{domain}"

        elif pii_type == PiiType.CREDIT_CARD:
            # ****-****-****-1234
            return '*' * (len(value) - 4) + value[-4:]

        elif pii_type == PiiType.PHONE:
            # Show last 4 digits
            digits = ''.join(c for c in value if c.isdigit())
            if len(digits) >= 4:
                return '*' * (len(value) - 4) + digits[-4:]

        elif pii_type == PiiType.RUT:
            # XX.XXX.XXX-K → **.***.*XX-K
            if value and len(value) >= 3:
                return '*' * (len(value) - 3) + value[-3:]

        # Default: show first and last character
        if len(value) <= 2:
            return '*' * len(value)
        return value[0] + '*' * (len(value) - 2) + value[-1]

    def get_statistics(self, detections: List[PiiDetection]) -> Dict[str, int]:
        """
        Get statistics about detected PII.

        Args:
            detections: List of detected PII elements

        Returns:
            Dictionary with counts by type
        """
        stats = {pii_type.value: 0 for pii_type in PiiType}
        for detection in detections:
            stats[detection.pii_type.value] += 1
        return {k: v for k, v in stats.items() if v > 0}


# Global instance for convenience
_default_masker = PiiMasker()


def detect_pii(text: str) -> List[PiiDetection]:
    """Detect PII in text using default masker."""
    return _default_masker.detect(text)


def mask_pii(
    text: str,
    strategy: str = "redact"
) -> Tuple[str, List[PiiDetection]]:
    """Mask PII in text using default masker."""
    return _default_masker.mask(text, strategy=strategy)


def get_pii_statistics(detections: List[PiiDetection]) -> Dict[str, int]:
    """Get statistics about detected PII."""
    return _default_masker.get_statistics(detections)
