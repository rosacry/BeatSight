"""Compare actual original checkpoint tensors and fixed-feature outputs."""
import argparse
from contextlib import redirect_stdout
import copy
import json
from pathlib import Path
import sys

import numpy as np
import torch

from audit_adtof_frontend import REFERENCE
from audit_adtof_model import diff
from decode_adtof_reference import decode_activations
from model_adtof_reference import replace_pooling
from probe_residual_input import truth_from
from score_timing import evaluate_timing
from transcribe import sha256
from transcribe_reference import reference_preflight, write_json


def main(root):
    out=root/'original-parity'
    if (out/'comparison.json').exists():raise ValueError('Do not replace completed parity evidence')
    protocol=json.loads((out/'protocol.json').read_text())
    complete=json.loads((out/'tf-complete.json').read_text())
    assert complete['status']=='complete' and complete['protocol_sha256']==sha256(out/'protocol.json')
    for row in protocol['protected']:
        if sha256(Path(row['path']))!=row['sha256']:raise ValueError('Frozen source/input changed')
    weights_path=reference_preflight(REFERENCE)
    converted=torch.load(weights_path,map_location='cpu',weights_only=True)['model_weights']
    original=np.load(out/'original-weights-in-port-layout.npz')
    if set(converted)!=set(original.files):raise ValueError('Weight names differ')
    weight_rows=[{'name':name,'exact':bool(np.array_equal(converted[name].numpy(),original[name])),
                  'comparison':diff(converted[name].numpy(),original[name])} for name in original.files]
    sys.path.insert(0,str(REFERENCE/'src'))
    from adtof_pytorch import create_frame_rnn_model,load_pytorch_weights
    torch.set_num_threads(2);torch.manual_seed(0)
    with (out/'comparison-load.log').open('x') as log,redirect_stdout(log):
        port=load_pytorch_weights(create_frame_rnn_model(84),str(weights_path),strict=True).eval()
    corrected=replace_pooling(copy.deepcopy(port)).eval()
    def stages(model,x):
        result={};y=x.permute(0,3,1,2)
        for b,block in enumerate(model.cnn_blocks):
            for i,layer in enumerate(block):
                y=layer(y)
                # Original Conv2D includes ReLU; align equivalent boundaries.
                mapping={1:0,2:1,4:2,5:3,6:4}
                if i in mapping:result[f'cnn_{b}_{mapping[i]}']=y.permute(0,2,3,1).numpy()
        y=y.permute(0,2,3,1).reshape(x.shape[0],x.shape[1],640);result['reshape']=y.numpy()
        for i,layer in enumerate(model.gru_layers):
            y,_=layer(y);result[f'gru_{i}']=y.numpy()
        result['output']=torch.sigmoid(model.output_layer(y)).numpy()
        return result
    clips=[]
    with torch.no_grad():
        for row in protocol['clips']:
            x=torch.from_numpy(np.load(row['path']))
            tf=np.load(out/'tf'/f"clip-{row['index']:02d}.npz")
            systems={arm:stages(model,x) for arm,model in [('port',port),('corrected_pool',corrected)]}
            clips.append({'index':row['index'],'track':row['track'],'source':row['source'],'role':row['role'],
                'comparisons':{arm:{key:diff(values[key],tf[key]) for key in tf.files} for arm,values in systems.items()}})
    recordings=[]
    for row in protocol['recordings']:
        original_act=np.load(out/'tf'/f"{row['track']}.npy");candidate=np.load(row['candidate_activation'])
        tf_chart=decode_activations(original_act);pt_chart=decode_activations(candidate)
        truth=truth_from(Path(row['annotation']))
        recordings.append({'track':row['track'],'activations':diff(candidate,original_act),
            'decoded_chart_exact':tf_chart==pt_chart,'events':len(tf_chart['hitObjects']),
            'original_activation_sha256':sha256(out/'tf'/f"{row['track']}.npy"),
            'original_scores':{ms:evaluate_timing(tf_chart,truth,int(ms)/1000) for ms in ['25','50']}})
        write_json(out/'tf'/f"{row['track']}.predictions.json",tf_chart)
    result={'protocol_sha256':sha256(out/'protocol.json'),'weight_tensors':weight_rows,
        'all_weight_tensors_exact':all(r['exact'] for r in weight_rows),'clips':clips,'recordings':recordings,
        'all_corrected_clip_stages_close':all(v['close'] for c in clips for v in c['comparisons']['corrected_pool'].values()),
        'all_corrected_recordings_close':all(r['activations']['close'] for r in recordings),
        'all_recording_charts_exact':all(r['decoded_chart_exact'] for r in recordings),
        'max_clip_output_difference':{arm:max(c['comparisons'][arm]['output']['max_abs'] for c in clips) for arm in ['port','corrected_pool']},
        'max_recording_output_difference':max(r['activations']['max_abs'] for r in recordings),
        'scope':'Actual original published checkpoint and original model-building method, TF/Keras2.13.1 CPU versus pinned PT with pool correction, on identical fixed externally-prepared features. Complete original audio file loader/preprocessing not exercised.'}
    write_json(out/'comparison.json',result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['weight_tensors','clips','recordings']}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
