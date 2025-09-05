from __future__ import annotations

from typing import Optional


def mic_reason(value: float, s_max: Optional[float], i_range: Optional[tuple[float, float]], r_min: Optional[float], version: Optional[str]) -> str:
    parts: list[str] = [f"MIC {value}"]
    if s_max is not None:
        parts.append(f"<= susceptible_max {s_max}")
    if i_range is not None:
        parts.append(f"I range {i_range[0]}–{i_range[1]}")
    if r_min is not None:
        parts.append(f">= resistant_min {r_min}")
    if version:
        parts.append(f"({version})")
    return " ".join(parts)


def disc_reason(value: float, s_min: Optional[float], i_range: Optional[tuple[float, float]], r_max: Optional[float], version: Optional[str]) -> str:
    parts: list[str] = [f"Zone {value} mm"]
    if s_min is not None:
        parts.append(f">= susceptible_min {s_min}")
    if i_range is not None:
        parts.append(f"I range {i_range[0]}–{i_range[1]} mm")
    if r_max is not None:
        parts.append(f"<= resistant_max {r_max}")
    if version:
        parts.append(f"({version})")
    return " ".join(parts)

