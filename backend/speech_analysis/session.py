"""Combine independent recording measurements without inventing judgments."""

import subprocess
import json
from pathlib import Path

from .analysis import FEATURES
from .content import AREAS
from .video import NAMES as VIDEO_FEATURES


def load_manifest(path):
    path = Path(path)
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(manifest, dict) or not isinstance(manifest.get('recordings'), list):
        raise ValueError('manifest must contain a recordings list')
    recordings = manifest['recordings']
    if any(not isinstance(item, dict) for item in recordings):
        raise ValueError('recordings must be objects')
    combine_results([{'id': item.get('id'), 'result': {}} for item in recordings])
    result = []
    for item in recordings:
        audio = item.get('path')
        targets = item.get('targets', [])
        prompt = item.get('prompt', '')
        if not isinstance(audio, str) or not audio.strip():
            raise ValueError('recording path must be a nonempty string')
        if not isinstance(targets, list) or any(not isinstance(t, str) for t in targets):
            raise ValueError('targets must be a list of strings')
        if not isinstance(prompt, str):
            raise ValueError('prompt must be a string')
        result.append({'id': item['id'], 'path': str(path.parent / audio), 'targets': targets, 'prompt': prompt, 'video': item.get('video', False) is True})
    return result


def analyze_session(recordings, analyzer, video_analyzer=None):
    # Validate the request before running any expensive model inference.
    combine_results([{'id': item.get('id'), 'result': {}} for item in recordings])
    samples = []
    for item in recordings:
        try:
            result = analyzer(item['path'], item.get('targets', []), item.get('prompt', ''))
        except (OSError, RuntimeError, ValueError, ImportError, subprocess.SubprocessError) as exc:
            result = {'quality': {'errors': [f'recording: {type(exc).__name__}']}, 'features': {}}
        if item.get('video') and video_analyzer:
            try:
                video = video_analyzer(item['path'])
                result.setdefault('features', {}).update(video['features'])
                result.setdefault('quality', {})['video'] = video['quality']
                if video.get('landmark_evidence'):
                    result.setdefault('research', {})['video_landmarks'] = video['landmark_evidence']
            except (OSError, RuntimeError, ValueError, ImportError, subprocess.SubprocessError) as exc:
                result.setdefault('quality', {})['video'] = {'error': type(exc).__name__}
        fields = result.setdefault('features', {})
        names = (*FEATURES, *AREAS, *VIDEO_FEATURES) if item.get('video') else (*FEATURES, *AREAS)
        for name in names:
            fields.setdefault(name, {'status': 'unavailable', 'value': None})
        samples.append({'id': item['id'], 'result': result})
    return combine_results(samples)


def combine_results(samples):
    if not 2 <= len(samples) <= 3:
        raise ValueError('provide two or three recordings')
    ids = [sample.get('id') for sample in samples]
    if any(not isinstance(value, str) or not value.strip() for value in ids) or len(set(ids)) != len(ids):
        raise ValueError('recording IDs must be distinct nonempty strings')
    names = sorted({name for sample in samples for name in sample['result'].get('features', {})}
                   - {'organization', 'prompt_coverage'})
    observations = {}
    for name in names:
        rows = []
        for sample in samples:
            feature = sample['result'].get('features', {}).get(name, {'status': 'unavailable', 'value': None})
            rows.append({'sample_id': sample['id'], **feature})
        count = sum(row.get('value') is not None and row.get('status') not in
                    {'unavailable', 'insufficient_evidence'} for row in rows)
        coverage = 'multiple_samples' if count >= 2 else 'single_sample' if count else 'insufficient_evidence'
        observation = {'coverage': coverage, 'samples': rows}
        if name == 'hand_near_face':
            tracked = [row for row in rows if type(row.get('observed_returns')) is int
                       and row.get('status') == 'experimental' and row.get('value') is not None]
            if tracked:
                observation['proximity_returns'] = {
                    'tracked_sample_ids': [row['sample_id'] for row in tracked],
                    'sample_ids_with_returns': [row['sample_id'] for row in tracked
                                                if row['observed_returns'] > 0],
                }
        observations[name] = observation
    return {'schema_version': 1, 'samples': [
        {'id': sample['id'], 'quality': sample['result'].get('quality', {}),
         'research': sample['result'].get('research', {})} for sample in samples
    ], 'observations': observations}


def main():
    import argparse
    import os
    from .__main__ import analyze_recording

    parser = argparse.ArgumentParser(description='Analyze two or three English audio recordings on CPU.')
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--model', choices=['tiny.en', 'base.en', 'small.en'], default='small.en')
    parser.add_argument('--cache-dir', default=os.environ.get('SPEAKLY_MODEL_CACHE'))
    parser.add_argument('--filler-head', type=Path)
    parser.add_argument('--disfluency-head', type=Path)
    parser.add_argument('--pose-model', type=Path)
    parser.add_argument('--hand-model', type=Path)
    parser.add_argument('--face-model', type=Path)
    parser.add_argument('--content-openai', action='store_true',
                        help='Send transcript and prompt to OpenAI for experimental content analysis')
    args = parser.parse_args()
    try:
        recordings = load_manifest(args.manifest)
        from .video import analyze_video
        video_analyzer = (lambda path: analyze_video(path, args.pose_model, hand_model=args.hand_model, face_model=args.face_model)) if args.pose_model else None
        if any(item['video'] for item in recordings) and video_analyzer is None:
            raise ValueError('video recordings require --pose-model')
        result = analyze_session(recordings, lambda path, targets, prompt: analyze_recording(
            path, targets, args.model, args.cache_dir, args.filler_head,
            prompt=prompt, content_openai=args.content_openai, disfluency_head=args.disfluency_head), video_analyzer)
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Invalid manifest: {type(exc).__name__}\n')
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
