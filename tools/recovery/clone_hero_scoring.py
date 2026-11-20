"""Chart-specific family-presence scoring, distinct from MDB label policy."""
from clone_hero_reference import family_reference
from evaluate_mdb import drum_family
from score_timing import evaluate_timing

COMPONENT = {"KD": "kick", "SD": "snare", "HH": "hihat", "TT": "tom", "CY": "cymbal", "OT": "other"}


def chart_family(component):
    # MDB deliberately puts SST in Other. A CH red snare pad cannot distinguish
    # rim/side-stick from a snare head, so this benchmark uses broad snare.
    return "SD" if component == "cross_stick" else drum_family(component)


def prediction_presence(chart, merge_cymbals=False):
    seen = set()
    events = []
    for event in chart["hitObjects"]:
        family = chart_family(event["component"])
        if merge_cymbals and family == "HH":
            family = "CY"
        key = event["time"], family
        if key not in seen:
            events.append({"time": event["time"], "component": COMPONENT[family]})
            seen.add(key)
    return {"hitObjects": sorted(events, key=lambda e: (e["time"], e["component"]))}


def score_chart_agreement(chart, events):
    return {str(ms): {view: evaluate_timing(prediction_presence(chart, merged), family_reference(events, merged), ms/1000)
                     for view, merged in [("five_family_proxy", False), ("cymbals_merged", True)]} for ms in [25,50]}
