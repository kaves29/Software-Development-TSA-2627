"""Produce an offline, readable handoff from one audio or audio-video response."""

import argparse
import json
import math
from pathlib import Path

from .session import analyze_session
from .video import NAMES as VIDEO_FEATURES

EVENT_FEATURES = {'pauses', 'fillers', 'repetitions', 'revisions'}
UNITS = {
    'speaking_rate': 'words per minute',
    'rate_changes': 'words per minute by recording third',
    'pitch_variation': 'semitones',
    'energy_variation': 'decibels',
    'shoulder_tilt': 'relative to shoulder width',
    'lateral_lean': 'relative to shoulder width',
    'torso_sway': 'shoulder widths per sampled frame',
    'vertical_motion': 'shoulder widths per sampled frame',
    'head_turn_proxy': 'distance asymmetry ratio',
    'head_motion': 'shoulder widths per sampled frame',
    'left_hand_motion': 'shoulder widths per sampled frame',
    'right_hand_motion': 'shoulder widths per sampled frame',
    'hand_asymmetry': 'shoulder widths per sampled frame',
    'gesture_span': 'shoulder widths',
    'rapid_gesture': 'fraction of tracked frames',
    'hands_together': 'fraction of tracked frames',
    'hand_near_face': 'fraction of tracked frames',
    'wrist_visibility': 'average fraction of wrists tracked',
    'pose_coverage': 'fraction of sampled frames',
}


def _safe_value(name, value):
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value if math.isfinite(value) else None
    if isinstance(value, list):
        if name in EVENT_FEATURES:
            events = []
            for event in value:
                if not isinstance(event, dict):
                    return None
                start, end = event.get('start_s'), event.get('end_s')
                if (isinstance(start, (int, float)) and not isinstance(start, bool)
                        and isinstance(end, (int, float)) and not isinstance(end, bool)
                        and math.isfinite(start) and math.isfinite(end) and 0 <= start <= end):
                    row = {'start_s': start, 'end_s': end}
                    if name == 'fillers' and event.get('text') in {'um', 'uh'}:
                        row['kind'] = event['text']
                    events.append(row)
                else:
                    return None
            return {'count': len(events), 'events': events}
        if all(isinstance(item, (int, float)) and not isinstance(item, bool)
               and math.isfinite(item) for item in value):
            return value
    return None


def make_handoff(session, *, question=''):
    """Return only descriptive measurements; exclude transcripts and file paths."""
    if len(session.get('samples', [])) != 1:
        raise ValueError('handoff requires exactly one analyzed response')
    observations = {}
    lines = []
    for name, observation in session.get('observations', {}).items():
        row = observation['samples'][0]
        value = _safe_value(name, row.get('value'))
        status = row.get('status', 'unavailable')
        if status in {'unavailable', 'insufficient_evidence'}:
            value = None
        if value is None and status not in {'unavailable', 'insufficient_evidence'}:
            status = 'unavailable'
        item = {'modality': 'video' if name in VIDEO_FEATURES else 'audio',
                'status': status, 'value': value}
        if isinstance(row.get('method'), str):
            item['method'] = row['method']
        if type(row.get('valid_frames')) is int and row['valid_frames'] >= 0:
            item['valid_frames'] = row['valid_frames']
        if (name == 'hand_near_face' and value is not None and type(row.get('observed_returns')) is int
                and row['observed_returns'] >= 0):
            item['observed_returns'] = row['observed_returns']
        if name in UNITS:
            item['unit'] = UNITS[name]
        observations[name] = item
        label = name.replace('_', ' ')
        if value is None:
            lines.append(f'{label}: {status.replace("_", " ")}.')
        elif name in EVENT_FEATURES:
            lines.append(f'{label}: {value["count"]} detected events ({status}).')
        else:
            unit = f' {UNITS[name]}' if name in UNITS else ''
            lines.append(f'{label}: {value}{unit} ({status}).')
            if 'observed_returns' in item:
                lines.append(f'hand near face: {item["observed_returns"]} observed returns ({status}).')
    sample = session.get('samples', [{}])[0]
    return {
        'schema_version': 1,
        'question': question,
        'quality': sample.get('quality', {}),
        'observations': observations,
        'summary': '\n'.join(lines),
        'limitations': 'Measurements are experimental and may be incorrect. They do not establish a weakness or emotional state.',
    }


