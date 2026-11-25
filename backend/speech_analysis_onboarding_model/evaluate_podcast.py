"""Score filler events on contiguous annotated PodcastFillers excerpts."""

import argparse
import csv
import json
import subprocess
from pathlib import Path

from .evaluate import recording_event_metrics


def annotations(path, episode, start, duration):
    with path.open(newline='', encoding='utf-8-sig') as stream:
        rows = [row for row in csv.DictReader(stream) if row['podcast_filename'] == episode]
    if not rows:
        raise ValueError('episode has no annotation rows')
    end = start + duration
    events = []
    for row in rows:
        text = row['label_consolidated_vocab'].lower()
        left, right = (float(row[k]) for k in ('event_start_inepisode', 'event_end_inepisode'))
        if text in {'um', 'uh'} and left >= start and right <= end:
            events.append({'text': text, 'start_s': left - start, 'end_s': right - start})
    return events


def main():
    import numpy as np
    import torch
    from silero_vad import get_speech_timestamps, load_silero_vad
    from transformers import AutoModel

    from .fillers import ENCODERS, RATE, FillerClassifier, checkpoint_encoder, score_filler_windows, select_filler_events, load_checkpoint, score_transcript_fillers

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('audio', type=Path)
    parser.add_argument('csv', type=Path)
    parser.add_argument('episode')
    parser.add_argument('checkpoint', type=Path)
    parser.add_argument('--start', type=float, default=60)
    parser.add_argument('--duration', type=float, default=180)
    parser.add_argument('--threshold', type=float, action='append', help='Sweep thresholds on validation only')
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--transcript-candidates', action='store_true')
    mode.add_argument('--frame-head', action='store_true')
    parser.add_argument('--cache-dir')
    parser.add_argument('--min-frames', type=int, default=5, help='Minimum consecutive frames for frame-head events')
    args = parser.parse_args()
    thresholds = args.threshold or [.85]
    if any(not 0 < value <= 1 for value in thresholds):
        parser.error('thresholds must be in (0, 1]')
    if not 0 <= args.start or not 0 < args.duration <= 240:
        parser.error('provide a nonnegative start and duration within 240 seconds')
    if args.min_frames < 1 or (args.min_frames != 5 and not args.frame_head):
        parser.error('--min-frames requires a positive frame count and --frame-head')
    torch.set_num_threads(4)
    audio = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', str(args.start), '-i',
                            str(args.audio), '-t', str(args.duration), '-ac', '1', '-ar', str(RATE),
                            '-f', 'f32le', 'pipe:1'], capture_output=True, check=True, timeout=90)
    waveform = np.frombuffer(audio.stdout, dtype='<f4').copy()
    duration = len(waveform) / RATE
    reference = annotations(args.csv, args.episode, args.start, duration)
    intervals = [(i['start'] / RATE, i['end'] / RATE) for i in get_speech_timestamps(
        torch.from_numpy(waveform), load_silero_vad(), sampling_rate=RATE)]
    encoder = checkpoint_encoder(args.checkpoint)
    name, revision = ENCODERS[encoder]
    classifier = FillerClassifier
    if args.frame_head:
        from .train_filler_frames import FrameClassifier
        from .filler_frames import decode_frames, score_recording

        classifier = FrameClassifier
        metadata = torch.load(args.checkpoint, map_location='cpu', weights_only=True)
        if metadata.get('kind') != 'frame_filler':
            parser.error('--frame-head requires a frame-trained checkpoint')
    model = classifier(AutoModel.from_pretrained(name, revision=revision), encoder_name=encoder)
    load_checkpoint(model, args.checkpoint)
    if args.frame_head:
        frame_scores = score_recording(model, waveform, window_samples=metadata.get('window_samples', RATE))
    elif args.transcript_candidates:
        import whisper

        asr = whisper.load_model('small.en', device='cpu', download_root=args.cache_dir)
        transcript = asr.transcribe(waveform, language='en', word_timestamps=True, fp16=False,
                                    condition_on_previous_text=False)
        words = [(w['word'], w['start'], w['end']) for segment in transcript['segments']
                 for w in segment.get('words', [])]
        windows = list(score_transcript_fillers(model, waveform, words, intervals))
    else:
        windows = list(score_filler_windows(model, waveform, intervals))

    def centered(events):
        result = []
        for event in events:
            midpoint = (event['start_s'] + event['end_s']) / 2
            result.append({**event, 'start_s': midpoint, 'end_s': midpoint})
        return result

    results = []
    for threshold in thresholds:
        predicted = (decode_frames(frame_scores, duration, threshold, args.min_frames) if args.frame_head
                     else select_filler_events(windows, threshold))
        row = {'duration_s': duration, 'reference': reference, 'predicted': predicted}
        centers = {**row, 'reference': centered(reference), 'predicted': centered(predicted)}
        results.append({'episode': args.episode, 'start_s': args.start, 'encoder': encoder,
                        'threshold': threshold, 'min_frames': args.min_frames if args.frame_head else None,
                        'metrics': recording_event_metrics([row]),
                        'center_metrics': recording_event_metrics([centers]), **row})
    print(json.dumps(results[0] if len(results) == 1 else results, indent=2))


if __name__ == '__main__':
    main()
