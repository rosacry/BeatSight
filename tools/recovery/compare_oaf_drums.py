"""Frozen official E-GMD checkpoint comparison, isolated from app defaults."""
import argparse
from collections import Counter
from datetime import datetime, timezone
from importlib.metadata import version
import json
from pathlib import Path
import sys
import time

import numpy as np

from compare_adt_str import BASE, PRIOR, save, verify
from probe_residual_input import acceptance, event_assignments, pool, truth_from
from score_timing import evaluate_timing
from transcribe import sha256

# Groove extended MIDI meanings override GM where they differ. Unrecognized
# output pitches remain explicit OT events; none are silently dropped.
COMPONENTS = {
    35: 'kick', 36: 'kick', 37: 'cross_stick', 38: 'snare', 40: 'snare',
    39: 'hand_clap', 41: 'tom_floor', 43: 'tom_floor', 58: 'tom_floor',
    45: 'tom_mid', 47: 'tom_mid', 48: 'tom_high', 50: 'tom_high',
    22: 'hihat_closed', 42: 'hihat_closed', 44: 'hihat_pedal',
    26: 'hihat_open', 46: 'hihat_open', 49: 'crash', 55: 'crash',
    57: 'crash', 52: 'crash', 51: 'ride', 53: 'ride_bell', 59: 'ride',
    54: 'tambourine', 56: 'cowbell', 70: 'maracas', 64: 'low_conga', 75: 'claves',
}


def notes_to_chart(notes):
    hits = []
    for onset, offset, pitch, velocity in np.asarray(notes).reshape(-1, 4):
        if not np.isfinite([onset, offset, pitch, velocity]).all() or onset < 0:
            raise ValueError('Invalid native note')
        if int(pitch) != pitch or not 21 <= pitch <= 108:
            raise ValueError('Pitch outside native 88-pitch output')
        hits.append({'time': float(onset) * 1000,
                     'component': COMPONENTS.get(int(pitch), f'unknown_pitch_{int(pitch)}'),
                     'groove_pitch': int(pitch), 'velocity': int(velocity)})
    return {'hitObjects': sorted(hits, key=lambda h: h['time'])}


def prepare(root):
    if root.resolve().parent != BASE or root.drive.upper() != 'C:':
        raise ValueError('A new scoped C: directory is required')
    prior = json.loads((PRIOR / 'metrics.json').read_text())
    assert prior['status'] == 'complete'
    files = [root / 'selection.json', root / 'evidence/model-load.json',
             PRIOR / 'metrics.json', Path(__file__), Path(__file__).with_name('oaf_runtime.py')]
    files += [Path(__file__).with_name(n) for n in [
        'score_timing.py', 'probe_residual_input.py', 'evaluate_mdb.py', 'compare_adt_str.py']]
    files += [f for d in ['source', 'checkpoint'] for f in (root / d).rglob('*') if f.is_file()]
    for base, names in [('deps/note_seq', ['audio_io.py', 'sequences_lib.py']),
                        ('legacy-deps/librosa', ['core/spectrum.py', 'filters.py', 'util/utils.py'])]:
        files += [root / base / n for n in names]
    rows = []
    for old in prior['tracks']:
        pred = PRIOR / old['track'] / 'predictions.json'
        assert sha256(pred) == old['candidate_prediction_sha256']
        truth = truth_from(Path(old['annotation']))
        chart = json.loads(pred.read_text())
        scores = {ms: {'baseline': evaluate_timing(chart, truth, int(ms) / 1000)} for ms in ['25', '50']}
        assert all(scores[ms]['baseline'] == old['scores'][ms]['candidate'] for ms in scores)
        files += [Path(old['stem']), Path(old['annotation']), pred]
        rows.append({'track': old['track'], 'stem': old['stem'], 'annotation': old['annotation'],
                     'baseline_predictions': str(pred), 'duration_seconds': old['duration_seconds'], 'scores': scores})
    hp = json.loads((root / 'evidence/model-load.json').read_text())['hparams']
    hp['batch_size'] = 1; hp['truncated_length_secs'] = 0
    protocol = {
        'utc': datetime.now(timezone.utc).isoformat(), 'selection': json.loads((root / 'selection.json').read_text()),
        'hparams': hp, 'tracks': rows, 'mapping': COMPONENTS,
        'mapping_limit': '8-hit training merges snare/x-stick/clap, tom/conga, HH/tambourine/maracas and ride-bell/cowbell. Map emitted base pitch literally, retain all truth including OT. No inferred articulation recovery.',
        'execution': 'Native process_record -> provide_batch -> build_model -> sigmoid > .5 -> native onset-only predict_sequence. Whole recording, batch 1, no chunking, seed 0, CPU float32, intra threads 2/inter 1. No app code or threshold changes.',
        'input': 'Same seven saved mono FLOAT 44.1kHz stems. Native process_record normalizes whole-record peak then roundtrips PCM16; native librosa0.7.2 mel uses spec_hop_length512, not unused hop_length441. Native batching truncates final partial frame. Preserve reference tail and all emitted notes.',
        'compatibility': 'TF2.13.1 CPU with pinned current primary TF-compat source; not demonstrated TF1.15 paper-runtime parity. numba.decorators.jit and keras.legacy_tf_layers module aliases only. Skip unrelated magenta package initialization, execute required primary common function. Native primary model variables all restored exactly.',
        'packages': {n: version(n) for n in ['tensorflow-intel', 'keras', 'tf-slim', 'librosa', 'note-seq', 'numpy', 'scipy', 'numba', 'protobuf']},
        'gate_50ms': {'minimum_pooled_f1_gain': .01, 'maximum_precision_loss': .01,
                      'maximum_track_f1_loss': .02, 'tom_tp_must_not_decrease': True, 'maximum_snare_recall_loss': .01},
        'stop_rule': 'One default checkpoint/decoder; no parameter sweep. Failure stops before user songs. No independent held-out claim; development set repeatedly inspected. KLEWS/Adapt excluded.',
        'protected': [{'path': str(p.resolve()), 'sha256': sha256(p)} for p in sorted(set(files))],
    }
    verify(json.loads((root / 'evidence/prior-preservation.json').read_text())['files'])
    save(root / 'protocol.json', protocol)
    print(json.dumps({'prepared': len(rows), 'hashes': len(protocol['protected']), 'baseline50': pool(rows, 'baseline', '50')['micro']}), flush=True)


