"""Bounded source-semantic checks; does not claim original-checkpoint parity."""
import argparse
import ast
from contextlib import redirect_stdout
import copy
from datetime import datetime, timezone
import io
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np
from scipy.special import expit
import soundfile as sf
import torch

from audit_adtof_frontend import REFERENCE
from frontend_adtof_reference import features
from model_adtof_reference import ReferenceWidthMaxPool, replace_pooling
from transcribe import sha256
from transcribe_reference import reference_preflight, write_json

FRONTEND = REFERENCE.parents[1]/'2026-10-15-adtof-frontend-audit-01'


def pool_numpy(x):
    """Independent valid-window max, NHWC input, SAME width/stride 3."""
    width=x.shape[2]; count=(width+2)//3
    left=max(0,(count-1)*3+3-width)//2
    return np.stack([x[:,:,max(0,i*3-left):min(width,i*3-left+3),:].max(axis=2)
                     for i in range(count)],axis=2)


def primary_gru_call(primary):
    manifest=json.loads((primary/'sources-2.13.json').read_text())
    row=next(r for r in manifest['files'] if Path(r['path']).name=='keras-2.13.1-gru.py')
    source=primary/'keras-2.13.1-gru.py'
    if sha256(source)!=row['sha256']:raise ValueError('Primary GRU source changed')
    cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='GRUCell')
    node=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='call')
    def split(a,sizes,axis=-1):
        return np.split(a,sizes if isinstance(sizes,int) else np.cumsum(sizes[:-1]),axis=axis)
    scope={'tf':SimpleNamespace(nest=SimpleNamespace(is_nested=lambda x:isinstance(x,(list,tuple))),
                                unstack=lambda a:list(a),split=split),
           'backend':SimpleNamespace(dot=np.dot,bias_add=lambda a,b:a+b)}
    exec(compile(ast.Module(body=[node],type_ignores=[]),str(source),'exec'),scope)
    return scope['call']


def gru_primary_sequence(call, layer, x, reverse=False):
    suffix='_reverse' if reverse else ''
    h=layer.hidden_size
    def keras_order(value):
        a=value.detach().cpu().numpy().astype(np.float64)
        return np.concatenate([a[h:2*h],a[:h],a[2*h:]],axis=0)
    cell=SimpleNamespace(units=h,reset_after=True,use_bias=True,implementation=2,
        dropout=0.,recurrent_dropout=0.,activation=np.tanh,recurrent_activation=expit,
        get_dropout_mask_for_cell=lambda *a,**k:None,
        get_recurrent_dropout_mask_for_cell=lambda *a,**k:None,
        kernel=keras_order(getattr(layer,'weight_ih_l0'+suffix)).T,
        recurrent_kernel=keras_order(getattr(layer,'weight_hh_l0'+suffix)).T,
        bias=np.stack([keras_order(getattr(layer,'bias_ih_l0'+suffix)),
                       keras_order(getattr(layer,'bias_hh_l0'+suffix))]))
    state=np.zeros((x.shape[0],h));output=np.empty((x.shape[0],x.shape[1],h))
    for i in (range(x.shape[1]-1,-1,-1) if reverse else range(x.shape[1])):
        state,_=call(cell,x[:,i].astype(np.float64),[state],training=False)
        output[:,i]=state
    return output


def diff(actual,expected):
    a=np.asarray(actual); b=np.asarray(expected)
    d=np.abs(a.astype(float)-b.astype(float))
    return {'max_abs':float(d.max()),'mae':float(d.mean()),
            'close':bool(np.allclose(a,b,atol=1e-5,rtol=1e-4)),
            'different_values':int(np.count_nonzero(a!=b))}


