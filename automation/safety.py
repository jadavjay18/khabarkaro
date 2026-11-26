"""Safety rules for fully automatic publishing.

SKIP  -> never publish automatically (too risky without a human check).
SENSITIVE -> publish, but no affiliate products on the post.
"""
import re

SKIP_PATTERNS = [
    r"\bsuicid", r"\bself[- ]harm", r"\brape[ds]?\b", r"\bsexual(ly)? assault", r"\bmolest",
    r"\bchild abuse", r"\bminor\b.*\b(abuse|assault|murder)", r"\bcommunal\b", r"\blynch",
    r"\bhate speech", r"\briot", r"\bmob\b.*\b(kill|attack)", r"\bbeheaded", r"\bmassacre",
    r"\bterror(ist)? attack", r"\bsextortion", r"\bacid attack",
]

SENSITIVE_PATTERNS = [
    r"\bdead\b", r"\bdies?\b", r"\bdied\b", r"\bdeath", r"\bkill(ed|s|ing)?\b", r"\bmurder", r"\bshot\b",
    r"\bstabb", r"\baccident", r"\bcrash", r"\bcollapse", r"\bfire\b", r"\bblast", r"\bexplosion",
    r"\bflood", r"\bearthquake", r"\bcyclone", r"\blandslide", r"\btsunami", r"\bdisaster", r"\bwar\b",
    r"\battack", r"\bmissile", r"\bbomb", r"\bhostage", r"\bkidnap", r"\barrest", r"\bvictim",
    r"\binjur", r"\bfuneral", r"\bmourn", r"\btragedy", r"\bhospitali[sz]ed", r"\bpasses away",
    r"\bpassed away", r"\bcourt\b", r"\bverdict", r"\bconvicted", r"\bfir\b", r"\bscam", r"\bfraud",
]


def _match(patterns, text):
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def classify(text):
    """Return 'skip', 'sensitive' or 'ok' for a story's combined text."""
    if _match(SKIP_PATTERNS, text):
        return "skip"
    if _match(SENSITIVE_PATTERNS, text):
        return "sensitive"
    return "ok"


TRAGEDY_PATTERNS = [
    r"\bdead\b", r"\bdies?\b", r"\bdied\b", r"\bdeath", r"\bkill(ed|s|ing)?\b", r"\bmurder", r"\bshot\b",
    r"\baccident", r"\bcrash", r"\bcollapse", r"\bblast", r"\bexplosion", r"\bflood", r"\bearthquake",
    r"\bcyclone", r"\blandslide", r"\btsunami", r"\bdisaster", r"\bwar\b", r"\battack", r"\bbomb",
    r"\bhostage", r"\bkidnap", r"\bvictim", r"\binjur", r"\bfuneral", r"\bmourn", r"\btragedy",
    r"\bpasse[sd] away", r"\bmaut\b", r"\bhaadsa", r"\bhadsa",
]


def is_tragedy(text):
    """Deaths, disasters, violence: no stock photo, only the headline card."""
    return _match(TRAGEDY_PATTERNS, text)
