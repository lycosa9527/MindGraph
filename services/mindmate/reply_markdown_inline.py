"""Inline markdown spans for MindMate reply documents, including math."""

from __future__ import annotations

import re
from dataclasses import dataclass

_LINK_RE = re.compile(r"\[([^\]\n]+)\]\(([^)\s]+)\)")
_ILLEGAL_XML_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F]")

_SUPER_MAP = {
    "0": "⁰",
    "1": "¹",
    "2": "²",
    "3": "³",
    "4": "⁴",
    "5": "⁵",
    "6": "⁶",
    "7": "⁷",
    "8": "⁸",
    "9": "⁹",
    "+": "⁺",
    "-": "⁻",
    "=": "⁼",
    "(": "⁽",
    ")": "⁾",
    "n": "ⁿ",
    "i": "ⁱ",
}
_SUB_MAP = {
    "0": "₀",
    "1": "₁",
    "2": "₂",
    "3": "₃",
    "4": "₄",
    "5": "₅",
    "6": "₆",
    "7": "₇",
    "8": "₈",
    "9": "₉",
    "+": "₊",
    "-": "₋",
    "=": "₌",
    "(": "₍",
    ")": "₎",
    "a": "ₐ",
    "e": "ₑ",
    "i": "ᵢ",
    "o": "ₒ",
    "r": "ᵣ",
    "u": "ᵤ",
    "x": "ₓ",
}
_COMMANDS = {
    "times": "×",
    "cdot": "·",
    "div": "÷",
    "pm": "±",
    "mp": "∓",
    "leq": "≤",
    "le": "≤",
    "geq": "≥",
    "ge": "≥",
    "neq": "≠",
    "ne": "≠",
    "approx": "≈",
    "equiv": "≡",
    "sim": "∼",
    "propto": "∝",
    "infty": "∞",
    "partial": "∂",
    "nabla": "∇",
    "forall": "∀",
    "exists": "∃",
    "in": "∈",
    "notin": "∉",
    "subset": "⊂",
    "subseteq": "⊆",
    "cup": "∪",
    "cap": "∩",
    "to": "→",
    "rightarrow": "→",
    "leftarrow": "←",
    "Rightarrow": "⇒",
    "Leftarrow": "⇐",
    "leftrightarrow": "↔",
    "ldots": "…",
    "cdots": "⋯",
    "dots": "…",
    "degree": "°",
    "circ": "∘",
    "angle": "∠",
    "triangle": "△",
    "perp": "⊥",
    "parallel": "∥",
    "int": "∫",
    "sum": "∑",
    "prod": "∏",
    "langle": "⟨",
    "rangle": "⟩",
    "pi": "π",
    "alpha": "α",
    "beta": "β",
    "gamma": "γ",
    "delta": "δ",
    "theta": "θ",
    "lambda": "λ",
    "mu": "μ",
    "sigma": "σ",
    "omega": "ω",
    "Delta": "Δ",
    "Omega": "Ω",
    "Sigma": "Σ",
    "Pi": "Π",
    "vert": "|",
    "lvert": "|",
    "rvert": "|",
    "mid": "|",
    "quad": " ",
    "qquad": "  ",
    "left": "",
    "right": "",
    "bigl": "",
    "bigr": "",
    "Bigl": "",
    "Bigr": "",
    "biggl": "",
    "biggr": "",
    "Biggl": "",
    "Biggr": "",
    "big": "",
    "Big": "",
    "bigg": "",
    "Bigg": "",
}
_TEXT_COMMANDS = frozenset({"text", "mathrm", "mathbf", "mathit", "textbf", "textit", "operatorname", "mbox"})
_FRAC_COMMANDS = frozenset({"frac", "dfrac", "tfrac", "cfrac"})
_ESCAPED_SYMBOLS = {
    "\\": "\\",
    "%": "%",
    "&": "&",
    "#": "#",
    "_": "_",
    "{": "{",
    "}": "}",
    "$": "$",
    ",": " ",
    ";": " ",
    ":": " ",
    "!": "",
    " ": " ",
}


@dataclass(frozen=True)
class InlineSpan:
    """One styled slice of a markdown line."""

    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    math: bool = False
    strike: bool = False
    link: str = ""


@dataclass(frozen=True)
class _Token:
    spans: tuple[InlineSpan, ...]
    next_index: int


