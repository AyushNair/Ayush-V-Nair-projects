"""Small, explainable detectors for a local AI data-loss prevention demo."""
import re


RULES = [
    ("Private key", re.compile(r"-----BEGIN (?:(?:RSA|EC|OPENSSH) )?PRIVATE KEY-----[\s\S]*?(?:-----END (?:(?:RSA|EC|OPENSSH) )?PRIVATE KEY-----|\Z)", re.I), "A private key block was found."),
    ("Cloud access key", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "An AWS access key format was found."),
    ("API token", re.compile(r"\b(?:sk-[A-Za-z0-9_-]{20,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{15,})\b"), "A token-like string was found."),
    ("Email address", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I), "An email address was found."),
    ("US Social Security number", re.compile(r"\b(?!000|666|9\d\d)\d{3}[- ]?(?!00)\d{2}[- ]?(?!0000)\d{4}\b"), "A US SSN format was found."),
    ("Credit card number", re.compile(r"\b(?:\d[ -]*?){13,19}\b"), "A possible payment card number was found (Luhn checked)."),
    ("Phone number", re.compile(r"(?<!\w)(?:\+?\d{1,3}[ .-]?)?(?:\(?\d{3}\)?[ .-]?)\d{3}[ .-]?\d{4}(?!\w)"), "A phone number format was found."),
]


def _luhn(value: str) -> bool:
    digits = [int(ch) for ch in value if ch.isdigit()]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    for index, digit in enumerate(reversed(digits)):
        if index % 2:
            digit *= 2
            if digit > 9:
                digit -= 9
        checksum += digit
    return checksum % 10 == 0


def inspect_text(text: str, enabled_types: set[str] | None = None,
                 custom_keywords: list[str] | None = None) -> list[dict]:
    """Return unique findings with type, explanation, and exact matched span."""
    findings = []
    for label, pattern, explanation in RULES:
        if enabled_types is not None and label not in enabled_types:
            continue
        for match in pattern.finditer(text):
            if label == "Credit card number" and not _luhn(match.group()):
                continue
            findings.append({"type": label, "explanation": explanation,
                             "start": match.start(), "end": match.end()})
    for keyword in dict.fromkeys(k.strip() for k in (custom_keywords or []) if k.strip()):
        if len(keyword) < 2 or len(keyword) > 100:
            continue
        pattern = re.compile(re.escape(keyword), re.I)
        for match in pattern.finditer(text):
            findings.append({"type": "Custom keyword", "explanation": f"Matches your custom policy term: {keyword}.",
                             "start": match.start(), "end": match.end()})
    findings.sort(key=lambda item: item["start"])
    # Avoid reporting overlapping matches twice (for example a phone-like sequence in a card).
    unique = []
    for item in findings:
        if not any(item["start"] < prior["end"] and item["end"] > prior["start"] for prior in unique):
            unique.append(item)
    return unique


def redact_text(text: str, findings: list[dict]) -> str:
    for item in sorted(findings, key=lambda finding: finding["start"], reverse=True):
        text = text[:item["start"]] + f"[REDACTED: {item['type']}]" + text[item["end"]:]
    return text
