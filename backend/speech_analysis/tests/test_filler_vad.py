from speech_analysis.filler_vad import filter_fillers_by_vad


def test_vad_filter_uses_union_of_speech_intervals_and_preserves_abstention():
    events = [
        {'text': 'uh', 'start_s': 1., 'end_s': 2.},
        {'text': 'um', 'start_s': 3., 'end_s': 4.},
    ]
    speech = [(1., 1.4), (1.3, 1.6), (3., 3.2)]
    assert filter_fillers_by_vad(events, speech) == events[:1]
    assert filter_fillers_by_vad(events, None) is None
    assert filter_fillers_by_vad(events, []) is None
    assert filter_fillers_by_vad([], [(0., 1.)]) == []


def test_paired_report_scores_same_reference_and_saves_timed_events(tmp_path, monkeypatch):
    import json
    import sys
    from types import SimpleNamespace
    from zipfile import ZipFile

    import numpy as np
    from speech_analysis.evaluate_verbatim_vad import main

    archive = tmp_path / 'annotations.zip'
    with ZipFile(archive, 'w') as z:
        z.writestr('corpusResources/meetings.xml', '<root><meeting observation="M"><speaker nxt_agent="A" global_name="S"/></meeting></root>')
        z.writestr('words/M.A.words.xml', '<root><w starttime="1" endtime="1.2">uh</w></root>')
        z.writestr('segments/M.A.segments.xml', '<root><segment transcriber_start="0" transcriber_end="3"/></root>')
    words = [SimpleNamespace(word='uh', start=1., end=1.2),
             SimpleNamespace(word='uh', start=4., end=4.2)]
    class Model:
        def __init__(self, *args, **kwargs):
            pass
        def transcribe(self, *args, **kwargs):
            return SimpleNamespace(words=words)
    monkeypatch.setitem(sys.modules, 'soundfile', SimpleNamespace(read=lambda *a, **k: (np.zeros(160000, dtype='float32'), 16000)))
    monkeypatch.setitem(sys.modules, 'torch', SimpleNamespace(set_num_threads=lambda n: None, from_numpy=lambda x: x))
    monkeypatch.setitem(sys.modules, 'crisperwhisper', SimpleNamespace(CrisperWhisperModel=Model))
    monkeypatch.setitem(sys.modules, 'silero_vad', SimpleNamespace(load_silero_vad=lambda: object(), get_speech_timestamps=lambda *a, **k: [{'start': 0, 'end': 48000}]))
    output = tmp_path / 'metrics.json'
    monkeypatch.setattr(sys, 'argv', ['evaluate', str(archive), str(tmp_path / 'M.A.wav'), '--model', 'mock', '--output', str(output)])
    main()
    report = json.loads(output.read_text())
    assert report['pooled']['features']['uh']['score'] == 2 / 3
    assert report['vad_candidate_pooled']['features']['uh']['score'] == 1
    assert report['vad_candidate_pooled']['features']['repetitions']['status'] == 'missing_reference'
    events = json.loads((tmp_path / 'filler-events.json').read_text())
    assert len(events['recordings'][0]['predicted']) == 2
    assert len(events['recordings'][0]['candidate']) == 1
    assert 'transcript' not in events['recordings'][0]
