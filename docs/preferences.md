# Preference Learning and Personalization

famulix learns user preferences from explicit ratings and implicit signals,
then applies them to personalize briefings and other outputs.

## PreferenceProfile

The `PreferenceProfile` stores learned preferences with confidence:

```python
from famulix.preferences import PreferenceProfile

profile = PreferenceProfile()
profile.add_feedback(
    pref_key="tone",
    value="concise",
    signal="up",
    timestamp_s=1000000,
    confidence=0.9,
)
```

### Feedback Signals

Signals indicate user preference strength:
- `up`: Explicit positive (thumbs up, 5-star)
- `down`: Explicit negative (thumbs down, 1-star)
- `accept`: Implicit positive (accepted suggestion)
- `decline`: Implicit negative (declined suggestion)
- `edit`: Implicit positive with modification
- `skip`: Weak/neutral (ignored)

### Confidence

Each feedback has a confidence in [0, 1]:
- 1.0: High confidence (explicit rating)
- 0.5: Medium confidence (implicit signal)
- 0.1: Low confidence (skip/ignore)

## Current Preferences

`current_preferences()` computes the dominant preference per key:

```python
prefs = profile.current_preferences(
    now_s=1000000,
    min_confidence=0.2,
)
# {"tone": ("concise", 0.85), "format": ("markdown", 0.72)}

for key, (value, conf) in prefs.items():
    print(f"{key}: {value} (confidence={conf:.2f})")
```

### Temporal Decay

Preferences decay over time with a configurable half-life:

```python
profile = PreferenceProfile(decay_half_life_s=86400 * 30)  # 30 days
```

Older feedback has less weight. The decay is exponential:

```
weight = confidence * exp(-age * log(2) / half_life)
```

### Dominant Value

For each key, the value with the highest total weight wins:

```
weights["tone"]["concise"] = 0.9 + 0.8 + 0.7 = 2.4
weights["tone"]["verbose"] = -0.5
→ dominant: "concise"
```

Negative weights (from "down"/"decline") subtract from the total.

## Personalization

`apply_preferences()` personalizes outputs based on the profile:

```python
from famulix.personalization import apply_preferences

personalized = apply_preferences(
    briefing,
    profile=profile,
    now_s=1000000,
)
```

### Personalization Dimensions

Preferences affect:
- **Tone**: concise vs verbose
- **Format**: markdown vs plain text vs HTML
- **Ordering**: priority vs chronological vs alphabetical
- **Length**: short vs medium vs long

### Explainability

Each personalization choice includes an explanation:

```python
for choice in personalized.choices:
    print(f"{choice.dimension}: {choice.value}")
    print(f"  Why: {choice.explanation}")
# "tone: concise"
# "  Why: User rated concise 3x higher than verbose (conf=0.85)"
```

## Cold Start

When no feedback is available, defaults are used:

```python
defaults = {
    "tone": "neutral",
    "format": "markdown",
    "ordering": "priority",
    "length": "medium",
}
```

The `min_confidence` threshold filters out low-confidence preferences, falling
back to defaults.

## Calibration

`calibration_score()` measures how well the profile predicts user feedback:

```python
from famulix.evaluation import eval_preference_calibration

brier = eval_preference_calibration(
    profile=profile,
    preference_signals=test_signals,
    now_s=1000000,
)
# Brier score: 0.0 = perfect, 1.0 = worst
```

Lower Brier score = better calibration.

## Contradiction Handling

When feedback contradicts existing preferences:

```python
# User previously preferred "concise"
profile.add_feedback("tone", "concise", signal="up", timestamp_s=1000000)

# Later, user prefers "verbose"
profile.add_feedback("tone", "verbose", signal="up", timestamp_s=2000000)

# The newer feedback has more weight (less decay)
prefs = profile.current_preferences(now_s=2000000)
# "tone" may shift to "verbose" if the new signal is strong enough
```

The system doesn't discard old preferences — it weights them by recency and
confidence.

## Serialization

Profiles can be serialized for persistence:

```python
import json

# Serialize
data = {
    "version": profile.version,
    "entries": [entry.to_dict() for entry in profile.entries],
    "decay_half_life_s": profile.decay_half_life_s,
}
json_str = json.dumps(data)

# Deserialize
loaded_data = json.loads(json_str)
loaded_profile = PreferenceProfile(
    version=loaded_data["version"],
    entries=[PreferenceEntry.from_dict(e) for e in loaded_data["entries"]],
    decay_half_life_s=loaded_data["decay_half_life_s"],
)
```

## CLI Usage

```bash
# View current preferences
famulix prefs --persona alex --seed 42

# View preference history
famulix prefs history --persona alex --seed 42
```

## A/B Testing

Compare personalized vs default outputs:

```python
from famulix.personalization import counterfactual_comparison

comparison = counterfactual_comparison(
    briefing,
    profile=profile,
    now_s=1000000,
)

print(f"Changed dimensions: {comparison.changed_count}")
print(f"Unchanged: {comparison.unchanged_count}")
```

This enables offline evaluation of personalization impact.
