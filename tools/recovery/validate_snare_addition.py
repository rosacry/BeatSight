"""Frozen external-corpus validation of the unchanged snare addition rule.

All outputs are new C: artifacts. Dataset sources and prior runtimes stay read-only.
Run prepare before either inference arm; score only after both arms finish.
"""
import argparse
import ast
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import random
import shutil
import sys
import time
import xml.etree.ElementTree as ET

import numpy as np
import soundfile as sf

from compare_adt_str import BASE, save, verify
from compare_snare_addition import RULE, add_snares, audit_additions, scoped_root
from evaluate_mdb import drum_family
from probe_residual_input import acceptance, event_assignments, pool, truth_from
from score_timing import evaluate_timing, timing_summary
from transcribe import sha256

OAF = BASE/'2026-10-15-oaf-drums-comparison-01'
ADTOF = BASE/'2026-10-13/reference-adtof'
REPO = Path(__file__).resolve().parents[2]


def read(p):
    return json.loads(Path(p).read_text(encoding='utf8'))


def enst_events(path, mapping):
    pitch_family = {35:'KD',36:'KD',37:'OT',38:'SD',41:'TT',42:'HH',45:'TT',46:'HH',47:'TT',48:'TT',49:'CY',51:'CY',52:'CY',55:'CY',56:'OT',57:'CY',59:'CY',75:'OT'}
    events=[]
    for line in Path(path).read_text(encoding='utf8').splitlines():
        t,label=line.split(); t=float(t)
        if not np.isfinite(t) or t<0: raise ValueError('Invalid ENST time')
        events.append({'time_seconds':t,'family':pitch_family.get(mapping.get(label),'OT'),'source_label':label})
    return events


def idmt_events(path):
    doc=ET.parse(path).getroot(); events=[]
    for e in doc.findall('./transcription/event'):
        t=float(e.findtext('onsetSec')); f=e.findtext('instrument')
        if f not in ['KD','SD','HH'] or not np.isfinite(t) or t<0: raise ValueError('Invalid IDMT event')
        events.append({'time_seconds':t,'family':f,'source_label':f})
    return events,doc.findtext('./globalParameter/audioFileName')


def mix_enst(wet, accompaniment):
    if wet.shape != accompaniment.shape or wet.ndim!=2 or wet.shape[1]!=2:
        raise ValueError('Aligned stereo source shapes required')
    if not np.isfinite(wet).all() or not np.isfinite(accompaniment).all():
        raise ValueError('Nonfinite source audio')
    return np.float32(.5)*(wet+accompaniment)


def idmt_crosscheck(events, copies, sr):
    checks={}
    for f in ['KD','SD','HH']:
        doc=ET.parse(copies['svl_'+f]).getroot();rate=int(doc.find('./data/model').get('sampleRate'))
        svl=sorted(int(p.get('frame'))/rate for p in doc.findall('./data/dataset/point'))
        xml=sorted(e['time_seconds'] for e in events if e['family']==f)
        error=max((abs(a-b) for a,b in zip(svl,xml)),default=0)
        checks[f]={'xml_count':len(xml),'svl_count':len(svl),'sample_rate':rate,
                   'common_prefix_max_difference_seconds':error,
                   'passes':len(svl)==len(xml) and rate==sr and error<=.0001,
                   'xml_trailing_events':xml[len(svl):]}
    return checks