def prepare(root):
    if root.resolve().drive.upper()!='C:':raise ValueError('Use a scoped C: root')
    weights=reference_preflight(REFERENCE)
    selection=json.loads((FRONTEND/'protocol.json').read_text())
    protected=[Path(r['path']) for r in selection['protected'] if r['path'].endswith('.wav')]
    protected += [weights,REFERENCE/'src/adtof_pytorch/model.py',REFERENCE/'dev/convert_weights.py',
                  FRONTEND/'protocol.json',Path(__file__),Path(__file__).with_name('model_adtof_reference.py'),
                  Path(__file__).with_name('frontend_adtof_reference.py')]
    protected += [p for p in (root/'primary').iterdir() if p.is_file()]
    protocol={'utc':datetime.now(timezone.utc).isoformat(),
        'boundary':'Reviewed Keras 2.13.1 GRUCell.call via NumPy shims; valid-window max pooling; numpy conv/BN equations. No TensorFlow runtime or original checkpoint available in inventoried scopes.',
        'selection':'Same 16 previously frozen mix/stem excerpts; features frames 168:232, first nine frames for convolution/BN local checks, first 16 recurrent frames for primary-equation checks.',
        'numeric_gate':{'atol':1e-5,'rtol':1e-4},
        'synthetic':'Seed 0 pooling arrays of widths 1..100 including negative and nonnegative values; all-negative boundary counterexample; six GRU directions with seeded features and real layer inputs.',
        'conditional_followup':'Only if pooling mismatch reproduces on real features and valid-window replacement passes: one fixed seven-recording comparison with source-aligned frontend and primary decoder, pooling change only. Same frozen .01 F1/.01 precision/.02 track-loss/tom TP/snare recall gate. No GRU flag selection or bias edits.',
        'clips':selection['clips'],
        'protected':[{'path':str(p),'sha256':sha256(p)} for p in sorted(set(protected))]}
    with (root/'protocol.json').open('x') as f:json.dump(protocol,f,indent=2)
    print(json.dumps({'prepared':16,'protocol_sha256':sha256(root/'protocol.json')}))


