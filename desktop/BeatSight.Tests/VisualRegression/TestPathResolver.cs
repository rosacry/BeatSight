using System.IO;

namespace BeatSight.Tests.VisualRegression
{
    internal static class TestPathResolver
    {
        internal static string ResolveRepositoryRoot()
        {
            string current = AppContext.BaseDirectory;
            for (int i = 0; i < 8; i++)
            {
                string candidate = Path.GetFullPath(Path.Combine(current, ".."));
                if (File.Exists(Path.Combine(candidate, "BeatSight.sln")))
                    return candidate;

                current = candidate;
            }

            throw new DirectoryNotFoundException("Could not locate repository root from test output directory.");
        }
    }
}
