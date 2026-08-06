"""
Prompt injection detection — heuristic, not an ML classifier.

Structural defenses matter more than this file: the user's question is
always placed in a "user"-role message, never concatenated into the system
prompt, and the system prompt itself instructs the model to answer only
from numbered context and cite only real markers. This module is a second,
much simpler layer on top of that — catching the most common blunt
injection phrasings so they can be logged and (for the clearest cases)
refused outright, rather than silently passed through.

This will have false negatives against a determined adversary rephrasing
around the patterns below, and is not a substitute for the structural
defenses above. Treat it as a tripwire, not a wall.
"""
import re
from dataclasses import dataclass

_INJECTION_PATTERNS = [
    r"ignore (all|any|the) (previous|prior|above) instructions",
    r"disregard (all|any|the) (previous|prior|above|system) (instructions|prompt)",
    r"you are now (in )?(developer|debug|jailbreak|dan) mode",
    r"reveal (your|the) (system prompt|instructions|api key)",
    r"forget (everything|all) (you|that) (were|was) told",
    r"act as if you have no (restrictions|rules|guidelines)",
    r"print (your|the) (system prompt|configuration|instructions)",
    r"do anything now",
]

_COMPILED = [re.compile(p, re.IGNORECASE) for p in _INJECTION_PATTERNS]


@dataclass
class InjectionCheckResult:
    flagged: bool
    matched_pattern_count: int


INJECTION_REFUSAL = (
    "I can't process that request as written — it looks like it's trying to override my "
    "instructions rather than ask a genuine question. Please rephrase what you'd like to know."
)


def check_for_injection(text: str) -> InjectionCheckResult:
    matches = sum(1 for pattern in _COMPILED if pattern.search(text))
    return InjectionCheckResult(flagged=matches > 0, matched_pattern_count=matches)