def prepare(root, inputs_name='inputs'):
    root=scoped_root(root); selection=read(root/'selection.json')
    verify(read(root/'evidence/prior-preservation.json')['files'])
    if Path(inputs_name).name!=inputs_name or not inputs_name.startswith('inputs'):
        raise ValueError('Use a new inputs folder name')
    out=root/inputs_name;out.mkdir(exist_ok=False)
    source=root/'primary/adtof-instrumentsMapping.py'
    node=next(n for n in ast.parse(source.read_text(encoding='utf8')).body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='ENST_MIDI' for t in n.targets))
    mapping=ast.literal_eval(node.value)
    from audit_clone_hero_reference import attack_envelope,attack_profile
    rows=[]; protected=[]
    for original in selection['tracks']:
        row=deepcopy(original);folder=out/row['id'];folder.mkdir();(folder/'original').mkdir()
        row['source_copies']={}
        for role,p in row['sources'].items():
            p=Path(p);h=sha256(p); (folder/'original'/role).mkdir(); dest=folder/'original'/role/p.name
            if dest.exists(): raise FileExistsError(dest)
            shutil.copy2(p,dest);assert sha256(dest)==h
            protected.extend([{'path':str(p),'sha256':h},{'path':str(dest),'sha256':h}]);row['source_copies'][role]=str(dest)
        copies=row['source_copies'];alignment=[]
        if row['dataset']=='ENST':
            wet,sr=sf.read(copies['wet'],dtype='float32',always_2d=True)
            acc,ar=sf.read(copies['accompaniment'],dtype='float32',always_2d=True)
            assert sr==ar==44100
            mixed=mix_enst(wet,acc);events=enst_events(copies['annotation'],mapping)
            mic,mr=sf.read(copies['snare_mic'],dtype='float32',always_2d=True)
            assert mr==sr and len(mic)==len(mixed)
            et,ev=attack_envelope(mic,sr);sd=[e['time_seconds'] for e in events if e['family']=='SD']
            duration=len(mixed)/sr
            for i in range(3):
                anchors=[t for t in sd if i*duration/3<=t<(i+1)*duration/3]
                alignment.append({'third':i+1,'anchor_count':len(anchors),**(attack_profile(et,ev,anchors) if len(anchors)>=5 else {'status':'too_few_anchors'})})
            peaks=[w.get('peak_lag_ms') for w in alignment]
            quarantine=all(p is not None for p in peaks) and (all(p>25 for p in peaks) or all(p< -25 for p in peaks))
            row['annotation_crosscheck']={'unknown_source_labels':sorted({e['source_label'] for e in events if e['source_label'] not in mapping}), 'clock':'Published seconds retained without shift; original snare mic attack screen is supporting evidence, not label proof.'}
        else:
            mixed,sr=sf.read(copies['mix'],dtype='float32',always_2d=True)
            assert sr==44100 and mixed.shape[1]==1
            mixed=np.repeat(mixed,2,axis=1)
            events,declared=idmt_events(copies['annotation'])
            checks=idmt_crosscheck(events,copies,sr)
            checks['filename']={'declared':declared,'actual':Path(copies['mix']).name,
                                'passes':declared==Path(copies['mix']).name}
            row['annotation_crosscheck']=checks;quarantine=not all(c['passes'] for c in checks.values())
        assert len(mixed)>0 and np.isfinite(mixed).all()
        assert all(e['time_seconds']<len(mixed)/sr for e in events)
        row.update(duration_seconds=len(mixed)/sr,sample_rate=sr,reference_counts=dict(Counter(e['family'] for e in events)),reference_events=len(events),admitted=not quarantine)
        row['alignment']=alignment
        row['mix']=str(folder/'mix.wav');sf.write(row['mix'],mixed,sr,subtype='FLOAT')
        reread,rate=sf.read(row['mix'],dtype='float32',always_2d=True);assert rate==sr and np.array_equal(reread,mixed)
        row['annotation']=str(folder/'reference.txt')
        with Path(row['annotation']).open('x',encoding='utf8') as f:
            for e in sorted(events,key=lambda e:e['time_seconds']):f.write(f"{e['time_seconds']:.12f} {e['family']}\n")
        save(folder/'reference-events.json',events);save(folder/'admission.json',row)
        for p in [Path(row['mix']),Path(row['annotation']),folder/'reference-events.json',folder/'admission.json']:
            protected.append({'path':str(p),'sha256':sha256(p)})
        rows.append(row)
        print(json.dumps({'admission':row['id'],'admitted':row['admitted'],'seconds':row['duration_seconds'],'counts':row['reference_counts'],'third_peak_lags':[w.get('peak_lag_ms') for w in alignment]}),flush=True)
    old=read(OAF/'protocol.json')
    paths=[root/'selection.json',Path(__file__),Path(__file__).with_name('test_snare_validation.py')]
    paths += [p for p in (root/'primary').iterdir() if p.is_file()]
    paths += [REPO/'tools/recovery'/n for n in ['compare_snare_addition.py','compare_oaf_drums.py','compare_adt_str.py','oaf_runtime.py','frontend_adtof_reference.py','decode_adtof_reference.py','model_adtof_reference.py','score_timing.py','evaluate_mdb.py','probe_residual_input.py','audit_clone_hero_reference.py']]
    paths += [REPO/'ai-pipeline/separation/demucs_separator.py']
    paths += list((Path('C:/Users/10ros/.cache/torch/hub/checkpoints')).glob('*.th'))
    paths += [p for p in (ADTOF/'src/adtof_pytorch').rglob('*') if p.is_file() and p.suffix in {'.py','.pth'}]
    protected += [{'path':str(p),'sha256':sha256(p)} for p in paths]
    protected += [e for e in old['protected'] if str(OAF/'source') in e['path'] or str(OAF/'checkpoint') in e['path']]
    unique={e['path']:e['sha256'] for e in protected}
    protocol={'utc':datetime.now(timezone.utc).isoformat(),'selection_sha256':sha256(root/'selection.json'),'rule':RULE,'tracks':rows,'gate_50ms':selection['gate_50ms'],
        'decision':selection['decision'],'overlap':selection['overlap'],
        'input':'Prepared stereo at44.1kHz, normalize both channels by mono peak, seed0 htdemucs_ft default shifts/segment and overlap.25, mean drum output to mono. ADTOF source-conformant frontend/pooling/decoder and native OaF unchanged.',
        'settings':{'torch_threads':2,'torch_seed':0,'device_separation':'cuda','device_transcription':'cpu','ADTOF_USE_KERAS_GRU':'0','oaf_hparams':old['hparams']},
        'protected':[{'path':p,'sha256':h} for p,h in sorted(unique.items())]}
    save(root/'protocol.json',protocol);print(json.dumps({'protocol_entries':len(unique),'admitted':sum(r['admitted'] for r in rows)}))


