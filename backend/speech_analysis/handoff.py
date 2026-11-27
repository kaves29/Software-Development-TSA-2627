"""Prepare a minimal, non-diagnostic input for a future roadmap service."""

import math
from .video import NAMES as VIDEO_FEATURES

PROFILE_FIELDS = ('goal', 'goals', 'situations', 'challenges', 'priority', 'constraints', 'age_band',
                  'motivation', 'follow_up_answers')
FEATURES = ('speaking_rate', 'rate_changes', 'pauses', 'fillers', 'repetitions', 'revisions',
            'pitch_variation', 'energy_variation', 'opening_context', 'main_point', 'supporting_detail',
            'transitions', 'closing', 'prompt_relevance', 'prompt_completion')


def _measurement(value):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (float, int)) and math.isfinite(value):
        return value
    if isinstance(value, list):
        if all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in value):
            return value
        if all(isinstance(x, dict) for x in value):
            return {'event_count': len(value)}
    return None


def roadmap_evidence(profile, session):
    """Preserve sample measurements, not names, age, transcripts, or audio."""
    observations = session.get('observations', {})
    features = {}
    for name in (*FEATURES, *VIDEO_FEATURES):
        if name not in observations:
            continue
        item = observations[name]
        rows = [{'sample_id': row.get('sample_id'), 'status': row.get('status', 'unavailable'),
                 'value': _measurement(row.get('value'))} for row in item.get('samples', [])]
        features[name] = {'coverage': item.get('coverage', 'insufficient_evidence'), 'samples': rows}
    return {'schema_version': 1, 'profile': {name: profile[name] for name in PROFILE_FIELDS if name in profile},
            'audio_evidence': features,
            'interpretation': 'Observations are experimental, not diagnoses or proof of weakness; prioritize user goals.'}
