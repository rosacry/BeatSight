"""Signal-boundary checks for the fixed oracle input control."""
import numpy as np
import pytest
from control_enst_brush_input import original_component


def test_original_component_keeps_mixture_gain_and_sample_positions():
    wet=np.zeros((8,2),dtype=np.float32);wet[2,0]=.8;wet[5,1]=.4
    untouched=wet.copy();actual=original_component(wet,.25)
    expected=np.zeros(8,dtype=np.float32);expected[2]=.8;expected[5]=.4
    np.testing.assert_array_equal(actual,expected)
    np.testing.assert_array_equal(wet,untouched)
    assert actual.dtype==np.float32
    # No independent peak normalization: fixed gain changes absolute values.
    np.testing.assert_array_equal(original_component(wet,.5),actual/2)


def test_original_component_rejects_ambiguous_or_invalid_input():
    wet=np.ones((8,2),dtype=np.float32)
    for value in [0,-1,np.nan,np.inf]:
        with pytest.raises(ValueError):original_component(wet,value)
    for value in [wet.astype('float64'),wet[:,0],wet[:0],np.full_like(wet,np.nan)]:
        with pytest.raises(ValueError):original_component(value,.5)
