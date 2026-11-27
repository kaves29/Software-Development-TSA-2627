import argparse
import json
import os
import resource
import subprocess
import sys
import time
from pathlib import Path

from .analysis import analyze_features

SAMPLE_RATE = 16000
MAX_SECONDS = 240


def decode_audio(path):
    import numpy as np

    completed = subprocess.run(
        ['ffmpeg', '-v', 'error', '-nostdin', '-i', str(path), '-map', '0:a:0',
         '-t', str(MAX_SECONDS + 1), '-ac', '1', '-ar', str(SAMPLE_RATE),
         '-f', 'f32le', 'pipe:1'],
        capture_output=True, check=True, timeout=90,
    )
    return np.frombuffer(completed.stdout, dtype='<f4').copy()


def analyze_recording(path, targets, model_name, cache_dir, filler_head=None, *, prompt='', content_openai=False,
                      disfluency_head=None):
    import numpy as np
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad

    started = time.perf_counter()
    waveform = decode_audio(path)
    duration = len(waveform) / SAMPLE_RATE
    if not duration or duration > MAX_SECONDS:
        raise ValueError(f'provide an audio recording up to {MAX_SECONDS} seconds')
    torch.set_num_threads(min(4, os.cpu_count() or 1))
    speech = [(row['start'] / SAMPLE_RATE, row['end'] / SAMPLE_RATE)
              for row in get_speech_timestamps(torch.from_numpy(waveform), load_silero_vad(),
                                               sampling_rate=SAMPLE_RATE)]
    coverage = sum(end - start for start, end in speech)
    errors = []
    words, pitch_span = None, None
    clipping = float(np.mean(np.abs(waveform) >= 0.999))
    if coverage >= 1 and clipping < 0.05:
        try:
            import whisper

            transcript = whisper.load_model(model_name, device='cpu', download_root=cache_dir).transcribe(
                waveform, language='en', fp16=False, word_timestamps=True,
                condition_on_previous_text=False, temperature=0,
            )
            words = [(w['word'], w['start'], w['end'])
                     for segment in transcript['segments'] for w in segment.get('words', [])
                     if any(w['end'] > start and w['start'] < end for start, end in speech)]
        except (OSError, RuntimeError, ValueError, ImportError) as exc:
            errors.append(f'transcription: {type(exc).__name__}')
        try:
            import librosa

            for start, end in speech:
                if end - start < 0.2:
                    continue
                # Process one speech interval at a time to avoid tracking across silence.
                sample = waveform[int(start * SAMPLE_RATE):int(end * SAMPLE_RATE)]
                pitch, voiced, _ = librosa.pyin(sample, fmin=65, fmax=500, sr=SAMPLE_RATE)
                selected = pitch[voiced & np.isfinite(pitch)]
                if pitch_span is None:
                    pitch_span = []
                pitch_span.extend(selected)
            pitch_span = (round(float(12 * np.log2(np.percentile(pitch_span, 90) /
                                                  np.percentile(pitch_span, 10))), 2)
                          if pitch_span and len(pitch_span) >= 20 else None)
        except (OSError, RuntimeError, ValueError, ImportError) as exc:
            errors.append(f'pitch: {type(exc).__name__}')
            pitch_span = None

    from .acoustics import energy_variation

    energy_span = energy_variation(waveform, SAMPLE_RATE, speech) if coverage >= 1 and clipping < 0.05 else None
    features = analyze_features(duration, speech if clipping < 0.05 else [], words, targets, pitch_span,
                                energy_span=energy_span)
    if features['fillers']['value'] is not None:
        features['fillers']['method'] = 'transcript heuristic'
    from .content import content_from_words

    features.update(content_from_words(words, prompt, os.environ.get('OPENAI_API_KEY', '') if content_openai else '',
                                      model=os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')))
    if filler_head and coverage >= 1 and clipping < 0.05:
        try:
            if cache_dir:
                os.environ.setdefault('HF_HOME', str(cache_dir))
            from transformers import AutoModel

            from .fillers import ENCODERS, FillerClassifier, detect_fillers, load_checkpoint, checkpoint_encoder

            encoder_name = checkpoint_encoder(filler_head)
            base_model, base_revision = ENCODERS[encoder_name]
            metadata = torch.load(filler_head, map_location='cpu', weights_only=True)
            is_frame = metadata.get('kind') == 'frame_filler'
            if is_frame:
                from .train_filler_frames import FrameClassifier

                classifier = FrameClassifier
            else:
                classifier = FillerClassifier
            model = classifier(AutoModel.from_pretrained(base_model, revision=base_revision),
                               encoder_name=encoder_name)
            load_checkpoint(model, filler_head)
            if is_frame:
                from .filler_frames import decode_frames, score_recording

                probabilities = score_recording(model, waveform,
                    window_samples=metadata.get('window_samples', SAMPLE_RATE))
                events = decode_frames(probabilities, duration, threshold=.80, min_frames=12)
                method = f'{encoder_name} frame classifier (.80, 12 frames)'
            else:
                events = detect_fillers(model, waveform, speech)
                method = f'{encoder_name} fixed windows'
            features['fillers'] = {'status': 'experimental', 'value': events, 'method': method}
        except (OSError, RuntimeError, ValueError, ImportError, KeyError, TypeError, AttributeError) as exc:
            errors.append(f'filler classifier: {type(exc).__name__}')
    if any(error.startswith('pitch:') for error in errors):
        features['pitch_variation']['status'] = 'unavailable'
    research = {}
    if disfluency_head and coverage >= 1 and clipping < 0.05:
        try:
            from transformers import AutoModel
            from .fillers import ENCODERS
            from .disfluency_model import DisfluencyClassifier, predict_segments

            checkpoint = torch.load(disfluency_head, map_location='cpu', weights_only=True)
            encoder_name = checkpoint['encoder']
            base_model, revision = ENCODERS[encoder_name]
            if checkpoint['revision'] != revision:
                raise ValueError('checkpoint revision mismatch')
            model = DisfluencyClassifier(AutoModel.from_pretrained(base_model, revision=revision))
            model.head.load_state_dict(checkpoint['head'])
            research['disfluency_segments'] = {'status': 'experimental',
                'meaning': 'uncalibrated probabilities of parsed annotations per segment, not event timestamps',
                'segments': predict_segments(model, torch.from_numpy(waveform))}
        except (OSError, RuntimeError, ValueError, KeyError, ImportError) as exc:
            errors.append(f'disfluency classifier: {type(exc).__name__}')
            research['disfluency_segments'] = {'status': 'unavailable', 'segments': None}
    return {
        'schema_version': 1,
        'quality': {'duration_s': round(duration, 3), 'speech_s': round(coverage, 3),
                    'clipping_fraction': round(clipping, 4), 'errors': errors},
        'features': features,
        'research': research,
        'cpu': {'elapsed_s': round(time.perf_counter() - started, 3),
                'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss *
                (1 if sys.platform == 'darwin' else 1024)},
    }


def main():
    parser = argparse.ArgumentParser(description='Analyze one English speaking response on CPU.')
    parser.add_argument('audio', type=Path)
    parser.add_argument('--target', action='append', default=[], help='Required prompt concept or phrase')
    parser.add_argument('--model', choices=['tiny.en', 'base.en', 'small.en'], default='small.en')
    parser.add_argument('--cache-dir', default=os.environ.get('SPEAKLY_MODEL_CACHE'))
    parser.add_argument('--filler-head', type=Path, help='Optional research checkpoint')
    parser.add_argument('--disfluency-head', type=Path, help='Optional unvalidated research checkpoint')
    args = parser.parse_args()
    try:
        result = analyze_recording(args.audio, args.target, args.model, args.cache_dir, args.filler_head,
                                   disfluency_head=args.disfluency_head)
    except (OSError, RuntimeError, ValueError, ImportError, subprocess.SubprocessError) as exc:
        parser.exit(1, f'Audio analysis failed: {exc}\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
