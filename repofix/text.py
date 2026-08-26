def compact_text(text: str, max_chars: int) -> tuple[str, int]:
    """Keep the useful beginning and ending while making truncation explicit."""
    if max_chars <= 0:
        return "", len(text)
    if len(text) <= max_chars:
        return text, 0

    marker_template = "\n...[{omitted} chars omitted]...\n"
    marker = marker_template.format(omitted=len(text) - max_chars)
    if len(marker) >= max_chars:
        return text[:max_chars], len(text) - max_chars
    available = max(max_chars - len(marker), 0)
    head_chars = available * 2 // 5
    tail_chars = available - head_chars
    omitted = len(text) - head_chars - tail_chars
    marker = marker_template.format(omitted=omitted)

    # The number of digits in `omitted` can grow the marker by a few chars.
    overflow = head_chars + tail_chars + len(marker) - max_chars
    tail_chars = max(tail_chars - max(overflow, 0), 0)
    omitted = len(text) - head_chars - tail_chars
    marker = marker_template.format(omitted=omitted)
    tail = text[-tail_chars:] if tail_chars else ""
    result = text[:head_chars] + marker + tail
    return result[:max_chars], omitted
