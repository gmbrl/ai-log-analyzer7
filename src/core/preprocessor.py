"""
preprocessor.py — PII / secrets redaction pipeline.

Applies a chain of regex substitutions to sanitize log text before it is
sent to an LLM or displayed in the UI.  Each pattern maps to a safe
placeholder token defined in config.PII_PLACEHOLDERS.

Design principles:
  - Each rule is a (compiled_regex, placeholder) tuple for speed.
  - Rules are applied in priority order so that more-specific patterns
    (JWT, Bearer tokens) are redacted before generic API-key patterns.
  - The function is pure (no side-effects) and returns the sanitized string
    along with a dict summarising how many replacements were made per category.
"""

import re
from dataclasses import dataclass, field
from typing import Dict, Tuple

from src.core.config import PII_PLACEHOLDERS

# ---------------------------------------------------------------------------
# Compiled regex rules — ordered from most-specific to least-specific
# ---------------------------------------------------------------------------

# JWT: three base64url segments separated by dots
_RE_JWT = re.compile(
    r"\beyJ[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\.[A-Za-z0-9\-_]+\b"
)

# Authorization / Bearer tokens (header value or bare token)
_RE_BEARER = re.compile(
    r"(?i)(?:bearer\s+|Authorization:\s*Bearer\s+)([A-Za-z0-9\-._~+/]+=*)",
    re.IGNORECASE,
)

# Generic API key patterns: key=VALUE or key: VALUE where key suggests a secret
_RE_API_KEY = re.compile(
    r"(?i)(?:api[_\-]?key|secret[_\-]?key|access[_\-]?token|auth[_\-]?token)"
    r"(?:\s*[:=]\s*)['\"]?([A-Za-z0-9\-._~+/]{16,})['\"]?",
    re.IGNORECASE,
)

# Passwords in logs (password=VALUE or "password":"VALUE")
_RE_PASSWORD = re.compile(
    r"(?i)(?:password|passwd|pwd)(?:\s*[:=]\s*)['\"]?(\S+)['\"]?",
    re.IGNORECASE,
)

# Credit card numbers — 13-19 digit strings with optional separators
_RE_CREDIT_CARD = re.compile(
    r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}"
    r"|3(?:0[0-5]|[68][0-9])[0-9]{11}|6(?:011|5[0-9]{2})[0-9]{12}"
    r"|(?:2131|1800|35\d{3})\d{11})\b"
)

# US Social Security Numbers: NNN-NN-NNNN
_RE_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

# Email addresses
_RE_EMAIL = re.compile(
    r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"
)

# IPv4 addresses (full octet notation)
_RE_IPV4 = re.compile(
    r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
)

# IPv6 addresses (simplified — matches the most common colon-hex forms)
_RE_IPV6 = re.compile(
    r"\b(?:[0-9a-fA-F]{1,4}:){2,7}[0-9a-fA-F]{1,4}\b"
    r"|::(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{1,4}"
    r"|(?:[0-9a-fA-F]{1,4}:)*[0-9a-fA-F]{1,4}::"
)

# ---------------------------------------------------------------------------
# Ordered rule chain: (category_name, compiled_regex, replacement_template)
# For rules that use capture groups the replacement uses \g<0> to replace the
# entire match while still counting the replacement.
# ---------------------------------------------------------------------------
_RULES: list[Tuple[str, re.Pattern, str]] = [
    ("jwt", _RE_JWT, PII_PLACEHOLDERS["jwt"]),
    ("bearer_token", _RE_BEARER, PII_PLACEHOLDERS["bearer_token"]),
    ("api_key", _RE_API_KEY, PII_PLACEHOLDERS["api_key"]),
    ("password", _RE_PASSWORD, PII_PLACEHOLDERS["password"]),
    ("credit_card", _RE_CREDIT_CARD, PII_PLACEHOLDERS["credit_card"]),
    ("ssn", _RE_SSN, PII_PLACEHOLDERS["ssn"]),
    ("email", _RE_EMAIL, PII_PLACEHOLDERS["email"]),
    ("ipv4", _RE_IPV4, PII_PLACEHOLDERS["ipv4"]),
    ("ipv6", _RE_IPV6, PII_PLACEHOLDERS["ipv6"]),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

@dataclass
class RedactionResult:
    """Holds the sanitized text plus per-category replacement counts."""
    sanitized: str
    counts: Dict[str, int] = field(default_factory=dict)

    @property
    def total_redactions(self) -> int:
        return sum(self.counts.values())

    @property
    def was_modified(self) -> bool:
        return self.total_redactions > 0


def redact(text: str) -> RedactionResult:
    """
    Run the full PII/secrets redaction pipeline on *text*.

    Returns a RedactionResult with the sanitized string and a dict mapping
    each PII category to the number of replacements made.

    Args:
        text: Raw log text (single line or multi-line block).

    Returns:
        RedactionResult
    """
    counts: Dict[str, int] = {}
    sanitized = text

    for category, pattern, placeholder in _RULES:
        # Count occurrences before replacing so we can report them
        matches = pattern.findall(sanitized)
        if matches:
            counts[category] = len(matches)
            sanitized = pattern.sub(placeholder, sanitized)

    return RedactionResult(sanitized=sanitized, counts=counts)


def redact_lines(lines: list[str]) -> Tuple[list[str], Dict[str, int]]:
    """
    Redact a list of log-line strings.

    Returns (redacted_lines, aggregated_counts_dict).
    """
    redacted: list[str] = []
    total_counts: Dict[str, int] = {}

    for line in lines:
        result = redact(line)
        redacted.append(result.sanitized)
        for cat, count in result.counts.items():
            total_counts[cat] = total_counts.get(cat, 0) + count

    return redacted, total_counts


def redact_dataframe_column(series):  # type: ignore[no-untyped-def]
    """
    Convenience wrapper: applies redact() to a pandas Series of strings.
    Returns a new Series with sanitized values.
    """
    return series.apply(lambda v: redact(str(v)).sanitized if isinstance(v, str) else v)
