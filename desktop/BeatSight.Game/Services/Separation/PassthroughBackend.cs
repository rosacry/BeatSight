using System;
using System.Threading;
using System.Threading.Tasks;

namespace BeatSight.Game.Services.Separation
{
    public sealed class PassthroughBackend : IDemucsBackend
    {
        public string Name => "passthrough";

        public Task LoadModelAsync(CancellationToken cancellationToken) => Task.CompletedTask;

        public Task<SeparationOutput> SeparateAsync(string audioPath, CancellationToken cancellationToken, IProgress<double>? progress = null)
        {
            cancellationToken.ThrowIfCancellationRequested();
            progress?.Report(1.0);
            return Task.FromResult(new SeparationOutput(audioPath, audioPath, true, false));
        }

        public ValueTask DisposeAsync() => ValueTask.CompletedTask;
    }
}
