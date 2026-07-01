"""
Keyword / theme extraction (NLP).

Two jobs:
  1) extract_keywords  -> salient terms from a single entry (for display + reco triggers)
  2) classify_themes   -> map an entry to wellbeing themes (sleep, work, social, money...)

We keep this lightweight and dependency-free (no spaCy download) so the container
stays small. Themes drive *personalised* recommendations downstream.
"""
import re
from collections import Counter

STOPWORDS = set("""
a an and the is are was were be been being to of in on at for with from by it its this that these those
i me my we our you your he she they them their as so but or if then than too very just really feel feeling
felt have has had do does did not no yes can will would could should about into out up down over again more
most some any all am pm today days todays im ive dont cant got get getting going go also like really lot bit
couldnt wouldnt shouldnt wasnt werent isnt arent off switch keep kept made make making thing things time
day week year much many even still back around think though every always never being been
""".split())

THEME_LEXICON = {
    "sleep": {"sleep", "tired", "exhausted", "insomnia", "rest", "nap", "awake", "fatigue", "fatigued"},
    "work": {"work", "deadline", "deadlines", "project", "boss", "meeting", "exam", "exams",
             "study", "assignment", "workload", "overtime", "office", "client", "interview"},
    "social": {"friend", "friends", "family", "argument", "fight", "lonely", "alone",
               "conflict", "partner", "relationship", "breakup"},
    "money": {"money", "rent", "bills", "debt", "salary", "broke", "expensive", "afford"},
    "health": {"sick", "pain", "headache", "ill", "doctor", "anxious", "anxiety", "panic"},
    "positive": {"grateful", "happy", "excited", "proud", "relaxed", "calm", "accomplished",
                 "win", "great", "love", "joy", "peaceful", "hopeful"},
}

_word_re = re.compile(r"[a-zA-Z']+")


def _tokens(text: str) -> list[str]:
    out = []
    for w in _word_re.findall(text):
        w = w.replace("'", "").lower()   # couldn't -> couldnt
        if len(w) > 2:
            out.append(w)
    return out


def extract_keywords(text: str, top_k: int = 5) -> list[str]:
    """Most frequent non-stopword tokens — cheap, transparent, good enough for triggers."""
    words = [w for w in _tokens(text) if w not in STOPWORDS]
    if not words:
        return []
    return [w for w, _ in Counter(words).most_common(top_k)]


def classify_themes(text: str) -> list[str]:
    """Return wellbeing themes present in the entry, ranked by hit count."""
    toks = set(_tokens(text))
    scored = {
        theme: len(toks & vocab)
        for theme, vocab in THEME_LEXICON.items()
    }
    return [t for t, n in sorted(scored.items(), key=lambda x: -x[1]) if n > 0]
