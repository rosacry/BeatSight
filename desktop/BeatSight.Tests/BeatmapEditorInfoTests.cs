using BeatSight.Game.Beatmaps;
using Newtonsoft.Json;
using Xunit;

namespace BeatSight.Tests
{
    public class BeatmapEditorInfoTests
    {
        [Fact]
        public void EditorSettingsSerializeWaveformScaleAndBeatGrid()
        {
            var beatmap = new Beatmap
            {
                Editor = new EditorInfo
                {
                    SnapDivisor = 8,
                    TimelineZoom = 1.5,
                    WaveformScale = 1.75,
                    BeatGridVisible = false
                }
            };

            string serialized = JsonConvert.SerializeObject(beatmap);
            var restored = JsonConvert.DeserializeObject<Beatmap>(serialized);

            Assert.NotNull(restored);
            Assert.NotNull(restored!.Editor);
            var editorInfo = restored.Editor!;
            Assert.Equal(8, editorInfo.SnapDivisor);
            Assert.Equal(1.5, editorInfo.TimelineZoom);

            double? waveformScale = editorInfo.WaveformScale;
            Assert.True(waveformScale.HasValue);
            Assert.Equal(1.75, waveformScale.Value);

            bool? beatGridVisible = editorInfo.BeatGridVisible;
            Assert.True(beatGridVisible.HasValue);
            Assert.False(beatGridVisible.Value);
        }
    }
}
