"""
Safety routing — the responsible-product layer.

A wellbeing product that just scores mood and gamifies streaks is incomplete and
arguably unsafe. If an entry expresses acute distress, the right behaviour is to
*step out of analytics mode*: suppress streak/gamification nudges and surface a
calm, supportive message pointing toward real human help.

This is intentionally simple and conservative (keyword-based). It is NOT a clinical
tool and never attempts to diagnose. It exists so the product fails safe.
"""

# Phrases indicating acute distress / possible crisis. Conservative by design.
_CONCERN_PHRASES = [
    "want to die", "end it all", "no reason to live", "can't go on", "cant go on",
    "better off without me", "hurt myself", "harm myself", "give up on life",
    "hopeless", "worthless and", "nothing matters anymore",
]

SUPPORT_MESSAGE = (
    "It sounds like you're carrying something really heavy right now, and you don't "
    "have to face it alone. Talking to someone you trust — a friend, family member, "
    "or a mental-health professional — can help. If you're in immediate distress, "
    "please reach out to a local crisis line or emergency services in your country. "
    "You deserve support from a real person who can be there with you."
)


def check_safety(text: str) -> bool:
    """Return True if the entry shows signs of acute distress."""
    low = text.lower()
    return any(phrase in low for phrase in _CONCERN_PHRASES)
