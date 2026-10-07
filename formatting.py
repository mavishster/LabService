import re


_NUMBER_PATTERN = r"[-+]?(?:\d+(?:[.,]\d*)?|[.,]\d+)(?:[eE][-+]?\d+)?"
_RANGE_PATTERN = re.compile(
    rf"^\s*({_NUMBER_PATTERN})\s*[-–]\s*"
    rf"({_NUMBER_PATTERN})(?:\s+.*)?\s*$"
)
_VALUE_PATTERN = re.compile(rf"^\s*({_NUMBER_PATTERN})")


def parse_range(ref):
    match = _RANGE_PATTERN.fullmatch(str(ref or ""))
    if not match:
        return None, None

    low, high = (
        float(value.replace(",", "."))
        for value in match.groups()
    )
    return low, high


def get_status(value, ref_range, flag):
    normalized_flag = str(flag or "").strip().upper()
    if normalized_flag in {"H", "HH"}:
        return "high"
    if normalized_flag in {"L", "LL"}:
        return "low"

    low, high = parse_range(ref_range)
    if low is None or high is None:
        return None

    match = _VALUE_PATTERN.match(str(value or ""))
    if not match:
        return None

    numeric_value = float(match.group(1).replace(",", "."))

    if numeric_value > high:
        return "high"
    if numeric_value < low:
        return "low"
    return None


def colorize(value, status):
    if status == "high":
        return (
            '<span style="color:#d32f2f;font-weight:bold">'
            f"{value}</span>"
        )
    if status == "low":
        return (
            '<span style="color:#1976d2;font-weight:bold">'
            f"{value}</span>"
        )
    return value
