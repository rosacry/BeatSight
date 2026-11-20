"""Run reviewed primary model construction in the isolated TensorFlow runtime.

Input features are prepared by the regular recovery environment and hash checked.
No full ADTOF module or preprocessing import is performed in this environment.
"""
import argparse
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path

os.environ['TF_ENABLE_ONEDNN_OPTS']='0'
os.environ['TF_CPP_MIN_LOG_LEVEL']='2'
os.environ['CUDA_VISIBLE_DEVICES']='-1'
import numpy as np
import tensorflow as tf


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def save(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,allow_nan=False)


def main(root):
    out=root/'original-parity';protocol=json.loads((out/'protocol.json').read_text())
    for row in protocol['protected']:
        if sha(row['path'])!=row['sha256']:raise ValueError('Frozen source/input changed')
    save(out/'tf-run-started.json',{'utc':datetime.now(timezone.utc).isoformat()})
    tf.config.threading.set_intra_op_parallelism_threads(2)
    tf.config.threading.set_inter_op_parallelism_threads(1)
    tf.random.set_seed(0);np.random.seed(0)
    source=root/'primary/adtof-model.py'
    cls=next(n for n in ast.parse(source.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='Model')
    method=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name=='_getCRNNFunctional')
    scope={'tf':tf}
    exec(compile(ast.Module(body=[method],type_ignores=[]),str(source),'exec'),scope)
    model=scope['_getCRNNFunctional'](None,context=9,n_bins=84,output=5,n_channels=1,
        conv_Filter=[32,64],GRU_units=[60,60,60],samePadding=True,lambdaRegularizer=None)
    status=model.load_weights(str(root/'original-checkpoint/Frame_RNN_adtofAll_0'))
    status.assert_existing_objects_matched()
    status.expect_partial()  # Optimizer state is outside inference, not missing model variables.
    save(out/'tf-model.json',{'tensorflow':tf.__version__,'numpy':np.__version__,
        'model_config':json.loads(model.to_json()),'weight_shapes':[list(w.shape) for w in model.get_weights()],
        'checkpoint_existing_objects_matched':True,
        'checkpoint_variables':[(n,list(s)) for n,s in tf.train.list_variables(str(root/'original-checkpoint/Frame_RNN_adtofAll_0'))]})
    # Direct, documented Keras -> PyTorch layout/gate mapping; keep both biases.
    weights={};cnn=model.layers[1]
    for i in range(2):
        for source_index,target_index in [(0,0),(2,3)]:
            kernel,bias=cnn.layers[i*6+source_index].get_weights()
            weights[f'cnn_blocks.{i}.{target_index}.weight']=kernel.transpose(3,2,0,1)
            weights[f'cnn_blocks.{i}.{target_index}.bias']=bias
        for source_index,target_index in [(1,2),(3,5)]:
            values=cnn.layers[i*6+source_index].get_weights()
            for key,value in zip(['weight','bias','running_mean','running_var'],values):
                weights[f'cnn_blocks.{i}.{target_index}.{key}']=value
    for i,layer in enumerate(model.layers[3:6]):
        for rev,direction in [(False,layer.forward_layer),(True,layer.backward_layer)]:
            kernel,recurrent,bias=direction.get_weights()
            if bias.shape!=(2,180):raise ValueError('Unexpected GRU bias configuration')
            indices=np.r_[60:120,0:60,120:180]
            suffix='_reverse' if rev else ''
            for key,value in [('weight_ih',kernel[:,indices].T),('weight_hh',recurrent[:,indices].T),
                              ('bias_ih',bias[0,indices]),('bias_hh',bias[1,indices])]:
                weights[f'gru_layers.{i}.{key}_l0{suffix}']=value
    kernel,bias=model.layers[-1].get_weights()
    weights['output_layer.weight']=kernel.T;weights['output_layer.bias']=bias
    np.savez(out/'original-weights-in-port-layout.npz',**weights)
    def stages(x):
        result={};y=x
        for b in range(2):
            for j in range(6):
                y=cnn.layers[b*6+j](y,training=False)
                if j<5:result[f'cnn_{b}_{j}']=y.numpy()
        y=model.layers[2](y);result['reshape']=y.numpy()
        for i,layer in enumerate(model.layers[3:6]):
            y=layer(y,training=False);result[f'gru_{i}']=y.numpy()
        result['output']=model.layers[-1](y).numpy()
        np.testing.assert_allclose(result['output'],model(x,training=False).numpy(),atol=1e-6,rtol=1e-6)
        return result
    folder=out/'tf';folder.mkdir()
    for row in protocol['clips']:
        x=np.load(row['path']);np.savez(folder/f"clip-{row['index']:02d}.npz",**stages(x))
    full=tf.function(lambda x:model(x,training=False),input_signature=[tf.TensorSpec([1,None,84,1],tf.float32)])
    for row in protocol['recordings']:
        act=full(np.load(row['path'])).numpy();np.save(folder/f"{row['track']}.npy",act)
        print(json.dumps({'original_model_completed':row['track'],'shape':list(act.shape)}),flush=True)
    save(out/'tf-complete.json',{'status':'complete','clips':len(protocol['clips']),
        'recordings':len(protocol['recordings']),'weight_tensors':len(weights),
        'protocol_sha256':sha(out/'protocol.json')})


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--root',type=Path,required=True)
    main(parser.parse_args().root)