def analyze_input(audio_path, *, video_path=None, question='', targets=None,
                  analyzer, video_analyzer=None):
    """Analyze a recording using injected audio and optional video analyzers."""
    if video_path is not None and video_analyzer is None:
        raise ValueError('video analysis requires a video analyzer')
    recording = {'id': 'response', 'path': str(audio_path), 'targets': targets or [],
                 'prompt': question, 'video': video_path is not None}
    if video_path is not None:
        recording['video_path'] = str(video_path)
    session = analyze_session([recording], analyzer, video_analyzer, allow_single=True)
    handoff = make_handoff(session, question=question)
    handoff['input_modalities'] = ['audio', 'video'] if video_path is not None else ['audio']
    available = {item['modality'] for item in handoff['observations'].values() if item['value'] is not None}
    handoff['analysis_status'] = ('observations_available' if set(handoff['input_modalities']) <= available
                                  else 'partial' if available else 'unavailable')
    if video_path is not None:
        handoff['alignment'] = 'not verified; audio and video were analyzed independently'
    return handoff


def analyze_onboarding(audio_path, *, video_path=None, question='', targets=None,
                       model_name='small.en', cache_dir=None, filler_head=None,
                       pose_model=None, hand_model=None, face_model=None, max_seconds=240):
    """Run the local analyzers and return a text-and-JSON-ready handoff."""
    from .__main__ import analyze_recording
    from .video import analyze_video

    if video_path is not None and pose_model is None:
        raise ValueError('video analysis requires a pose model')

    def audio(path, sample_targets, prompt):
        result = analyze_recording(path, sample_targets, model_name, cache_dir, filler_head,
                                   prompt=prompt, content_openai=False, max_seconds=max_seconds)
        filler = result.get('features', {}).get('fillers', {})
        if filler_head is None and filler.get('value') is not None:
            filler.setdefault('method', 'transcript-derived estimate')
        return result

    def video(path):
        return analyze_video(path, pose_model, hand_model=hand_model,
                             face_model=face_model, max_seconds=max_seconds)

    return analyze_input(audio_path, video_path=video_path, question=question, targets=targets,
                         analyzer=audio, video_analyzer=video if video_path is not None else None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio', type=Path, help='Audio file or video file containing an audio track')
    parser.add_argument('--video', type=Path, help='Optional video file; may be the same file as audio')
    parser.add_argument('--question', default='', help='Question or prompt answered in the recording')
    parser.add_argument('--target', action='append', default=[])
    parser.add_argument('--model', choices=['tiny.en', 'base.en', 'small.en'], default='small.en')
    parser.add_argument('--cache-dir')
    parser.add_argument('--filler-head', type=Path)
    parser.add_argument('--pose-model', type=Path)
    parser.add_argument('--hand-model', type=Path)
    parser.add_argument('--face-model', type=Path)
    parser.add_argument('--max-seconds', type=int, choices=range(1, 3601), default=240, metavar='1–3600')
    args = parser.parse_args()
    if args.video is not None and args.pose_model is None:
        parser.error('--video requires --pose-model')
    result = analyze_onboarding(args.audio, video_path=args.video, question=args.question, targets=args.target,
                                model_name=args.model, cache_dir=args.cache_dir, filler_head=args.filler_head,
                                pose_model=args.pose_model, hand_model=args.hand_model, face_model=args.face_model,
                                max_seconds=args.max_seconds)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == '__main__':
    main()
