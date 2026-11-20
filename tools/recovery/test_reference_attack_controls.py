"""Protect the source-control logic, independent of any model output."""
import numpy as np
import pytest
import soundfile as sf

from probe_reference_attack_controls import reconstruct_parts, safe_profile, screen_decision
from transcribe import sha256
from audit_cymbal_similarity import waveform_similarity


def test_stem_sum_zero_pads_without_time_shift_and_preserves_common_gain(tmp_path):
    drum=np.zeros((480,2),dtype=np.float32);drum[30]=[.5,-.5]
    guitar=np.zeros((600,1),dtype=np.float32);guitar[45]=.25
    sources=[]
    for name,a in [('drums.wav',drum),('guitar.wav',guitar)]:
        p=tmp_path/name;sf.write(p,a,48000,subtype='FLOAT')
        sources.append({'name':name,'sha256':sha256(p),'frames':len(a)})
    # The production source is OGG, but stem identity is its basename, not codec.
    ref={'chart':str(tmp_path/'notes.mid'),'audio':{'frames':600,'sample_rate':48000,'sources':sources,'linear_gain':.5}}
    result,sr,files=reconstruct_parts(ref)
    assert sr==48000 and len(files)==2
    assert np.array_equal(result['original_mix'],result['original_drums']+result['drums_stem_withheld'])
    assert np.array_equal(np.flatnonzero(np.any(result['original_drums'],axis=1)),[30])
    assert np.array_equal(np.flatnonzero(np.any(result['drums_stem_withheld'],axis=1)),[45])
    assert result['original_mix'][30,0]==.25
    assert result['original_mix'][45,0]==.125
    sources[0]['sha256']='invalid'
    with pytest.raises(ValueError,match='hash changed'):reconstruct_parts(ref)


def test_silence_and_missing_anchors_cannot_pass_screen():
    silent=safe_profile(np.arange(20)/1000,np.zeros(20),[.01])
    assert silent['peak_lag_ms'] is None
    assert not screen_decision([silent]*3)['passes']
    assert safe_profile(np.arange(20)/1000,np.ones(20),[])['status']=='no anchors'


def test_independent_end_window_failure_is_not_hidden_by_start_fit():
    windows=[{'status':'measured','notes':10,'peak_lag_ms':x,'individual_support_within_10_ms':1} for x in [-3,-3,25]]
    assert screen_decision(windows)=={'candidate_ms':-5,'passes':False}


def test_waveform_reuse_screen_handles_gain_delay_and_silence():
    rng=np.random.default_rng(4)
    a=rng.normal(size=1280)*np.exp(-np.arange(1280)/300)
    b=np.r_[np.zeros(8),a[:-8]]*.4
    matched=waveform_similarity(a,b)
    assert matched['correlation']>.99
    assert matched['lag_ms']==.5
    assert waveform_similarity(np.zeros(1280),np.zeros(1280))['correlation'] is None
    assert waveform_similarity(a,rng.normal(size=1280))['correlation']<.4
