"""Boundary counterexamples and differential tests for model audit helpers."""
import os
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import torch
from scipy.special import expit

from audit_adtof_model import pool_numpy, primary_gru_call
from model_adtof_reference import ReferenceWidthMaxPool, replace_pooling


def test_negative_boundary_preserves_real_maximum():
    x=-torch.arange(1,29,dtype=torch.float32).reshape(1,1,1,28)
    expected=pool_numpy(x.numpy().transpose(0,2,3,1))
    output=ReferenceWidthMaxPool()(x).numpy().transpose(0,2,3,1)
    assert np.array_equal(output,expected)
    assert output[0,0,0,0]==-1 and output[0,0,-1,0]==-27
    zero_padded=torch.nn.functional.max_pool2d(torch.nn.functional.pad(x,(1,1)),(1,3),(1,3))
    assert zero_padded[0,0,0,0]==0 and zero_padded[0,0,0,-1]==0


def test_pooling_handles_all_remainders():
    rng=np.random.default_rng(27)
    for width in range(1,101):
        x=torch.from_numpy(rng.normal(size=(2,3,4,width)).astype(np.float32))
        expected=pool_numpy(x.numpy().transpose(0,2,3,1))
        assert np.array_equal(ReferenceWidthMaxPool()(x).numpy().transpose(0,2,3,1),expected)


def test_gru_candidate_bias_must_stay_inside_reset_gate():
    directory=os.environ.get('BEATSIGHT_MODEL_AUDIT_PRIMARY')
    if not directory:pytest.skip('Set BEATSIGHT_MODEL_AUDIT_PRIMARY to the saved primary source directory')
    call=primary_gru_call(Path(directory))
    cell=SimpleNamespace(units=1,reset_after=True,use_bias=True,implementation=2,
        dropout=0.,recurrent_dropout=0.,activation=np.tanh,recurrent_activation=expit,
        get_dropout_mask_for_cell=lambda *a,**k:None,
        get_recurrent_dropout_mask_for_cell=lambda *a,**k:None,
        kernel=np.zeros((1,3)),recurrent_kernel=np.zeros((1,3)),bias=np.array([[0.,0.,0.],[0.,0.,1.]]))
    correct,_=call(cell,np.zeros((1,1)),[np.zeros((1,1))],training=False)
    np.testing.assert_allclose(correct,.5*np.tanh(.5),atol=1e-14)
    cell.bias=np.array([[0.,0.,1.],[0.,0.,0.]])
    merged,_=call(cell,np.zeros((1,1)),[np.zeros((1,1))],training=False)
    assert abs(float(merged[0,0]-correct[0,0]))>.1


def test_unexpected_model_is_rejected_before_mutation():
    invalid=SimpleNamespace(cnn_blocks=[torch.nn.Sequential()])
    with pytest.raises(ValueError):replace_pooling(invalid)
