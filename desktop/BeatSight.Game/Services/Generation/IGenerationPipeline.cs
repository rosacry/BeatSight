using System.Collections.Generic;
using System.Threading;
using BeatSight.Game.AI;

namespace BeatSight.Game.Services.Generation
{
    public interface IGenerationPipeline
    {
        IAsyncEnumerable<PipelineProgress> RunAsync(GenerationPipelineRequest request, CancellationToken cancellationToken);
    }
}
