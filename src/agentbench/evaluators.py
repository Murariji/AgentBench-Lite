"""Evaluators: judge a finished run against its task. The "third umpire".

They only READ a RunResult: no LLM, no API request, no cost. So any old run can be
re-graded for free whenever the rules improve.

    evaluate(task, result) -> EvaluationResult
        checks:  status            did the run finish?
                 answer:<type>     is the final answer right? (exact / contains / number)
                 required_tools    were the required tools used successfully?
        passed = every check passed (no score, no averaging)

Limitation: these checks compare text and numbers, not MEANING. "New Delhi" vs
"Delhi", or "Not Delhi" (contains-match still passes!) need human or LLM judgement,
which is out of scope (it would cost API quota). Benchmark tasks are therefore
written to have crisp answers: a number, a name, a category.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from agentbench.models import Check, EvaluationResult, RunResult, Task

# ---------- text normalisation ------------------------------------------------

_QUOTES = "\"'`“”‘’"


def normalize_text(text: str) -> str:
    """Lower-case, single spaces, no surrounding quotes, no final '.' or '!'."""
    text = re.sub(r"\s+", " ", text)
    previous = None
    while previous != text:  # repeat: '"Paris."' -> 'Paris.' -> 'Paris'
        previous = text
        text = text.strip().strip(_QUOTES).rstrip(".!")
    return text.casefold()


# ---------- number extraction -------------------------------------------------

# Removed deliberately (fixed list) before looking for numbers.
_CURRENCY = re.compile(r"[₹$€£]|\b(?:rs\.?|inr|usd|rupees?|dollars?)(?![a-z])", re.IGNORECASE)
# A candidate number: optional sign, digits with optional commas, optional decimals, optional %.
# (?<![\w.]) stops matching digits glued to words, e.g. the "1" in "Q1".
_NUMBER = re.compile(r"(?<![\w.])([-+]?)(\d[\d,]*)(\.\d+)?(%?)")
_PLAIN = re.compile(r"\d+")
_WESTERN = re.compile(r"\d{1,3}(?:,\d{3})+")        # 1,240  1,240,000
_INDIAN = re.compile(r"\d{1,2}(?:,\d{2})*,\d{3}")   # 1,240  12,40,000
# Words that introduce the final answer; we use the number right after the LAST one.
_MARKER = re.compile(r"=|\bis\b|\banswer\s*:|\btotal\s*:", re.IGNORECASE)


@dataclass(frozen=True)
class _Candidate:
    text: str
    value: Decimal | None  # None = the format is unclear (e.g. "1,5")
    start: int


@dataclass(frozen=True)
class NumberParse:
    """Result of reading a number out of an answer. value is None when we refuse to guess."""

    value: Decimal | None
    reason: str


def _fmt(value: Decimal) -> str:
    """Decimal -> short text without exponent: Decimal('1.2E+3') -> '1200'."""
    text = format(value.normalize(), "f")
    return text


def _candidates(text: str) -> list[_Candidate]:
    found = []
    for match in _NUMBER.finditer(text):
        sign, integer, fraction, percent = match.groups()
        integer = integer.rstrip(",")  # "1,240, and" -> "1,240"
        token = f"{sign}{integer}{fraction or ''}{percent}"
        well_formed = (
            _PLAIN.fullmatch(integer) or _WESTERN.fullmatch(integer) or _INDIAN.fullmatch(integer)
        )
        value = None
        if well_formed:
            try:
                value = Decimal(sign + integer.replace(",", "") + (fraction or ""))
            except InvalidOperation:
                value = None
        found.append(_Candidate(token, value, match.start()))
    return found


def extract_number(answer: str) -> NumberParse:
    """Find THE number in an answer, or refuse with a reason. Never just "the first number".

    Rules, in order:
      1. exactly one number in the answer      -> use it
      2. several numbers + a final-answer marker (=, is, answer:, total:)
                                               -> the first number after the LAST marker
      3. several numbers, all the same value   -> use it
      4. otherwise                             -> ambiguous: refuse (value None)
    Commas must be real thousands separators (1,240 or 12,40,000); "1,5" is refused.
    "12.5%" reads as 12.5. Decimal (not float) keeps values exact: "126" == "126.0".
    """
    cleaned = _CURRENCY.sub(" ", answer)
    candidates = _candidates(cleaned)
    if not candidates:
        return NumberParse(None, "no number found in the answer")
    unclear = [c.text for c in candidates if c.value is None]
    if unclear:
        return NumberParse(None, f"unclear number format: {', '.join(unclear)}")

    if len(candidates) == 1:
        return NumberParse(candidates[0].value, f"found {_fmt(candidates[0].value)} (the only number)")

    markers = list(_MARKER.finditer(cleaned))
    if markers:
        last = markers[-1]
        after = [c for c in candidates if c.start >= last.end()]
        if after:
            return NumberParse(
                after[0].value,
                f"found {_fmt(after[0].value)} after the final-answer marker {last.group(0)!r}",
            )

    values = {c.value for c in candidates}
    if len(values) == 1:
        value = values.pop()
        return NumberParse(value, f"found {_fmt(value)} (every number in the answer is the same)")

    listed = ", ".join(c.text for c in candidates)
    return NumberParse(None, f"ambiguous: found {listed} and no clear final answer")


# ---------- the individual checks ---------------------------------------------

def check_status(result: RunResult) -> Check:
    if result.status == "completed":
        return Check(name="status", passed=True, reason="run completed")
    if result.status == "max_steps":
        reason = f"run hit the step limit after {len(result.trace.steps)} steps without a final answer"
    else:
        reason = f"run ended with an error ({result.error_kind}): {result.error}"
    return Check(name="status", passed=False, reason=reason)


def check_exact(expected: str, answer: str) -> Check:
    ok = normalize_text(answer) == normalize_text(expected)
    reason = (f"{answer!r} matches {expected!r}" if ok
              else f"{answer!r} does not exactly match {expected!r}")
    return Check(name="answer:exact", passed=ok, reason=reason)


def check_contains(expected: str, answer: str) -> Check:
    # Whole words only: "Delhi" is NOT found in "Delhiwala".
    pattern = r"(?<!\w)" + re.escape(normalize_text(expected)) + r"(?!\w)"
    ok = re.search(pattern, normalize_text(answer)) is not None
    reason = (f"{answer!r} contains {expected!r}" if ok
              else f"{answer!r} does not contain {expected!r} as whole words")
    return Check(name="answer:contains", passed=ok, reason=reason)


def check_number(expected: str, answer: str, abs_tol: float = 0.0, rel_tol: float = 0.0) -> Check:
    name = "answer:number"
    target = extract_number(expected)
    if target.value is None:
        return Check(name=name, passed=False,
                     reason=f"task's expected_answer {expected!r} is not one clear number")
    got = extract_number(answer)
    if got.value is None:
        return Check(name=name, passed=False, reason=f"could not read the answer: {got.reason}")

    difference = abs(got.value - target.value)
    allowed = max(Decimal(str(abs_tol)), Decimal(str(rel_tol)) * abs(target.value))
    if difference <= allowed:
        return Check(name=name, passed=True,
                     reason=f"{got.reason}; matches expected {_fmt(target.value)}")
    return Check(name=name, passed=False,
                 reason=f"{got.reason}; expected {_fmt(target.value)} "
                        f"(difference {_fmt(difference)} > allowed {_fmt(allowed)})")


def check_answer(task: Task, result: RunResult) -> Check:
    name = f"answer:{task.answer_type}"
    if task.expected_answer is None:
        return Check(name=name, passed=False,
                     reason="task has no expected_answer, so it cannot be graded deterministically")
    if result.final_answer is None:
        return Check(name=name, passed=False, reason="no final answer to check")
    if task.answer_type == "number":
        return check_number(task.expected_answer, result.final_answer,
                            task.abs_tolerance, task.rel_tolerance)
    if task.answer_type == "contains":
        return check_contains(task.expected_answer, result.final_answer)
    return check_exact(task.expected_answer, result.final_answer)


def check_required_tools(required: list[str], result: RunResult) -> Check:
    """Each required tool must have at least one SUCCESSFUL call (an error doesn't count)."""
    calls = [s.tool_call for s in result.trace.steps if s.tool_call is not None]
    problems, used = [], []
    for tool in required:
        attempts = [c for c in calls if c.tool_name == tool]
        successes = [c for c in attempts if c.error is None]
        if successes:
            used.append(f"{tool} ({len(successes)} successful call(s))")
        elif attempts:
            problems.append(f"{tool} was called {len(attempts)} time(s) but never succeeded")
        else:
            problems.append(f"{tool} was never called")
    if problems:
        return Check(name="required_tools", passed=False, reason="; ".join(problems))
    return Check(name="required_tools", passed=True, reason="used: " + ", ".join(used))


# ---------- the evaluator -----------------------------------------------------

def evaluate(task: Task, result: RunResult) -> EvaluationResult:
    """Grade one run. Every check is mandatory; the verdict is derived from them."""
    if task.id != result.task_id:
        raise ValueError(f"result is for task {result.task_id!r}, not {task.id!r}")
    checks = [check_status(result), check_answer(task, result)]
    if task.required_tools:
        checks.append(check_required_tools(task.required_tools, result))
    return EvaluationResult(
        run_id=result.run_id,
        task_id=task.id,
        passed=all(c.passed for c in checks),
        checks=checks,
    )