class _LatexReader:
    """Walk a LaTeX math snippet and emit readable text."""

    def __init__(self, source: str) -> None:
        self.source = source
        self.index = 0

    def _eof(self) -> bool:
        return self.index >= len(self.source)

    def _peek(self) -> str:
        if self._eof():
            return ""
        return self.source[self.index]

    def _advance(self) -> str:
        char = self._peek()
        if char:
            self.index += 1
        return char

    def _skip_spaces(self) -> None:
        while not self._eof() and self._peek().isspace():
            self._advance()

    def read_sequence(self, *, stop: str = "") -> str:
        """Read atoms until `stop` or the end of the snippet."""
        parts: list[str] = []
        while not self._eof():
            if stop and self._peek() == stop:
                break
            parts.append(self.read_atom())
        return "".join(parts)

    def read_atom(self) -> str:
        """Read one math atom: group, script, command, or character."""
        if self._eof():
            return ""
        char = self._peek()
        if char.isspace():
            self._advance()
            while not self._eof() and self._peek().isspace():
                self._advance()
            return " "
        if char == "{":
            self._advance()
            body = self.read_sequence(stop="}")
            if self._peek() == "}":
                self._advance()
            return body
        if char == "}":
            self._advance()
            return ""
        if char in "^_":
            superscript = char == "^"
            self._advance()
            return _to_script(self._read_script_body(), superscript=superscript)
        if char == "\\":
            return self._read_command()
        self._advance()
        return char

    def _read_script_body(self) -> str:
        self._skip_spaces()
        if self._eof():
            return ""
        if self._peek() in "{\\":
            return self.read_atom()
        return self._advance()

    def _read_required_group(self) -> str:
        self._skip_spaces()
        return self.read_atom()

    def _read_command(self) -> str:
        self._advance()
        if self._eof():
            return ""
        char = self._peek()
        if not char.isalpha():
            self._advance()
            return _ESCAPED_SYMBOLS.get(char, char)
        start = self.index
        while not self._eof() and self._peek().isalpha():
            self._advance()
        name = self.source[start : self.index]
        if name in _FRAC_COMMANDS:
            return _format_frac(self._read_required_group(), self._read_required_group())
        if name == "sqrt":
            return self._read_sqrt()
        if name == "binom":
            upper = self._read_required_group().strip()
            lower = self._read_required_group().strip()
            return f"C({upper}, {lower})"
        if name == "placeholder":
            return self._read_placeholder()
        if name in _TEXT_COMMANDS:
            return self._read_required_group()
        mapped = _COMMANDS.get(name)
        if mapped is None:
            return name
        return mapped

    def _read_sqrt(self) -> str:
        degree = ""
        self._skip_spaces()
        if self._peek() == "[":
            self._advance()
            degree = self.read_sequence(stop="]").strip()
            if self._peek() == "]":
                self._advance()
        return _format_sqrt(self._read_required_group(), degree)

    def _read_placeholder(self) -> str:
        self._skip_spaces()
        if self._peek() != "{":
            return "□"
        inner = self.read_atom().strip()
        return inner or "□"


def linearize_latex(source: str) -> str:
    """Turn a LaTeX math snippet into readable plain text."""
    return _LatexReader(source.strip()).read_sequence().strip()


def clean_docx_text(text: str) -> str:
    """Drop control characters that Word rejects inside a run."""
    return _ILLEGAL_XML_RE.sub("", text)


def inline_plain_text(text: str) -> str:
    """Visible text of one markdown line, without markers or math delimiters."""
    return "".join(span.text for span in parse_inline(text))


def parse_inline(text: str, *, bold: bool = False, italic: bool = False) -> list[InlineSpan]:
    """Split one markdown line into styled spans, including `$...$` math."""
    spans: list[InlineSpan] = []
    buffer: list[str] = []
    index = 0
    while index < len(text):
        token = _try_token(text, index, bold=bold, italic=italic)
        if token is None:
            buffer.append(text[index])
            index += 1
            continue
        _flush(spans, buffer, bold=bold, italic=italic)
        spans.extend(token.spans)
        index = token.next_index
    _flush(spans, buffer, bold=bold, italic=italic)
    return _merge(spans)


