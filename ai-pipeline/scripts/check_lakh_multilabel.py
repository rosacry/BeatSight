#!/usr/bin/env python3
"""Check Lakh MIDI for multi-label china/splash windows."""
from pathlib import Path
import mido
from collections import Counter

lakh_path = Path('F:/datasets/lakh_midi/lmd_full/0')
GM = {35:'kick',36:'kick',37:'cross_stick',38:'snare',40:'snare',42:'hh_c',44:'hh_p',46:'hh_o',49:'crash',52:'china',55:'splash',57:'crash',51:'ride',53:'ride_bell',41:'tom',43:'tom',45:'tom',47:'tom',48:'tom',50:'tom'}

china_with = Counter()
splash_with = Counter()
china_total = 0
splash_total = 0
files = 0

for mf in list(lakh_path.glob('*.mid'))[:300]:
    try:
        mid = mido.MidiFile(str(mf))
        events = []
        for track in mid.tracks:
            t = 0
            for msg in track:
                t += msg.time
                if msg.type == 'note_on' and msg.velocity > 0 and msg.note in GM:
                    events.append((t, GM[msg.note]))
        events.sort()
        for i,(t1,c1) in enumerate(events):
            if c1 == 'china':
                china_total += 1
            if c1 == 'splash':
                splash_total += 1
            nearby = set([c1])
            for j,(t2,c2) in enumerate(events):
                if i!=j and abs(t2-t1) < 50:
                    nearby.add(c2)
            if len(nearby)>1:
                if 'china' in nearby:
                    for c in nearby:
                        if c != 'china': china_with[c] += 1
                if 'splash' in nearby:
                    for c in nearby:
                        if c != 'splash': splash_with[c] += 1
        files += 1
    except Exception as e:
        pass

print(f'Files checked: {files}')
print(f'China total: {china_total}, Splash total: {splash_total}')
print(f'China co-occurs with: {china_with.most_common(8)}')
print(f'Splash co-occurs with: {splash_with.most_common(8)}')
