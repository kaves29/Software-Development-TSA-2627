"""Score fresh verbatim ASR on full AMI recordings using manual references."""

import argparse
import json
from pathlib import Path
from xml.etree import ElementTree
from zipfile import ZipFile

from .ami_references import segment_gap_references, word_references
from .benchmark_features import benchmark
from .verbatim import analyze_timestamped_words


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('annotations', type=Path)
    parser.add_argument('recordings', nargs='+', type=Path, help='Full WAV tracks named MEETING.SLOT.wav')
    parser.add_argument('--model', required=True, help='Local CrisperWhisper Transformers snapshot')
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cpu')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if len({path.stem for path in args.recordings}) != len(args.recordings):
        parser.error('recording identifiers must be unique')

    import numpy as np
    import soundfile as sf
    import torch
    from crisperwhisper import CrisperWhisperModel
    from silero_vad import get_speech_timestamps, load_silero_vad

    torch.set_num_threads(4)
    model = CrisperWhisperModel(args.model, backend='transformers', device=args.device,
                               compute_type='float16' if args.device == 'cuda' else 'float32')
    vad = load_silero_vad()
    rows = []
    tolerances = {'speaking_rate': 10, 'rate_changes': 15}
    with ZipFile(args.annotations) as archive:
        with archive.open('corpusResources/meetings.xml') as stream:
            meetings = ElementTree.parse(stream)
        speakers = {
            f"{meeting.attrib['observation']}.{speaker.attrib['nxt_agent']}": speaker.attrib['global_name']
            for meeting in meetings.iter('meeting') for speaker in meeting.findall('speaker')
        }
        for path in args.recordings:
            audio, sample_rate = sf.read(path, dtype='float32')
            if sample_rate != 16000 or audio.ndim != 1:
                parser.error(f'{path}: provide a mono 16 kHz complete track')
            duration = len(audio) / sample_rate
            ref = word_references(archive, path.stem, duration)
            ref['pauses'] = segment_gap_references(archive, path.stem, duration)
            speech = [(r['start'] / sample_rate, r['end'] / sample_rate)
                      for r in get_speech_timestamps(torch.from_numpy(np.ascontiguousarray(audio)),
                                                     vad, sampling_rate=sample_rate)]
            result = model.transcribe(audio, sr=sample_rate, language='en', word_timestamps=True)
            features = analyze_timestamped_words(duration, speech, result.words or [])
            rows.append({'id': path.stem, 'speaker': speakers[path.stem], 'duration_s': duration,
                         'features': features, 'reference': ref})
            report = {
                'model': args.model,
                'complete': len(rows) == len(args.recordings),
                'pooled': benchmark(rows, tolerances),
                'per_recording': {
                    row['id']: benchmark([row], tolerances) for row in rows
                },
            }
            temporary = args.output.with_suffix(args.output.suffix + '.tmp')
            temporary.write_text(json.dumps(report, indent=2) + '\n')
            temporary.replace(args.output)
            print(f'Analyzed {path.stem}: {duration:.1f}s', flush=True)


if __name__ == '__main__':
    main()