def _flush(spans: list[InlineSpan], buffer: list[str], *, bold: bool, italic: bool) -> None:
    if not buffer:
        return
    spans.append(InlineSpan("".join(buffer), bold=bold, italic=italic))
    buffer.clear()


def _merge(spans: list[InlineSpan]) -> list[InlineSpan]:
    merged: list[InlineSpan] = []
    for span in spans:
        if not span.text:
            continue
        if merged and _same_style(merged[-1], span):
            previous = merged[-1]
            merged[-1] = InlineSpan(
                previous.text + span.text,
                bold=previous.bold,
                italic=previous.italic,
                code=previous.code,
                math=previous.math,
                strike=previous.strike,
                link=previous.link,
            )
            continue
        merged.append(span)
    return merged


def _same_style(left: InlineSpan, right: InlineSpan) -> bool:
    return (
        left.bold == right.bold
        and left.italic == right.italic
        and left.code == right.code
        and left.math == right.math
        and left.strike == right.strike
        and left.link == right.link
    )


def _try_token(text: str, index: int, *, bold: bool, italic: bool) -> _Token | None:
    math = _try_math(text, index, bold=bold, italic=italic)
    if math is not None:
        return math
    emphasis = _try_emphasis(text, index, bold=bold, italic=italic)
    if emphasis is not None:
        return emphasis
    code = _try_code(text, index, bold=bold, italic=italic)
    if code is not None:
        return code
    strike = _try_strike(text, index, bold=bold, italic=italic)
    if strike is not None:
        return strike
    link = _try_link(text, index, bold=bold, italic=italic)
    if link is not None:
        return link
    return _try_backslash(text, index, bold=bold, italic=italic)


def _span(text: str, *, bold: bool, italic: bool, code: bool = False, math: bool = False) -> InlineSpan:
    return InlineSpan(text, bold=bold, italic=italic, code=code, math=math)


def _try_math(text: str, index: int, *, bold: bool, italic: bool) -> _Token | None:
    display = _delimited(text, index, "$$", "$$")
    if display is not None:
        return _math_token(display[0], display[1], bold=bold, italic=italic)
    bracket = _delimited(text, index, r"\[", r"\]")
    if bracket is not None:
        return _math_token(bracket[0], bracket[1], bold=bold, italic=italic)
    inline_paren = _delimited(text, index, r"\(", r"\)")
    if inline_paren is not None:
        return _math_token(inline_paren[0], inline_paren[1], bold=bold, italic=italic)
    if text[index] != "$":
        return None
    if not _dollar_can_open(text, index):
        return None
    end = _closing_dollar(text, index + 1)
    if end is None:
        return None
    return _math_token(text[index + 1 : end], end + 1, bold=bold, italic=italic)


def _math_token(body: str, next_index: int, *, bold: bool, italic: bool) -> _Token | None:
    linear = linearize_latex(body)
    if not linear:
        return None
    return _Token((_span(linear, bold=bold, italic=italic, math=True),), next_index)


def _dollar_can_open(text: str, index: int) -> bool:
    if index > 0 and _is_ascii_word(text[index - 1]):
        return False
    if index + 1 >= len(text) or text[index + 1] in " $\t":
        return False
    return True


def _closing_dollar(text: str, start: int) -> int | None:
    end = text.find("$", start)
    while end != -1:
        preceded_by_space = text[end - 1] in " \t"
        followed_by_word = end + 1 < len(text) and _is_ascii_word(text[end + 1])
        if not preceded_by_space and not followed_by_word:
            return end
        end = text.find("$", end + 1)
    return None


def _is_ascii_word(char: str) -> bool:
    return char.isascii() and (char.isalnum() or char == "_")


def _delimited(text: str, index: int, opener: str, closer: str) -> tuple[str, int] | None:
    if not text.startswith(opener, index):
        return None
    end = text.find(closer, index + len(opener))
    if end == -1:
        return None
    return text[index + len(opener) : end], end + len(closer)


