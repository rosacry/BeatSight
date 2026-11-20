"""Known counterexamples distinguish primary decoder semantics from the port."""
import numpy as np
import pytest

from decode_adtof_reference import decode_activations, pick_reference


def test_nearby_events_keep_the_earliest_not_the_strongest():
    values = np.zeros(40, dtype=np.float32)
    values[10], values[12] = .6, .9
    assert pick_reference(values,.22) == [.1]


def test_zero_boundary_padding_and_separate_family_events():
    values = np.zeros((20,5),dtype=np.float32)
    values[0,0] = .6
    values[10,1] = .7
    values[10,2] = .8
    chart = decode_activations(values)
    assert chart['hitObjects'] == [{'time':0.,'component':'kick'},
                                  {'time':100.,'component':'snare'},
                                  {'time':100.,'component':'tom'}]
    assert decode_activations(values[None]) == chart


def test_invalid_batch_nonfinite_and_silence():
    assert decode_activations(np.zeros((20,5))) == {'hitObjects':[]}
    assert pick_reference(np.array([]),.22) == []
    with pytest.raises(ValueError): decode_activations(np.zeros((2,20,5)))
    with pytest.raises(ValueError): decode_activations(np.full((20,5),np.nan))
    with pytest.raises(ValueError): pick_reference(np.zeros(20),0)
