using System;
using System.Reflection;
using BeatSight.Game.Screens.Settings;
using osu.Framework.Bindables;
using osu.Framework.Graphics;
using osu.Framework.Graphics.Containers;
using Xunit;

namespace BeatSight.Tests
{
    public partial class SettingsSectionBuildTests
    {
        [Fact]
        public void BuildingSectionWithEnumDropdownsDoesNotThrowResponsiveSizingErrors()
        {
            var section = new TestSettingsSection();

            Exception? ex = Record.Exception(() =>
            {
                invokePrivate(section, "loadSection");
                invokePrivate(section, "applyResponsiveControlSizing", true);
                invokePrivate(section, "rebuildContent");
                invokePrivate(section, "applyResponsiveControlSizing", true);
            });

            Assert.Null(ex);
        }

        private static object? invokePrivate(object target, string methodName, params object?[] args)
        {
            var method = target.GetType().BaseType?.GetMethod(methodName, BindingFlags.Instance | BindingFlags.NonPublic)
                ?? throw new InvalidOperationException($"Method '{methodName}' not found on base SettingsSection.");

            return method.Invoke(target, args);
        }

        private enum TestQualityMode
        {
            Fast,
            Balanced,
            Accurate
        }

        private sealed partial class TestSettingsSection : SettingsSection
        {
            private readonly Bindable<TestQualityMode> enumBindable = new(TestQualityMode.Balanced);
            private readonly BindableBool toggleBindable = new(true);
            private readonly BindableDouble sliderBindable = new(0.5)
            {
                MinValue = 0,
                MaxValue = 1,
                Precision = 0.01
            };

            public TestSettingsSection()
                : base("Test Section", new Container(), new SettingsTooltipOverlay())
            {
            }

            protected override Drawable createContent()
            {
                var content = new FillFlowContainer
                {
                    RelativeSizeAxes = Axes.X,
                    AutoSizeAxes = Axes.Y,
                    Direction = FillDirection.Vertical,
                    Spacing = new osuTK.Vector2(0, 6),
                    Children = new Drawable[]
                    {
                        CreateEnumDropdown("Mode", enumBindable),
                        CreateEnumDropdown("Mode Label", enumBindable, formatter: value => value.ToString(), enableSearch: true),
                        CreateCheckbox("Enabled", toggleBindable),
                        CreateSlider("Confidence", sliderBindable, 0, 1, 0.01, toggleBindable: toggleBindable, toggleLabelText: "Force")
                    }
                };

                return content;
            }
        }
    }
}