def _try_emphasis(text: str, index: int, *, bold: bool, italic: bool) -> _Token | None:
    for marker, make_bold, make_italic in (
        ("***", True, True),
        ("___", True, True),
        ("**", True, False),
        ("__", True, False),
    ):
        found = _delimited(text, index, marker, marker)
        if found is None or not found[0]:
            continue
        inner = parse_inline(found[0], bold=bold or make_bold, italic=italic or make_italic)
        return _Token(tuple(inner), found[1])
    if text.startswith("*", index) and not text.startswith("**", index):
        return _wrapped_emphasis(text, index, "*", bold=bold, italic=True)
    if text.startswith("_", index) and not text.startswith("__", index) and _underscore_opens(text, index):
        return _wrapped_emphasis(text, index, "_", bold=bold, italic=True)
    return None


def _wrapped_emphasis(
    text: str,
    index: int,
    marker: str,
    *,
    bold: bool,
    italic: bool,
) -> _Token | None:
    found = _delimited(text, index, marker, marker)
    if found is None or not found[0].strip():
        return None
    if marker == "_" and not _underscore_closes(text, found[1] - 1):
        return None
    inner = parse_inline(found[0], bold=bold, italic=italic)
    return _Token(tuple(inner), found[1])


def _underscore_opens(text: str, index: int) -> bool:
    if index > 0 and _is_ascii_word(text[index - 1]):
        return False
    return index + 1 < len(text) and not text[index + 1].isspace()


def _underscore_closes(text: str, close_index: int) -> bool:
    if close_index <= 0 or text[close_index - 1].isspace():
        return False
    return close_index + 1 >= len(text) or not _is_ascii_word(text[close_index + 1])


def _try_code(text: str, index: int, *, bold: bool, italic: bool) -> _Token | None:
    found = _delimited(text, index, "`", "`")
    if found is None:
        return None
    return _Token((_span(found[0], bold=bold, italic=italic, code=True),), found[1])


def _try_strike(text: str, index: int, *, bold: bool, italic: bool) -> _Token | None:
    found = _delimited(text, index, "~~", "~~")
    if found is None or not found[0]:
        return None
    inner = parse_inline(found[0], bold=bold, italic=italic)
    struck = tuple(
        InlineSpan(
            span.text,
            bold=span.bold,
            italic=span.italic,
            code=span.code,
            math=span.math,
            strike=True,
            link=span.link,
        )
        for span in inner
    )
    return _Token(struck, found[1])


def _try_link(text: str, index: int, *, bold: bool, italic: bool) -> _Token | None:
    if text[index] != "[":
        return None
    match = _LINK_RE.match(text, index)
    if match is None:
        return None
    label = parse_inline(match.group(1), bold=bold, italic=italic)
    href = match.group(2).strip()
    linked = tuple(
        InlineSpan(
            span.text,
            bold=span.bold,
            italic=span.italic,
            code=span.code,
            math=span.math,
            strike=span.strike,
            link=href,
        )
        for span in label
    )
    return _Token(linked, match.end())


def _try_backslash(text: str, index: int, *, bold: bool, italic: bool) -> _Token | None:
    if text[index] != "\\" or index + 1 >= len(text):
        return None
    nxt = text[index + 1]
    if nxt in "\\`*_{}[]()#+-.!|":
        return _Token((_span(nxt, bold=bold, italic=italic),), index + 2)
    if not nxt.isalpha():
        return None
    reader = _LatexReader(text[index:])
    atom = reader.read_atom()
    if reader.index <= 1 or not atom.strip():
        return None
    return _Token((_span(atom, bold=bold, italic=italic, math=True),), index + reader.index)


def _to_script(text: str, *, superscript: bool) -> str:
    mapping = _SUPER_MAP if superscript else _SUB_MAP
    if text and all(char in mapping for char in text):
        return "".join(mapping[char] for char in text)
    marker = "^" if superscript else "_"
    if len(text) == 1:
        return f"{marker}{text}"
    return f"{marker}({text})"


def _is_simple_term(text: str) -> bool:
    body = text.strip()
    if not body or len(body) > 8:
        return False
    return all(char.isalnum() or char in "+-." for char in body)


def _format_frac(numerator: str, denominator: str) -> str:
    num = numerator.strip()
    den = denominator.strip()
    if _is_simple_term(num) and _is_simple_term(den):
        return f"{num}/{den}"
    return f"({num})/({den})"


def _format_sqrt(body: str, degree: str) -> str:
    inner = body.strip()
    prefix = _to_script(degree, superscript=True) if degree else ""
    if _is_simple_term(inner):
        return f"{prefix}√{inner}"
    return f"{prefix}√({inner})"
