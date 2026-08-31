"""Untrusted-content boundaries for the LLM evaluator's prompt.

Used only by Arm B (``defense="delimited"``) of the prompt-boundary experiment.
Arm A, the control, never calls anything here: its prompt must stay byte-identical
to what SlopLab has always measured.

Why neutralization comes first
------------------------------
Wrapping adversarial text in ``--- BEGIN/END UNTRUSTED REPORT ---`` markers is
only a defense if the text cannot forge the closing marker and escape the fence.
A report that contains its own ``--- END UNTRUSTED REPORT ---`` would otherwise
end the fence early and have everything after it read as prompt, not as data - so
Arm B would measure a defense that is not there.

Detection runs on a normalized view, not on the raw text
--------------------------------------------------------
Matching the literal ASCII marker is not enough, because a model reads far more
than ASCII as a boundary. All of these were live bypasses of an earlier
literal-matching version of this module:

- ``END\\nUNTRUSTED REPORT`` - the words split across two lines
- a non-breaking space used as the separator
- a zero-width space inside the word (``UNTR<U+200B>USTED``)
- a Cyrillic ``Е`` in place of Latin ``E``

So each pass builds a *detection view* of the text - format characters (zero
width, bidi controls) dropped, per-character NFKC applied, and a small confusables
table folded - matches on that view, and maps the matched spans back to the
original text through an index built alongside. The original is what gets edited;
the view only decides where.

**Known limit:** the confusables table covers Cyrillic and Greek lookalikes for
the letters the markers actually use. Lookalikes from other scripts are not
folded. This is a bounded, deliberate gap, not an oversight - a complete
confusables mapping is a data problem this module does not try to own. The
architecture question behind it (a per-case nonce delimiter would make forgery
impossible by construction and need no stripping at all) is recorded in
docs/review-brief-injection-arm.md for review rather than decided here.

The replacement is a non-empty, marker-free token, which is what defeats
reassembly attacks like ``--- END UNTR--- END UNTRUSTED ---USTED ---``: deleting
the inner marker outright would splice the outer fragments into a working one,
whereas substituting an inert token keeps them apart. Passes repeat to a fixpoint
as defense in depth.

The bare ``---`` fence is neutralized too. Arm A's own fence is exactly that, so
it is forgeable by a report - by injection today, and by an ordinary Markdown
horizontal rule tomorrow.
"""

from __future__ import annotations

import re
import unicodedata

BEGIN_MARKER = "--- BEGIN UNTRUSTED REPORT ---"
END_MARKER = "--- END UNTRUSTED REPORT ---"

#: Inert stand-in. Contains no dashes and no marker vocabulary, so no combination
#: of surrounding text can reassemble a boundary through it.
REPLACEMENT = "[boundary marker removed]"

#: Cyrillic and Greek lookalikes for the letters used in BEGIN / END / UNTRUSTED
#: / REPORT. Folded only in the detection view, never in the emitted text.
_CONFUSABLES: dict[str, str] = {
    # Cyrillic
    "В": "B",  # В
    "Е": "E",  # Е
    "І": "I",  # І
    "Р": "P",  # Р
    "Ѕ": "S",  # Ѕ
    "Т": "T",  # Т
    "О": "O",  # О
    "А": "A",  # А
    "е": "e",  # е
    "о": "o",  # о
    "р": "p",  # р
    "т": "t",  # т
    # Greek
    "Β": "B",  # Β
    "Ε": "E",  # Ε
    "Ι": "I",  # Ι
    "Ν": "N",  # Ν
    "Ο": "O",  # Ο
    "Ρ": "P",  # Ρ
    "Τ": "T",  # Τ
    "Γ": "G",  # Γ (shape-adjacent; folded conservatively)
}

#: Separator between marker words: intra-line whitespace and at most one line
#: break. May be empty, which is required - dropping a zero-width space leaves
#: ``ENDUNTRUSTED`` with no separator at all.
_SEP = r"[^\S\r\n]*(?:\r?\n)?[^\S\r\n]*"

