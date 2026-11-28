"""Safety rules for fully automatic publishing.

SKIP      -> never publish automatically (too risky without a human check).
SENSITIVE -> publish, but no affiliate products on the post.
TRAGEDY   -> deaths, disasters, violence: no stock photo, and limited per day
             (see automation/run.py: only big stories, max one a day).
"""
import re

SKIP_PATTERNS = [
    r"\bsuicid", r"\bself[- ]harm", r"\brape[ds]?\b", r"\bsexual(ly)? assault", r"\bmolest",
    r"\bchild abuse", r"\bminor\b.*\b(abuse|assault|murder)", r"\bcommunal\b", r"\blynch",
    r"\bhate speech", r"\briot", r"\bmob\b.*\b(kill|attack)", r"\bbeheaded", r"\bmassacre",
    r"\bterror(ist)? attack", r"\bsextortion", r"\bacid attack",
]

# Violence / disaster words, written so business phrases do not match
# ("trade war", "price war", "market crash", "attacks the policy", "stock collapse").
_VIOLENCE = [
    r"\bdead\b", r"\bdies?\b", r"\bdied\b", r"\bdeath", r"\bkill(ed|s|ing)?\b", r"\bmurder", r"\bshot dead",
    r"\bgunfire", r"\bshooting\b", r"\bstabb",
    r"\baccident", r"\b(plane|jet|helicopter|chopper) crash", r"\bcrash(ed|es)? (into|kills?|killing)",
    r"\b(building|bridge|roof|wall|stadium|mine|tunnel|structure) collapse",
    r"\bblast", r"\bexplosion", r"\bblaze", r"\b(massive|major|huge|fierce) fire", r"\bfire (broke|breaks|kills|killed|guts|at)\b", r"\bflood", r"\bearthquake", r"\bcyclone", r"\blandslide", r"\btsunami",
    r"\bdisaster", r"(?<!trade )(?<!price )(?<!tariff )(?<!talent )(?<!bidding )(?<!console )(?<!streaming )\bwar\b",
    r"\b(drone|missile|air|terror|militant|armed|rocket|bomb|gun|knife|grenade) ?(attack|strike)s?\b",
    r"\bairstrikes?\b", r"\bshelling", r"\bbomb(ing|ed|s)?\b", r"\bhostage", r"\bkidnap", r"\bvictim",
    r"\binjur", r"\bfuneral", r"\bmourn", r"\btragedy", r"\bpasse[sd] away",
]

# Crime and police matters stay product-free. Courts and lawsuits alone do not:
# a company lawsuit (OpenAI vs Apple) is business news and can carry products.
_CRIME = [
    r"\barrest", r"\bpolice\b", r"\bjail", r"\bbail\b", r"\bcustody", r"\baccused\b", r"\bchargesheet",
    r"\bconvicted", r"\bsentenced", r"\bcrime", r"\bscam", r"\bfraud",
]

SENSITIVE_PATTERNS = _VIOLENCE + _CRIME

TRAGEDY_PATTERNS = _VIOLENCE + [r"\bmaut\b", r"\bhaadsa", r"\bhadsa", r"\bnidhan\b"]


def _match(patterns, text):
    t = text.lower()
    return any(re.search(p, t) for p in patterns)


def classify(text):
    """Return 'skip', 'sensitive' or 'ok' for a story's combined text."""
    if _match(SKIP_PATTERNS, text):
        return "skip"
    if _match(SENSITIVE_PATTERNS, text) or re.search(r"\bFIR\b", text):  # FIR case-sensitive: Hinglish "fir" = "then"
        return "sensitive"
    return "ok"


def is_tragedy(text):
    """Deaths, disasters, violence."""
    return _match(TRAGEDY_PATTERNS, text)
