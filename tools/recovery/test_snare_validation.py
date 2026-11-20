"""Guard new corpus parsing/mixture boundaries, not measured model scores."""
import numpy as np
import pytest
from validate_snare_addition import enst_events,idmt_events,mix_enst,idmt_crosscheck


def test_enst_side_stick_and_unknown_are_retained(tmp_path):
    p=tmp_path/'a.txt';p.write_text('1.0 cs\n1.0 sd\n2.0 sweep\n')
    assert [x['family'] for x in enst_events(p,{'cs':37,'sd':38})]==['OT','SD','OT']


def test_idmt_keeps_last_event_and_instrument_not_dummy_pitch(tmp_path):
    p=tmp_path/'a.xml';p.write_text('<instrumentRecording><globalParameter><audioFileName>a.wav</audioFileName></globalParameter><transcription><event><pitch>0</pitch><onsetSec>0.1</onsetSec><instrument>SD</instrument></event><event><pitch>0</pitch><onsetSec>1.2</onsetSec><instrument>HH</instrument></event></transcription></instrumentRecording>')
    events,name=idmt_events(p)
    assert name=='a.wav' and [(x['time_seconds'],x['family']) for x in events]==[(.1,'SD'),(1.2,'HH')]


def test_fixed_stereo_mix_preserves_impulse_times_and_channels():
    a=np.zeros((100,2),dtype=np.float32);b=a.copy();a[10,0]=1;b[80,1]=.5
    out=mix_enst(a,b)
    assert out[10,0]==.5 and out[80,1]==.25 and np.count_nonzero(out)==2
    assert a[10,0]==1 and b[80,1]==.5
    with pytest.raises(ValueError):mix_enst(a,b[:-1])
    with pytest.raises(ValueError):mix_enst(a,np.full_like(b,np.nan))


def test_idmt_missing_last_event_fails_admission_without_dropping_it(tmp_path):
    events=[{'time_seconds':1.,'family':f} for f in ['KD','SD','HH']]+[{'time_seconds':2.,'family':'HH'}]
    copies={}
    for f in ['KD','SD','HH']:
        p=tmp_path/(f+'.svl');p.write_text('<sv><data><model sampleRate="44100"/><dataset><point frame="44100"/></dataset></data></sv>');copies['svl_'+f]=p
    checks=idmt_crosscheck(events,copies,44100)
    assert checks['KD']['passes'] and checks['SD']['passes']
    assert not checks['HH']['passes'] and checks['HH']['xml_trailing_events']==[2.]
    assert len(events)==4