def run(root):
    protocol = json.loads((root / 'protocol.json').read_text()); verify(protocol['protected'])
    from oaf_runtime import load
    tf, configs, data, model, infer = load(root)
    from magenta.models.onsets_frames_transcription import audio_label_data_utils, constants
    from note_seq.protobuf import music_pb2
    from note_seq import midi_io
    hp = configs.CONFIG_MAP['drums'].hparams
    hp.batch_size = 1; hp.truncated_length_secs = 0
    assert hp.values() == protocol['hparams']
    out = root / 'full-recordings'; out.mkdir(exist_ok=False)
    save(out / 'started.json', {'utc': datetime.now(timezone.utc).isoformat(), 'protocol_sha256': sha256(root / 'protocol.json')})
    np.random.seed(0); rows = []
    checkpoint = str(root / 'checkpoint/model.ckpt-569400')
    with tf.Graph().as_default():
        tf.set_random_seed(0)
        examples = tf.placeholder(tf.string, [None])
        dataset = data.provide_batch(examples, True, hp, False, False, 0)
        iterator = tf.data.make_initializable_iterator(dataset)
        next_record = iterator.get_next()
        spec = tf.placeholder(tf.float32, [1, None, hp.spec_n_bins, 1])
        length = tf.placeholder(tf.int32, [1])
        outputs = model.build_model(spec, length, hp, False)
        # For drums the native decoder uses only these two outputs. Building
        # every branch keeps the complete checkpoint variable contract checked.
        probs_op = tf.sigmoid(outputs[1]); velocities_op = outputs[3]
        variables = tf.global_variables(); checkpoint_shapes = dict(tf.train.list_variables(checkpoint))
        assert all(checkpoint_shapes[v.name[:-2]] == v.shape.as_list() for v in variables)
        saver = tf.train.Saver()
        with tf.Session(config=tf.ConfigProto(intra_op_parallelism_threads=2, inter_op_parallelism_threads=1)) as sess:
            saver.restore(sess, checkpoint)
            assert all(np.array_equal(sess.run(v), tf.train.load_variable(checkpoint, v.name[:-2])) for v in variables)
            save(out / 'model-load.json', {'variables_restored_exactly': len(variables), 'model_parameters': sum(int(np.prod(v.shape)) for v in variables)})
            for original in protocol['tracks']:
                started = time.perf_counter(); row = json.loads(json.dumps(original))
                folder = out / row['track']; folder.mkdir()
                records = list(audio_label_data_utils.process_record(
                    wav_data=Path(row['stem']).read_bytes(), sample_rate=hp.sample_rate,
                    ns=music_pb2.NoteSequence(), example_id=row['track'], min_length=0, max_length=-1,
                    allow_empty_notesequence=True, load_audio_with_librosa=False))
                assert len(records) == 1
                example = records[0]; raw = example.SerializeToString()
                (folder / 'native-example.pb').write_bytes(raw)
                audio = example.features.feature['audio'].bytes_list.value[0]
                (folder / 'native-normalized-pcm16.wav').write_bytes(audio)
                sess.run(iterator.initializer, {examples: [raw]})
                features, labels = sess.run(next_record)
                np.save(folder / 'native-features.npy', features.spec)
                # Independently check the dataset's native waveform/feature path,
                # including its floor-length final frame truncation.
                independent_spec = data.wav_to_spec(audio, hp)
                nframes = int(data.wav_to_num_frames(audio, data.hparams_frames_per_second(hp)))
                assert features.length.tolist() == [nframes]
                assert np.array_equal(features.spec[0, :, :, 0], independent_spec[:nframes])
                probs, velocities = sess.run([probs_op, velocities_op], {spec: features.spec, length: features.length})
                assert np.isfinite(probs).all() and np.isfinite(velocities).all()
                np.savez_compressed(folder / 'native-outputs.npz', onset_probs=probs[0], velocity_values=velocities[0])
                onsets = probs[0] > hp.predict_onset_threshold
                seq = infer.predict_sequence(probs[0], probs[0], onsets, onsets, onsets,
                                             velocities[0], constants.MIN_MIDI_PITCH, hp, onsets_only=True)
                for note in seq.notes: note.is_drum = True
                (folder / 'native-sequence.pb').write_bytes(seq.SerializeToString())
                midi_io.sequence_proto_to_midi_file(seq, str(folder / 'native-groove-pitches.mid'))
                notes = np.array([[n.start_time, n.end_time, n.pitch, n.velocity] for n in seq.notes]).reshape(-1, 4)
                np.save(folder / 'native-notes.npy', notes)
                # Native drum decoding emits every above-threshold frame,
                # including adjacent frames and simultaneous same-family hits.
                fi, pi = np.nonzero(onsets)
                assert len(notes) == len(fi)
                assert np.array_equal(notes[:, 2], pi + constants.MIN_MIDI_PITCH)
                assert np.allclose(notes[:, 0], fi / data.hparams_frames_per_second(hp), atol=1e-12, rtol=0)
                chart = notes_to_chart(notes); save(folder / 'predictions.json', chart)
                row['pitch_counts'] = dict(Counter(str(h['groove_pitch']) for h in chart['hitObjects']))
                row['audit'] = {'frames': nframes, 'native_feature_path_exact': True,
                                'onset_grid_reconstructed': True, 'notes': len(notes),
                                'adjacent_active_pairs': int((onsets[1:] & onsets[:-1]).sum()),
                                'predictions_beyond_audio': sum(h['time'] / 1000 >= row['duration_seconds'] for h in chart['hitObjects'])}
                truth = truth_from(Path(row['annotation']))
                for ms in ['25', '50']:
                    row['scores'][ms]['candidate'] = evaluate_timing(chart, truth, int(ms) / 1000)
                    save(folder / f'events-{ms}ms.json', event_assignments(chart, truth, int(ms) / 1000))
                row['runtime_seconds'] = time.perf_counter() - started
                row['prediction_sha256'] = sha256(folder / 'predictions.json')
                rows.append(row); save(folder / 'metrics.json', row)
                print(json.dumps({'track': row['track'], 'seconds': row['runtime_seconds'], 'candidate50': row['scores']['50']['candidate']['micro']}), flush=True)
    pooled = {ms: {arm: pool(rows, arm, ms) for arm in ['baseline', 'candidate']} for ms in ['25', '50']}
    decision = acceptance(pooled['50']['baseline'], pooled['50']['candidate'],
                          [r['scores']['50']['candidate']['micro']['f1'] - r['scores']['50']['baseline']['micro']['f1'] for r in rows])
    verify(protocol['protected'])
    save(out / 'metrics.json', {'status': 'complete', 'protocol_sha256': sha256(root / 'protocol.json'),
         'tracks': rows, 'pooled': pooled, 'decision': decision, 'protected_hashes_verified_after': len(protocol['protected'])})
    print(json.dumps({'pooled50': pooled['50']['candidate'], 'decision': decision}), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(); parser.add_argument('action', choices=['prepare', 'run'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args(); {'prepare': prepare, 'run': run}[args.action](args.root)
