
lines = []
with open('desktop/BeatSight.Game/Screens/Playback/PlaybackScreen.cs', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Keep lines 0 to 2194 (index 2194 is line 2195, so we want up to index 2194 exclusive? No, 1-based line 2194 is index 2193)
# We want to keep up to line 2194.
# Line 2194 is "    }\n"
# So we want lines[:2194]
truncated_lines = lines[:2194]

# Add the closing brace for the namespace
truncated_lines.append("}\n")

with open('desktop/BeatSight.Game/Screens/Playback/PlaybackScreen.cs', 'w', encoding='utf-8') as f:
    f.writelines(truncated_lines)
