using System.Reflection;
using System.Text.Json;
using System.Text.Json.Nodes;
using BeatSight.Tests.VisualRegression;

namespace BeatSight.Tests;

[Collection("VisualRegression")]
public class VisualRegressionInputSuppressionTests
{
    private static readonly string[] suppressedHandlerNames =
    {
        "OpenTabletDriverHandler",
        "PenHandler",
        "JoystickHandler",
        "TouchHandler",
    };

    private static readonly string[] inputSuppressionEnvKeys =
    {
        "SDL_JOYSTICK_HIDAPI",
        "SDL_JOYSTICK_RAWINPUT",
        "SDL_JOYSTICK_WGI",
        "SDL_DIRECTINPUT_ENABLED",
        "SDL_XINPUT_ENABLED",
        "SDL_AUTO_UPDATE_JOYSTICKS",
        "SDL_HINT_JOYSTICK_HIDAPI",
        "SDL_HINT_JOYSTICK_RAWINPUT",
        "SDL_HINT_JOYSTICK_WGI",
        "SDL_HINT_DIRECTINPUT_ENABLED",
        "SDL_HINT_XINPUT_ENABLED",
        "SDL_HINT_AUTO_UPDATE_JOYSTICKS",
    };

    private static readonly BindingFlags privateStatic = BindingFlags.NonPublic | BindingFlags.Static;
    private static readonly Type rendererType = typeof(LiveVisualCaptureRenderer);

    [Fact]
    public void PreseedFrameworkConfigAddsIgnoredInputHandlers()
    {
        MethodInfo? method = rendererType.GetMethod("preseedSuppressedInputHandlersConfig", privateStatic);
        Assert.NotNull(method);

        string path = Path.Combine(AppContext.BaseDirectory, "framework.ini");
        using var restoreScope = new FileRestoreScope(path);

        File.WriteAllText(path, "WindowMode = Windowed\nIgnoredInputHandlers = \n");
        method!.Invoke(null, null);

        string content = File.ReadAllText(path);
        Assert.Contains("IgnoredInputHandlers", content, StringComparison.Ordinal);
        foreach (string name in suppressedHandlerNames)
            Assert.Contains(name, content, StringComparison.Ordinal);
    }

    [Fact]
    public void PreseedInputProfileDisablesOptionalHandlers()
    {
        MethodInfo? method = rendererType.GetMethod("preseedSuppressedInputHandlersProfile", privateStatic);
        Assert.NotNull(method);

        string path = Path.Combine(AppContext.BaseDirectory, "input.json");
        using var restoreScope = new FileRestoreScope(path);

        JsonObject root = new()
        {
            ["InputHandlers"] = new JsonArray
            {
                new JsonObject
                {
                    ["$type"] = "osu.Framework.Input.Handlers.Keyboard.KeyboardHandler, osu.Framework",
                    ["Enabled"] = true,
                },
                new JsonObject
                {
                    ["$type"] = "osu.Framework.Input.Handlers.Tablet.OpenTabletDriverHandler, osu.Framework",
                    ["Enabled"] = true,
                },
                new JsonObject
                {
                    ["$type"] = "osu.Framework.Input.Handlers.Touch.TouchHandler, osu.Framework",
                    ["Enabled"] = true,
                },
                new JsonObject
                {
                    ["$type"] = "osu.Framework.Input.Handlers.Joystick.JoystickHandler, osu.Framework",
                    ["Enabled"] = true,
                },
                new JsonObject
                {
                    ["$type"] = "osu.Framework.Input.Handlers.Midi.MidiHandler, osu.Framework",
                    ["Enabled"] = true,
                },
            },
        };

        File.WriteAllText(path, root.ToJsonString(new JsonSerializerOptions { WriteIndented = false }));
        method!.Invoke(null, null);

        JsonObject? parsedRoot = JsonNode.Parse(File.ReadAllText(path)) as JsonObject;
        Assert.NotNull(parsedRoot);

        JsonArray? handlers = parsedRoot!["InputHandlers"] as JsonArray;
        Assert.NotNull(handlers);

        bool keyboardSeen = false;
        bool tabletSeen = false;
        bool touchSeen = false;
        bool joystickSeen = false;
        bool midiSeen = false;

        foreach (JsonNode? handlerNode in handlers!)
        {
            JsonObject? handler = handlerNode as JsonObject;
            if (handler == null)
                continue;

            string? type = handler["$type"]?.GetValue<string>();
            bool enabled = handler["Enabled"]?.GetValue<bool>() ?? true;
            if (string.IsNullOrWhiteSpace(type))
                continue;

            if (type.Contains("KeyboardHandler", StringComparison.Ordinal))
            {
                keyboardSeen = true;
                Assert.True(enabled);
            }
            else if (type.Contains("OpenTabletDriverHandler", StringComparison.Ordinal))
            {
                tabletSeen = true;
                Assert.False(enabled);
            }
            else if (type.Contains("TouchHandler", StringComparison.Ordinal))
            {
                touchSeen = true;
                Assert.False(enabled);
            }
            else if (type.Contains("JoystickHandler", StringComparison.Ordinal))
            {
                joystickSeen = true;
                Assert.False(enabled);
            }
            else if (type.Contains("MidiHandler", StringComparison.Ordinal))
            {
                midiSeen = true;
                Assert.True(enabled);
            }
        }

        Assert.True(keyboardSeen);
        Assert.True(tabletSeen);
        Assert.True(touchSeen);
        Assert.True(joystickSeen);
        Assert.True(midiSeen);
    }

    [Fact]
    public void ApplyInputSubsystemHintsSetsSuppressionEnvironment()
    {
        MethodInfo? method = rendererType.GetMethod("applyInputSubsystemHints", privateStatic);
        Assert.NotNull(method);

        var priorValues = new Dictionary<string, string?>(StringComparer.Ordinal);
        foreach (string key in inputSuppressionEnvKeys)
        {
            priorValues[key] = Environment.GetEnvironmentVariable(key);
            Environment.SetEnvironmentVariable(key, null);
        }

        try
        {
            method!.Invoke(null, null);
            foreach (string key in inputSuppressionEnvKeys)
                Assert.Equal("0", Environment.GetEnvironmentVariable(key));
        }
        finally
        {
            foreach (var kvp in priorValues)
                Environment.SetEnvironmentVariable(kvp.Key, kvp.Value);
        }
    }

    private sealed class FileRestoreScope : IDisposable
    {
        private readonly string path;
        private readonly bool existed;
        private readonly string? contents;

        public FileRestoreScope(string path)
        {
            this.path = path;
            existed = File.Exists(path);
            contents = existed ? File.ReadAllText(path) : null;
        }

        public void Dispose()
        {
            if (existed)
                File.WriteAllText(path, contents ?? string.Empty);
            else if (File.Exists(path))
                File.Delete(path);
        }
    }
}
