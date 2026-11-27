"""Compare repetition decoders on timed ASR words and manual AMI references."""

import argparse
import json
import math
from pathlib import Path
from zipfile import ZipFile

from .ami_disfluency import repetition_references
from .analysis import TOKEN
from .evaluate import recording_event_metrics
from .verbatim import level_gated_fillers, repeat_events

FILLERS = {'um', 'uh'}
EDIT_WORDS = FILLERS | {'yeah', 'well', 'so', 'like', 'er', 'ah', 'oh', 'maybe', 'no'}
EDIT_PHRASES = {'i mean', 'you know', 'sort of', 'kind of', 'i guess', 'i think'}
SAMPLE_RATE = 16000


def can_bridge(bridge, phrase):
    return (' '.join(token for token, *_ in bridge) in EDIT_PHRASES
            or all(token in EDIT_WORDS or clipped
                   or (len(token) <= 2 and any(word.startswith(token) and word != token for word in phrase))
                   for token, _, _, clipped in bridge))


def bridged_repetitions(words):
    """Allow a short editing cue between two copies of the same phrase."""
    timed = [(token, start, end, raw.rstrip().endswith(('-', '—')))
             for raw, start, end in words
             for token in TOKEN.findall(raw.lower().replace('’', "'"))]
    tokens = [token for token, *_ in timed]
    events = []
    index = 0
    while index + 1 < len(tokens):
        choices = []
        for width in range(1, min(4, (len(tokens) - index) // 2) + 1):
            repeat_start = index + width
            phrase = tokens[index:repeat_start]
            if any(token in FILLERS for token in phrase):
                continue
            for skipped in range(4):
                next_start = repeat_start + skipped
                end = next_start + width
                if (tokens[next_start:end] != phrase
                        or timed[next_start][1] - timed[repeat_start - 1][2] > 1.05
                        or not can_bridge(timed[repeat_start:next_start], phrase)):
                    continue
                while tokens[end:end + width] == phrase and timed[end][1] - timed[end - 1][2] <= 1.05:
                    end += width
                choices.append((width, -skipped, end))
        if not choices:
            index += 1
            continue
        _, _, stop = max(choices)
        start, end = timed[index][1], timed[stop - 1][2]
        if start < end:
            events.append({'start_s': start, 'end_s': end})
        index = stop
    return events


def paired_events(words, audio, sample_rate):
    baseline = [{key: event[key] for key in ('start_s', 'end_s')}
                for event in repeat_events(words)]
    return {name: level_gated_fillers(events, audio, sample_rate)
            for name, events in (('adjacent', baseline), ('bridged', bridged_repetitions(words)))}


def gate_against_track(events, waveform, offset):
    # An excerpt containing only crosstalk should not set its own second level reference.
    absolute = [{'start_s': event['start_s'] + offset, 'end_s': event['end_s'] + offset}
                for event in events]
    retained = level_gated_fillers(absolute, waveform, SAMPLE_RATE, drop_db=-10 * math.log10(.13))
    return [{key: event[key] - offset for key in ('start_s', 'end_s')} for event in retained]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path, help='AMI annotations ZIP')
    parser.add_argument('model', type=Path, help='Local CrisperWhisper Small snapshot')
    parser.add_argument('recordings', type=Path, nargs='+', help='16 kHz mono WAVs named MEETING.SLOT.wav')
    parser.add_argument('--offset', type=int, action='append', required=True,
                        help='Beginning of a 180-second excerpt, in seconds. Repeat for multiple excerpts.')
    parser.add_argument('--cache-dir', type=Path, help='Local CTranslate2 conversion cache')
    args = parser.parse_args()
    offsets = sorted(args.offset)
    if offsets[0] < 0 or any(b - a < 180 for a, b in zip(offsets, offsets[1:])):
        parser.error('offsets must select disjoint, nonnegative excerpts')

    import soundfile as sf
    import torch
    from crisperwhisper import CrisperWhisperModel

    torch.set_num_threads(2)
    model = CrisperWhisperModel(str(args.model), backend='ct2', device='cpu', compute_type='int8',
                               cache_dir=args.cache_dir)
    results = {'adjacent': [], 'bridged': [], 'bridged_track_gate': []}
    excerpts = []
    with ZipFile(args.annotations) as annotations:
        for path in args.recordings:
            waveform, sample_rate = sf.read(path, dtype='float32')
            if sample_rate != SAMPLE_RATE or waveform.ndim != 1:
                parser.error(f'{path}: provide 16 kHz mono audio')
            duration = len(waveform) / SAMPLE_RATE
            if offsets[-1] + 180 > duration:
                parser.error(f'{path}: final excerpt exceeds track duration')
            labels = repetition_references(annotations, path.stem, duration)
            if labels is None:
                parser.error(f'{path}: no manual repetition labels')
            for offset in offsets:
                words = transcribe_excerpt(model, waveform, offset)
                references = [{key: event[key] - offset for key in ('start_s', 'end_s')}
                              for event in labels['events']
                              if offset <= event['start_s'] < event['end_s'] <= offset + 180]
                predictions = paired_events(words, waveform[offset * SAMPLE_RATE:(offset + 180) * SAMPLE_RATE],
                                            SAMPLE_RATE)
                predictions['bridged_track_gate'] = gate_against_track(predictions['bridged'], waveform, offset)
                excerpts.append({'track': path.stem, 'start_s': offset, 'reference_count': len(references)})
                for name, events in predictions.items():
                    results[name].append({'duration_s': 180, 'reference': references, 'predicted': events})
    print(json.dumps({'excerpts': excerpts,
                      'results': {name: recording_event_metrics(rows) for name, rows in results.items()}},
                     allow_nan=False, indent=2))


def transcribe_excerpt(model, waveform, offset):
    words = []
    # Context around the 30-second cores avoids committing duplicate words at chunk boundaries.
    for start in range(offset, offset + 180, 30):
        context_start = max(0, start - 3)
        audio = waveform[context_start * SAMPLE_RATE:(start + 33) * SAMPLE_RATE]
        result = model.transcribe(audio, sr=SAMPLE_RATE, language='en', word_timestamps=True)
        for word in result.words or []:
            first = word.start + context_start
            last = word.end + context_start
            if not (0 <= word.start < word.end and start <= (first + last) / 2 < start + 30):
                continue
            words.append((word.word, max(0., first - offset), min(180., last - offset)))
    return words


if __name__ == '__main__':
    main()
