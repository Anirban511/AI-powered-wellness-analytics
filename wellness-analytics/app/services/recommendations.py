"""
Personalised recommendations.

Input signals -> ranked suggestions, each with a *rationale* (explainability is a
product feature here, not an afterthought: users trust advice they understand).

Priority order:
  1) Safety first   — if distress is flagged, surface support, suppress the rest.
  2) Trend          — a rising stress trend gets a "get ahead of it" nudge.
  3) Themes         — sleep / work / social / money / health specific tips.
  4) Reinforcement  — when things are going well, reinforce what's working.

The content is general, non-clinical wellbeing guidance — explicitly not medical
advice. The library is small and curated on purpose; a real deployment would A/B
test phrasing and expand it.
"""
from app.services.safety import SUPPORT_MESSAGE

# category -> (title, body)
_LIBRARY = {
    "sleep": ("Protect your sleep tonight",
              "Aim for a consistent wind-down: screens off 30 minutes before bed and a "
              "dark, cool room. Even one good night measurably lowers next-day stress."),
    "work": ("Break the workload into one next action",
             "When a deadline feels huge, the load is usually ambiguity. Write down the "
             "single next 20-minute task and start only that. Momentum beats overwhelm."),
    "social": ("Reach out to one person",
               "Social strain weighs heavily. Consider a short, honest message to someone "
               "you trust — connection is one of the most reliable stress buffers."),
    "money": ("Turn money worry into one concrete step",
              "Financial stress thrives on vagueness. Pick one small, doable action this "
              "week (a list, a call, a tiny budget tweak) to convert worry into control."),
    "health": ("Try a 4-7-8 breathing reset",
               "Breathe in for 4, hold for 7, out for 8, a few rounds. It nudges your "
               "nervous system toward calm in about two minutes."),
    "rising": ("Get ahead of a rising week",
               "Your stress has been climbing. Block 15 minutes today for something "
               "restorative before it compounds — a walk, a stretch, or simply nothing."),
    "volatile": ("Add one steady anchor to your day",
                 "Your days have swung a lot lately. A single fixed ritual (morning coffee "
                 "without your phone, an evening walk) creates a stabilising rhythm."),
    "reinforce": ("Keep doing what's working",
                  "You've been in a good stretch. Note what contributed — sleep, people, "
                  "exercise? Naming it makes it easier to repeat on harder weeks."),
    "general": ("A small reset goes a long way",
                "Take two minutes for a few slow breaths and a glass of water. Tiny resets, "
                "done often, add up more than rare big ones."),
}


def _make(category: str, rationale: str) -> dict:
    title, body = _LIBRARY[category]
    return {"category": category, "title": title, "body": body, "rationale": rationale}


def recommend(*, safety_flag: bool, themes: list[str], trend: str,
              volatility: float, stress_level: float, top_k: int = 3) -> list[dict]:
    """Return up to top_k recommendations, safety-first and explainable."""
    if safety_flag:
        return [{
            "category": "support",
            "title": "You're not alone — reach out",
            "body": SUPPORT_MESSAGE,
            "rationale": "Your entry signalled acute distress, so support takes priority "
                         "over analytics. (Aura is not a medical service.)",
        }]

    recs: list[dict] = []
    if trend == "rising" or stress_level >= 65:
        recs.append(_make("rising", f"Stress is {('rising' if trend=='rising' else 'elevated')} "
                                    f"(~{round(stress_level)}/100), so acting early helps."))
    for theme in themes:
        if theme in _LIBRARY and theme != "positive":
            recs.append(_make(theme, f"Your recent entries kept surfacing the '{theme}' theme."))
    if volatility >= 18:
        recs.append(_make("volatile", f"Your daily stress has been swinging a lot "
                                      f"(volatility {round(volatility)})."))
    if not recs:
        if stress_level <= 35:
            recs.append(_make("reinforce", "You've been in a low-stress, positive stretch."))
        else:
            recs.append(_make("general", "A light, general reset based on your recent mood."))

    # de-duplicate by category, preserve priority order
    seen, unique = set(), []
    for r in recs:
        if r["category"] not in seen:
            seen.add(r["category"])
            unique.append(r)
    return unique[:top_k]
