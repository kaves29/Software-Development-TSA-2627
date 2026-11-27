"""Measure a single English onboarding response."""

import math
import re
from collections import Counter

FEATURES = (
    'speaking_rate', 'rate_changes', 'pauses', 'fillers', 'repetitions',
    'revisions', 'prompt_coverage', 'organization', 'pitch_variation', 'energy_variation',
)
TOKEN = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
REVISION_MARKERS = {('i', 'mean'), ('or', 'rather'), ('let', 'me', 'rephrase')}
STRUCTURE_MARKERS = {
    'point_marker': ('my point is', 'the main idea is', 'i think'),
    'example_marker': ('for example', 'for instance', 'such as'),
    'closing_marker': ('in conclusion', 'to sum up', 'overall'),
}


def phrases(tokens, phrase):
    return [i for i in range(len(tokens) - len(phrase) + 1)
            if tokens[i:i + len(phrase)] == phrase]


def analyze_features(duration, speech, words, targets, pitch_span=None, energy_span=None):
    result = {name: {'status': 'insufficient_evidence', 'value': None}
              for name in FEATURES}

    def set_value(name, value, status='estimated'):
        result[name] = {'status': status, 'value': value}

    if not speech or sum(end - start for start, end in speech) < 1:
        return result
    set_value('pauses', [
        {'start_s': round(end, 3), 'end_s': round(start, 3),
         'duration_s': round(start - end, 3)}
        for (_, end), (start, _) in zip(speech, speech[1:]) if start > end
    ])
    if pitch_span is not None and math.isfinite(pitch_span):
        set_value('pitch_variation', pitch_span, 'experimental')
    if energy_span is not None and math.isfinite(energy_span):
        set_value('energy_variation', energy_span, 'experimental')
    if words is None:
        for name in FEATURES:
            if name not in {'pauses', 'pitch_variation', 'energy_variation'}:
                set_value(name, None, 'unavailable')
        return result

    timed = [(token, a, b) for word, a, b in words
             if 0 <= a <= b <= duration + 0.1
             for token in TOKEN.findall(word.lower().replace('’', "'"))]
    if not timed:
        for name in FEATURES:
            if name not in {'pauses', 'pitch_variation', 'energy_variation'}:
                set_value(name, None, 'insufficient_evidence')
        return result
    tokens = [token for token, _, _ in timed]
    set_value('speaking_rate', round(60 * len(tokens) / duration, 1))
    thirds = Counter(min(2, int(3 * (a + b) / (2 * duration))) for _, a, b in timed)
    if min(thirds[i] for i in range(3)) >= 4:
        set_value('rate_changes', [round(180 * thirds[i] / duration, 1) for i in range(3)])

    def event(i, length=1):
        return {'text': ' '.join(tokens[i:i + length]),
                'start_s': round(timed[i][1], 3), 'end_s': round(timed[i + length - 1][2], 3)}

    set_value('fillers', [event(i) for i, word in enumerate(tokens) if word in {'um', 'uh'}],
              'experimental')
    repeats = []
    i = 0
    while i < len(tokens) - 1:
        length = next((n for n in range(min(4, (len(tokens) - i) // 2), 0, -1)
                       if tokens[i:i + n] == tokens[i + n:i + 2 * n]
                       and any(token not in {'um', 'uh'} for token in tokens[i:i + n])), 0)
        if length:
            repeats.append(event(i, 2 * length))
            i += 2 * length
        else:
            i += 1
    set_value('repetitions', repeats, 'experimental')
    revisions = [event(i, len(marker)) for marker in REVISION_MARKERS
                 for i in phrases(tokens, list(marker))]
    revisions.extend({'text': word.strip(), 'start_s': round(a, 3), 'end_s': round(b, 3)}
                     for word, a, b in words if re.search(r'[A-Za-z][—-]$', word.strip()))
    set_value('revisions', sorted(revisions, key=lambda item: item['start_s']), 'experimental')
    if targets:
        matched = [target for target in targets if phrases(tokens, TOKEN.findall(target.lower()))
                   and TOKEN.findall(target.lower())]
        set_value('prompt_coverage', {'matched': matched,
                                      'missing': [target for target in targets if target not in matched]},
                  'experimental')
    set_value('organization', {name: any(phrases(tokens, marker.split()) for marker in markers)
                               for name, markers in STRUCTURE_MARKERS.items()}, 'experimental')
    return result