def run(root):
    protocol=json.loads((root/'protocol.json').read_text())
    for row in protocol['protected']:
        if sha256(Path(row['path']))!=row['sha256']:raise ValueError('Frozen source/input changed')
    with (root/'audit-started.json').open('x') as f:json.dump({'protocol_sha256':sha256(root/'protocol.json')},f)
    sys.path.insert(0,str(REFERENCE/'src'))
    from adtof_pytorch.model import create_frame_rnn_model,load_pytorch_weights,SamePadWidthMaxPool,KerasGRUCell
    if os.environ.get('ADTOF_USE_KERAS_GRU','0')!='0':raise ValueError('Model environment changed')
    torch.set_num_threads(2);torch.manual_seed(0);rng=np.random.default_rng(0)
    with (root/'model-load.log').open('x') as log,redirect_stdout(log):
        model=load_pytorch_weights(create_frame_rnn_model(84),str(reference_preflight(REFERENCE)),strict=True).eval()
    candidate=replace_pooling(copy.deepcopy(model)).eval()
    call=primary_gru_call(root/'primary')
    synthetic=[]
    for width in range(1,101):
        for kind in ['negative','mixed','nonnegative']:
            a=rng.normal(size=(2,3,5,width)).astype(np.float32)
            if kind=='negative':a=-np.abs(a)-.1
            if kind=='nonnegative':a=np.abs(a)
            expected=pool_numpy(a.transpose(0,2,3,1))
            x=torch.from_numpy(a)
            synthetic.append({'width':width,'kind':kind,
                'port':diff(SamePadWidthMaxPool()(x).numpy().transpose(0,2,3,1),expected),
                'candidate':diff(ReferenceWidthMaxPool()(x).numpy().transpose(0,2,3,1),expected)})
    clips=[];gru_checks=[]
    with torch.no_grad():
        for index,c in enumerate(protocol['clips']):
            y,sr=sf.read(c['path'],start=c['start_sample'],frames=c['frames'],dtype='float32')
            if sr!=44100 or len(y)!=c['frames']:raise ValueError('Audio boundary differs')
            if y.ndim==2:y=y.mean(axis=1)
            feature=features(y)[168:232];x=torch.from_numpy(feature).unsqueeze(0)
            pre=x.permute(0,3,1,2);local=[];pools=[]
            for b,block in enumerate(model.cnn_blocks):
                for layer_index,layer in enumerate(block):
                    if layer_index in [0,3]:
                        # Use an independent channel-last numpy cross-correlation.
                        inp=pre[:,:,:9,:].numpy().transpose(0,2,3,1).astype(np.float64)
                        kernel=layer.weight.numpy().transpose(2,3,1,0).astype(np.float64)
                        pad=np.pad(inp,((0,0),(1,1),(1,1),(0,0)))
                        windows=np.lib.stride_tricks.sliding_window_view(pad,(3,3),axis=(1,2))
                        expected=np.einsum('btfcij,ijco->btfo',windows,kernel,optimize=True)+layer.bias.numpy()
                        actual=layer(pre[:,:,:9,:]).numpy().transpose(0,2,3,1)
                        local.append({'stage':f'{b}.{layer_index}.conv','comparison':diff(actual,expected)})
                    if layer_index in [2,5]:
                        inp=pre[:,:,:9,:].numpy().transpose(0,2,3,1).astype(np.float64)
                        expected=(inp-layer.running_mean.numpy())/np.sqrt(layer.running_var.numpy()+.001)*layer.weight.numpy()+layer.bias.numpy()
                        local.append({'stage':f'{b}.{layer_index}.bn','comparison':diff(layer(pre[:,:,:9,:]).numpy().transpose(0,2,3,1),expected)})
                    if layer_index==6:
                        expected=pool_numpy(pre.numpy().transpose(0,2,3,1))
                        pools.append({'block':b,'input_negative_values':int((pre<0).sum()),
                            'port':diff(layer(pre).numpy().transpose(0,2,3,1),expected),
                            'candidate':diff(ReferenceWidthMaxPool()(pre).numpy().transpose(0,2,3,1),expected)})
                    pre=layer(pre)
            recurrent=pre.permute(0,2,3,1).reshape(1,64,640)[:,:16]
            for i,layer in enumerate(model.gru_layers):
                actual,_=layer(recurrent)
                primary=np.concatenate([gru_primary_sequence(call,layer,recurrent.numpy(),rev) for rev in [False,True]],axis=-1)
                gru_checks.append({'clip':index,'layer':i,'comparison':diff(actual.numpy(),primary)})
                recurrent=actual
            clips.append({'clip':index,'track':c['track'],'source':c['source'],'role':c['role'],
                          'local_layers':local,'pooling':pools,
                          'final_activation_change':diff(candidate(x).numpy(),model(x).numpy())})
        synthetic_gru=[]
        for i,layer in enumerate(model.gru_layers):
            x=torch.from_numpy(rng.normal(0,.5,(2,19,layer.input_size)).astype(np.float32))
            actual,_=layer(x)
            primary=np.concatenate([gru_primary_sequence(call,layer,x.numpy(),rev) for rev in [False,True]],axis=-1)
            synthetic_gru.append({'layer':i,'comparison':diff(actual.numpy(),primary)})
    # Mathematical converter counterexample, independent of the bundled checkpoint.
    r=.5; separate=float(.5*np.tanh(r*1.));merged=float(.5*np.tanh(1.))
    recurrent_biases=[{'layer':i,'reverse':rev,'candidate_nonzero':int(getattr(layer,'bias_hh_l0'+('_reverse' if rev else ''))[120:].count_nonzero())}
                       for i,layer in enumerate(model.gru_layers) for rev in [False,True]]
    result={'protocol_sha256':sha256(root/'protocol.json'),'synthetic_pooling':synthetic,
        'clips':clips,'primary_gru_checks':gru_checks,'synthetic_gru_checks':synthetic_gru,
        'checkpoint_recurrent_candidate_biases':recurrent_biases,
        'converter_bias_counterexample':{'zero_input_state_and_kernels':True,'reset_and_update':.5,
            'recurrent_candidate_bias':1.,'separate_expected':separate,'merge_result':merged,
            'applies_to_bundled_checkpoint':'Not established; all six directions retain 60 nonzero candidate recurrent biases'},
        'candidate_pooling_passes':all(r['candidate']['close'] for r in synthetic) and all(p['candidate']['close'] for c in clips for p in c['pooling']),
        'real_pool_mismatch':any(not p['port']['close'] for c in clips for p in c['pooling']),
        'gru_equations_pass':all(r['comparison']['close'] for r in gru_checks+synthetic_gru),
        'local_conv_bn_pass':all(r['comparison']['close'] for c in clips for r in c['local_layers']),
        'context':'context 9 equals four 3x3 convolutions receptive field 9; both require no extra context concatenation. Flatten order is time/frequency/channel in both. Inference dropout disabled.',
        'limits':'Same converted weights re-expressed in primary Keras gate order. Cannot validate tensor provenance or faithful conversion from missing original weights. No TensorFlow kernel execution.'}
    write_json(root/'layer-audit.json',result)
    print(json.dumps({k:result[k] for k in ['candidate_pooling_passes','real_pool_mismatch','gru_equations_pass','local_conv_bn_pass']}))
    print(json.dumps({'real_pool_max':max(p['port']['max_abs'] for c in clips for p in c['pooling']),
        'final_activation_max':max(c['final_activation_change']['max_abs'] for c in clips),
        'gru_max':max(r['comparison']['max_abs'] for r in gru_checks+synthetic_gru)}))


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('action',choices=['prepare','run']);parser.add_argument('--root',type=Path,required=True)
    args=parser.parse_args();{'prepare':prepare,'run':run}[args.action](args.root)