#: Any dash-decorated BEGIN/END UNTRUSTED marker, in any case, with or without
#: the trailing "REPORT" and with any number of surrounding dashes.
_MARKER_RE = re.compile(
    rf"-*{_SEP}\b(?:BEGIN|END){_SEP}UNTRUSTED(?:{_SEP}REPORT)?\b{_SEP}-*",
    re.IGNORECASE,
)

#: A line consisting only of three or more dashes - Arm A's fence.
_FENCE_RE = re.compile(r"^[^\S\r\n]*-{3,}[^\S\r\n]*$", re.MULTILINE)

_MAX_PASSES = 8


class BoundaryError(Exception):
    """Raised when a wrapped prompt does not hold exactly one marker pair."""


def detection_view(text: str) -> tuple[str, list[int]]:
    """Normalized copy used for matching, plus each kept char's source index.

    Format characters are dropped rather than mapped: they are invisible to a
    reader and to a model, so leaving them in would let ``UNTR<U+200B>USTED``
    hide from the pattern while still reading as ``UNTRUSTED``.
    """
    chars: list[str] = []
    index: list[int] = []
    for position, char in enumerate(text):
        if unicodedata.category(char) == "Cf":
            continue
        folded = unicodedata.normalize("NFKC", char)
        simple = folded if len(folded) == 1 else char
        chars.append(_CONFUSABLES.get(simple, simple))
        index.append(position)
    return "".join(chars), index


def _spans_in_original(view: str, index: list[int]) -> list[tuple[int, int]]:
    """Marker spans found in the view, expressed as ranges over the original."""
    found: list[tuple[int, int]] = []
    for pattern in (_MARKER_RE, _FENCE_RE):
        for match in pattern.finditer(view):
            if match.end() <= match.start():
                continue
            found.append((index[match.start()], index[match.end() - 1] + 1))
    if not found:
        return []

    found.sort()
    merged: list[tuple[int, int]] = [found[0]]
    for start, end in found[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))
    return merged


def neutralize_boundaries(text: str) -> tuple[str, list[str]]:
    """Strip boundary-looking markers from untrusted content.

    Returns the cleaned text and the markers that were replaced, in the order
    encountered. The list is provenance: Arm B modifies the content as well as
    fencing it, and recording what changed keeps that visible instead of hidden.
    """
    removed: list[str] = []
    cleaned = text
    for _pass in range(_MAX_PASSES):
        view, index = detection_view(cleaned)
        spans = _spans_in_original(view, index)
        if not spans:
            break
        pieces: list[str] = []
        cursor = 0
        for start, end in spans:
            pieces.append(cleaned[cursor:start])
            removed.append(cleaned[start:end])
            pieces.append(REPLACEMENT)
            cursor = end
        pieces.append(cleaned[cursor:])
        cleaned = "".join(pieces)
    return cleaned, removed


def wrap_untrusted(text: str) -> tuple[str, list[str]]:
    """Neutralize ``text``, then fence it as untrusted content.

    Returns the wrapped block and the neutralized markers. Raises
    :class:`BoundaryError` if the result does not contain exactly one marker
    pair - that would mean the neutralizer let a forgery through, which is a
    defect in this module rather than a property of the report.

    The check runs over the detection view, not the raw text: counting literal
    ASCII markers would pass every bypass this module exists to stop.
    """
    cleaned, removed = neutralize_boundaries(text)
    wrapped = f"{BEGIN_MARKER}\n{cleaned}\n{END_MARKER}"

    view, _index = detection_view(wrapped)
    begins = len(list(re.finditer(r"BEGIN" + _SEP + "UNTRUSTED", view, re.IGNORECASE)))
    ends = len(list(re.finditer(r"\bEND" + _SEP + "UNTRUSTED", view, re.IGNORECASE)))
    if begins != 1 or ends != 1:
        raise BoundaryError(
            f"wrapped content does not hold exactly one marker pair (begin={begins}, end={ends})"
        )
    return wrapped, removed