def checked(root):
    root=scoped_root(root);p=read(root/'protocol.json');verify(p['protected']);assert p['rule']==RULE
    return p


def separate_adtof(root):
    protocol=checked(root);out=root/'adtof';out.mkdir(exist_ok=False)
    save(out/'started.json',{'utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha256(root/'protocol.json')})
    import os
    assert os.environ.get('ADTOF_USE_KERAS_GRU','0')=='0'
    import torch
    from frontend_adtof_reference import features
    from decode_adtof_reference import decode_activations
    from model_adtof_reference import replace_pooling
    from transcribe_reference import reference_preflight
    sys.path.insert(0,str(REPO/'ai-pipeline'));sys.path.insert(0,str(ADTOF/'src'))
    from adtof_pytorch import create_frame_rnn_model,load_pytorch_weights
    from separation.demucs_separator import separate_drums
    # Refuse network fallback. Existing checkpoint files were frozen above.
    torch.hub.download_url_to_file=lambda *a,**k: (_ for _ in ()).throw(RuntimeError('Unexpected model download prohibited'))
    torch.set_num_threads(2);torch.manual_seed(0)
    model=replace_pooling(load_pytorch_weights(create_frame_rnn_model(84),str(reference_preflight(ADTOF)),strict=True)).eval()
    rows=[]
    for spec in protocol['tracks']:
        if not spec['admitted']:continue
        start=time.perf_counter();folder=out/spec['id'];folder.mkdir()
        audio,sr=sf.read(spec['mix'],dtype='float32',always_2d=True);y=audio.T.copy()
        peak=float(np.abs(np.mean(y,axis=0)).max());assert peak>1e-10;y=y/peak
        random.seed(0);np.random.seed(0);torch.manual_seed(0)
        stem,rate=separate_drums((y,sr),model_name='htdemucs_ft')
        assert rate==44100 and stem.shape==(len(audio),) and np.isfinite(stem).all()
        sf.write(folder/'drums.wav',stem,rate,subtype='FLOAT')
        x=features(stem);np.save(folder/'features.npy',x)
        with torch.no_grad():act=model(torch.from_numpy(x).unsqueeze(0)).cpu().numpy()
        assert np.isfinite(act).all();np.save(folder/'activations.npy',act)
        chart=decode_activations(act);save(folder/'predictions.json',chart)
        row={'id':spec['id'],'prediction_sha256':sha256(folder/'predictions.json'),'stem_sha256':sha256(folder/'drums.wav'),'feature_sha256':sha256(folder/'features.npy'),'activation_sha256':sha256(folder/'activations.npy'),'seconds':time.perf_counter()-start,'mono_peak_divisor':peak,'notes':len(chart['hitObjects'])}
        save(folder/'run.json',row);rows.append(row);print(json.dumps(row),flush=True)
    verify(protocol['protected']);save(out/'completed.json',{'protocol_sha256':sha256(root/'protocol.json'),'tracks':rows})


def oaf(root):
    protocol=checked(root);baseline=read(root/'adtof/completed.json')
    assert baseline['protocol_sha256']==sha256(root/'protocol.json')
    from oaf_runtime import load
    from compare_oaf_drums import notes_to_chart
    tf,configs,data,model,infer=load(OAF)
    from magenta.models.onsets_frames_transcription import audio_label_data_utils,constants
    from note_seq.protobuf import music_pb2
    hp=configs.CONFIG_MAP['drums'].hparams;hp.batch_size=1;hp.truncated_length_secs=0
    assert hp.values()==protocol['settings']['oaf_hparams']
    out=root/'oaf';out.mkdir(exist_ok=False)
    save(out/'started.json',{'utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha256(root/'protocol.json')})
    rows=[];np.random.seed(0)
    with tf.Graph().as_default():
        tf.set_random_seed(0);examples=tf.placeholder(tf.string,[None])
        dataset=data.provide_batch(examples,True,hp,False,False,0)
        iterator=tf.data.make_initializable_iterator(dataset);next_record=iterator.get_next()
        spec=tf.placeholder(tf.float32,[1,None,hp.spec_n_bins,1]);length=tf.placeholder(tf.int32,[1])
        outputs=model.build_model(spec,length,hp,False);probs_op=tf.sigmoid(outputs[1]);velocities_op=outputs[3]
        checkpoint=str(OAF/'checkpoint/model.ckpt-569400');variables=tf.global_variables();saver=tf.train.Saver()
        with tf.Session(config=tf.ConfigProto(intra_op_parallelism_threads=2,inter_op_parallelism_threads=1)) as sess:
            saver.restore(sess,checkpoint)
            assert all(np.array_equal(sess.run(v),tf.train.load_variable(checkpoint,v.name[:-2])) for v in variables)
            save(out/'model-load.json',{'variables_restored_exactly':len(variables)})
            for row in baseline['tracks']:
                start=time.perf_counter();folder=out/row['id'];folder.mkdir()
                stem=root/'adtof'/row['id']/'drums.wav';assert sha256(stem)==row['stem_sha256']
                record=list(audio_label_data_utils.process_record(wav_data=stem.read_bytes(),sample_rate=hp.sample_rate,ns=music_pb2.NoteSequence(),example_id=row['id'],min_length=0,max_length=-1,allow_empty_notesequence=True,load_audio_with_librosa=False))
                assert len(record)==1;example=record[0];raw=example.SerializeToString();(folder/'native-example.pb').write_bytes(raw)
                audio=example.features.feature['audio'].bytes_list.value[0];(folder/'native-normalized-pcm16.wav').write_bytes(audio)
                sess.run(iterator.initializer,{examples:[raw]});features,_=sess.run(next_record)
                np.save(folder/'native-features.npy',features.spec)
                nframes=int(data.wav_to_num_frames(audio,data.hparams_frames_per_second(hp)))
                assert features.length.tolist()==[nframes] and np.array_equal(features.spec[0,:,:,0],data.wav_to_spec(audio,hp)[:nframes])
                probs,velocities=sess.run([probs_op,velocities_op],{spec:features.spec,length:features.length})
                assert np.isfinite(probs).all() and np.isfinite(velocities).all()
                np.savez_compressed(folder/'native-outputs.npz',onset_probs=probs[0],velocity_values=velocities[0])
                onsets=probs[0]>hp.predict_onset_threshold
                seq=infer.predict_sequence(probs[0],probs[0],onsets,onsets,onsets,velocities[0],constants.MIN_MIDI_PITCH,hp,onsets_only=True)
                (folder/'native-sequence.pb').write_bytes(seq.SerializeToString())
                notes=np.array([[n.start_time,n.end_time,n.pitch,n.velocity] for n in seq.notes]).reshape(-1,4);np.save(folder/'native-notes.npy',notes)
                fi,pi=np.nonzero(onsets);assert len(notes)==len(fi) and np.array_equal(notes[:,2],pi+21)
                assert np.allclose(notes[:,0],fi*512/44100,atol=1e-12,rtol=0)
                chart=notes_to_chart(notes);save(folder/'predictions.json',chart)
                result={'id':row['id'],'prediction_sha256':sha256(folder/'predictions.json'),'native_notes':len(notes),'frames':nframes,'seconds':time.perf_counter()-start}
                rows.append(result);save(folder/'run.json',result);print(json.dumps(result),flush=True)
    verify(protocol['protected']);save(out/'completed.json',{'protocol_sha256':sha256(root/'protocol.json'),'tracks':rows})


def score(root):
    protocol=checked(root);a=read(root/'adtof/completed.json');b=read(root/'oaf/completed.json')
    assert a['protocol_sha256']==b['protocol_sha256']==sha256(root/'protocol.json')
    out=root/'comparison';out.mkdir(exist_ok=False);rows=[];additions=[]
    for spec in protocol['tracks']:
        if not spec['admitted']:continue
        folder=out/spec['id'];folder.mkdir();ar=next(r for r in a['tracks'] if r['id']==spec['id']);br=next(r for r in b['tracks'] if r['id']==spec['id'])
        ap=root/'adtof'/spec['id']/'predictions.json';bp=root/'oaf'/spec['id']/'predictions.json'
        assert sha256(ap)==ar['prediction_sha256'] and sha256(bp)==br['prediction_sha256']
        baseline,native=read(ap),read(bp);candidate,decisions=add_snares(baseline,native)
        save(folder/'predictions.json',candidate);save(folder/'decisions.json',decisions)
        truth=truth_from(Path(spec['annotation']));scores={};assignments={}
        for ms in ['25','50']:
            scores[ms]={arm:evaluate_timing(chart,truth,int(ms)/1000) for arm,chart in [('baseline',baseline),('candidate',candidate)]}
            assignments[ms]={arm:event_assignments(chart,truth,int(ms)/1000) for arm,chart in [('baseline',baseline),('candidate',candidate)]}
            save(folder/f'events-{ms}ms.json',assignments[ms])
        adds=audit_additions(baseline,native,decisions,truth,assignments,root/'oaf'/spec['id']/'native-outputs.npz')
        save(folder/'additions.json',adds);additions.extend(dict(x,track=spec['id']) for x in adds)
        row={'track':spec['id'],'dataset':spec['dataset'],'duration_seconds':spec['duration_seconds'],'annotation':spec['annotation'],'scores':scores,'decisions':dict(Counter(d['decision'] for d in decisions)),'prediction_sha256':sha256(folder/'predictions.json')}
        rows.append(row);save(folder/'metrics.json',row);print(json.dumps({'track':spec['id'],'baseline50':scores['50']['baseline']['micro'],'candidate50':scores['50']['candidate']['micro'],'decisions':row['decisions']}),flush=True)
    strata={}
    for dataset in ['ENST','IDMT','all']:
        selected=[r for r in rows if dataset=='all' or r['dataset']==dataset]
        if not selected:
            strata[dataset]={'tracks':0,'status':'No admitted recordings; not scored','pooled':None,'decision':None}
            continue
        pooled={ms:{arm:pool(selected,arm,ms) for arm in ['baseline','candidate']} for ms in ['25','50']}
        decision=acceptance(pooled['50']['baseline'],pooled['50']['candidate'],[r['scores']['50']['candidate']['micro']['f1']-r['scores']['50']['baseline']['micro']['f1'] for r in selected])
        strata[dataset]={'tracks':len(selected),'pooled':pooled,'decision':decision}
    summaries={ms:{'added':len(additions),'matched':sum(x['matches'][ms] is not None for x in additions),'false':sum(x['matches'][ms] is None for x in additions),'timing':timing_summary([x['matches'][ms]['signed_error_ms']/1000 for x in additions if x['matches'][ms]])} for ms in ['25','50']}
    save(out/'metrics.json',{'status':'complete','protocol_sha256':sha256(root/'protocol.json'),'tracks':rows,'strata':strata,'primary_decision':strata['ENST']['decision'],'additions':summaries})
    save(root/'evidence/false-additions.json',{'events':[x for x in additions if x['matches']['50'] is None],'scope':'All additions unmatched to source annotations at50ms; not auditory proof.'})
    verify(protocol['protected']);print(json.dumps({'strata':{k:({'baseline':v['pooled']['50']['baseline']['micro'],'candidate':v['pooled']['50']['candidate']['micro'],'decision':v['decision']} if v['pooled'] else v) for k,v in strata.items()},'additions':summaries}),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','separate_adtof','oaf','score']);p.add_argument('--root',type=Path,required=True);p.add_argument('--inputs-name',default='inputs')
    args=p.parse_args()
    if args.action=='prepare':prepare(scoped_root(args.root),args.inputs_name)
    else:globals()[args.action](scoped_root(args.root))
