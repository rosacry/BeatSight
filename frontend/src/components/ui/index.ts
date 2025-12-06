/**
 * UI Components - Modern, accessible, and animated component library.
 * Exports all reusable UI components for the BeatSight frontend.
 */

// Button components
export { Button, IconButton, buttonVariants, type ButtonProps, type IconButtonProps } from './Button'

// Card components
export {
    Card,
    CardHeader,
    CardContent,
    CardFooter,
    FeatureCard,
    StatCard,
    GlowingCard,
    cardVariants,
    type CardProps,
} from './Card'

// Badge components
export {
    Badge,
    StatusBadge,
    CountBadge,
    badgeVariants,
    type BadgeProps,
    type StatusType,
} from './Badge'

// Input components
export {
    Input,
    Textarea,
    SearchInput,
    PasswordInput,
    inputVariants,
    type InputProps,
    type TextareaProps,
} from './Input'

// Modal components
export {
    Modal,
    ModalHeader,
    ModalBody,
    ModalFooter,
    ConfirmDialog,
    modalVariants,
    type ModalProps,
} from './Modal'

// Advanced Modal components
export {
    Sheet,
    CommandPalette,
    Drawer,
    FullscreenOverlay,
    useModalState,
    useCommandPalette,
    useConfirmDialog,
    type SheetProps,
    type SheetSide,
    type SheetSize,
    type CommandItem,
    type CommandPaletteProps,
    type DrawerProps,
    type FullscreenOverlayProps,
} from './AdvancedModals'

// Dropdown components
export {
    Dropdown,
    DropdownTrigger,
    DropdownMenu,
    DropdownItem,
    DropdownSeparator,
    DropdownLabel,
    Select,
    MultiSelect,
    dropdownTriggerVariants,
    dropdownMenuVariants,
    type DropdownProps,
    type SelectOption,
    type SelectProps,
    type MultiSelectProps,
} from './Dropdown'

// Tabs components
export {
    Tabs,
    TabsList,
    TabTrigger,
    TabContent,
    TabIndicator,
    IconTabs,
    VerticalTabs,
    tabsListVariants,
    tabTriggerVariants,
    tabContentVariants,
    type TabsProps,
    type TabContentProps,
} from './Tabs'

// Tooltip components
export {
    Tooltip,
    RichTooltip,
    ShortcutTooltip,
    InfoTooltip,
    tooltipVariants,
    type TooltipProps,
    type RichTooltipProps,
    type ShortcutTooltipProps,
} from './Tooltip'

// Progress components
export {
    ProgressBar,
    CircularProgress,
    StepsProgress,
    Spinner,
    Skeleton,
    progressVariants,
    progressBarVariants,
    type ProgressBarProps,
    type CircularProgressProps,
    type StepsProgressProps,
    type SpinnerProps,
    type SkeletonProps,
    type Step,
} from './Progress'

// Switch/Toggle components
export {
    Switch,
    ToggleGroup,
    Checkbox,
    RadioGroup,
    switchVariants,
    type SwitchProps,
    type ToggleOption,
    type ToggleGroupProps,
    type CheckboxProps,
    type RadioOption,
    type RadioGroupProps,
} from './Switch'

// Alert/Notification components
export {
    Alert,
    Toast,
    ToastContainer,
    Banner,
    Callout,
    alertVariants,
    type AlertProps,
    type ToastProps,
    type ToastContainerProps,
    type BannerProps,
    type CalloutProps,
} from './Alert'

// Slider components
export {
    Slider,
    RangeSlider,
    VolumeSlider,
    type SliderProps,
    type RangeSliderProps,
    type VolumeSliderProps,
} from './Slider'

// DataTable components
export {
    DataTable,
    TablePagination,
    type Column,
    type SortState,
    type DataTableProps,
    type TablePaginationProps,
} from './DataTable'

// Avatar components
export {
    Avatar,
    AvatarGroup,
    AvatarWithName,
    AvatarUpload,
    type AvatarProps,
    type AvatarGroupProps,
    type AvatarWithNameProps,
    type AvatarUploadProps,
} from './Avatar'

// Navigation components
export {
    Breadcrumb,
    NavMenu,
    NavItem,
    Sidebar,
    SidebarSection,
    SidebarItem,
    Pagination,
    type BreadcrumbItem,
    type BreadcrumbProps,
    type NavMenuProps,
    type NavItemProps,
    type SidebarProps,
    type SidebarSectionProps,
    type SidebarItemProps,
    type PaginationProps,
} from './Navigation'

// Accordion components
export {
    Accordion,
    AccordionItem,
    AccordionTrigger,
    AccordionContent,
    Collapsible,
    CollapsibleTrigger,
    CollapsibleContent,
    ExpandableCard,
    type AccordionProps,
    type AccordionItemProps,
    type AccordionTriggerProps,
    type AccordionContentProps,
    type CollapsibleProps,
    type CollapsibleTriggerProps,
    type CollapsibleContentProps,
    type ExpandableCardProps,
} from './Accordion'

// Chart components
export {
    BarChart,
    DonutChart,
    LineChart,
    StatCard as ChartStatCard,
    ProgressRing,
    type DataPoint,
    type BarChartProps,
    type DonutChartProps,
    type LineChartProps,
    type StatCardProps as ChartStatCardProps,
    type ProgressRingProps,
} from './Charts'

// File Upload components
export {
    FileUpload,
    FilePreview,
    AudioFileUpload,
    UploadProgress,
    type FileUploadProps,
    type FilePreviewProps,
    type AudioFileUploadProps,
    type UploadProgressProps,
} from './FileUpload'

// Notification components
export {
    NotificationProvider,
    Notification,
    NotificationBadge,
    NotificationBell,
    NotificationList,
    useNotification,
    notify,
    type NotificationData,
    type NotificationProps,
    type NotificationProviderProps,
    type NotificationContextType,
    type NotificationBadgeProps,
    type NotificationBellProps,
    type NotificationListProps,
} from './Notification'

// Audio Player components
export {
    AudioPlayer,
    MiniPlayer,
    type AudioPlayerProps,
    type AudioTrack,
    type MiniPlayerProps,
} from './AudioPlayer'

// Advanced Visualization components
export {
    SpectrumVisualizer,
    WaveformDisplay,
    RadarChart,
    Heatmap,
    DrumKitVisualizer,
    PerformanceMeter,
    TimelineVisualizer,
    type SpectrumVisualizerProps,
    type WaveformDisplayProps,
    type RadarChartProps,
    type HeatmapProps,
    type DrumKitVisualizerProps,
    type PerformanceMeterProps,
    type TimelineVisualizerProps,
    type FrequencyData,
    type WaveformPoint,
    type HeatmapCell,
    type RadarDataPoint,
    type DrumHit,
    type TimelineEvent,
} from './Visualizations'

// Advanced Form components (extends base form controls)
export {
    Form,
    FormField,
    FormGroup,
    FormSection,
    FormActions,
    RadioGroup as AdvancedRadioGroup,
    CheckboxGroup,
    ColorPicker,
    RangeSlider as AdvancedRangeSlider,
    useFormContext,
    type FormProps,
    type FormFieldProps,
    type FormGroupProps,
    type FormSectionProps,
    type FormActionsProps,
    type RadioGroupProps as AdvancedRadioGroupProps,
    type CheckboxGroupProps,
    type ColorPickerProps,
    type RangeSliderProps as AdvancedRangeSliderProps,
    type FormContextValue,
    type RadioOption as AdvancedRadioOption,
    type CheckboxOption,
} from './FormElements'

// Micro-interaction components
export {
    useRipple,
    MagneticButton,
    TiltCard,
    AnimatedCounter,
    HoverReveal,
    SpotlightCard,
    TypingText,
    StaggerChildren,
    ParallaxContainer,
    MorphingButton,
    type MagneticButtonProps,
    type TiltCardProps,
    type AnimatedCounterProps,
    type HoverRevealProps,
    type SpotlightCardProps,
    type TypingTextProps,
    type StaggerChildrenProps,
    type ParallaxContainerProps,
    type MorphingButtonProps,
} from './MicroInteractions'

// Icons
export {
    Icon,
    PlayIcon,
    PauseIcon,
    StopIcon,
    SkipForwardIcon,
    SkipBackIcon,
    VolumeIcon,
    VolumeMuteIcon,
    MusicNoteIcon,
    MicrophoneIcon,
    WaveformIcon,
    DrumIcon,
    DrumstickIcon,
    MetronomeIcon,
    HomeIcon,
    SearchIcon,
    SettingsIcon,
    UserIcon,
    MenuIcon,
    CloseIcon,
    ChevronLeftIcon,
    ChevronRightIcon,
    ChevronUpIcon,
    ChevronDownIcon,
    ArrowLeftIcon,
    ArrowRightIcon,
    PlusIcon,
    MinusIcon,
    CheckIcon,
    EditIcon,
    TrashIcon,
    CopyIcon,
    DownloadIcon,
    UploadIcon,
    ShareIcon,
    RefreshIcon,
    InfoIcon,
    WarningIcon,
    ErrorIcon,
    SuccessIcon,
    LoadingIcon,
    StarIcon,
    HeartIcon,
    TrophyIcon,
    FireIcon,
    GridIcon,
    ListIcon,
    MaximizeIcon,
    MinimizeIcon,
    ClockIcon,
    CalendarIcon,
    ExternalLinkIcon,
    FilterIcon,
    SortIcon,
    MoreHorizontalIcon,
    MoreVerticalIcon,
    KeyboardIcon,
    DynamicIcon,
    iconMap,
    type IconProps,
    type IconName,
} from './Icons'

// Page Transitions
export {
    TransitionProvider,
    usePageTransition,
    PageTransition,
    AnimatedOutlet,
    StaggeredContent,
    AnimatedPageHeader,
    RevealOnScroll,
    ParallaxHero,
    type TransitionType,
    type PageTransitionProps,
    type StaggeredContentProps,
    type AnimatedPageHeaderProps,
    type RevealOnScrollProps,
    type ParallaxHeroProps,
} from './PageTransitions'

// Loading States
export {
    BrandLoader,
    WaveformLoader,
    BeatPulseLoader,
    ProgressLoader,
    Skeleton as LoadingSkeleton,
    SongCardSkeleton,
    TableRowSkeleton,
    ProfileSkeleton,
    TimelineSkeleton,
    FullPageLoader,
    InlineLoader,
    Shimmer,
    type BrandLoaderProps,
    type WaveformLoaderProps,
    type BeatPulseLoaderProps,
    type ProgressLoaderProps,
    type SkeletonProps as LoadingSkeletonProps,
} from './LoadingStates'

// Empty States
export {
    EmptyState,
    NoDataIcon,
    NoSongsIcon,
    NoSearchResultsIcon,
    NoNotificationsIcon,
    NoActivityIcon,
    ErrorIcon as EmptyErrorIcon,
    OfflineIcon,
    UploadIcon as EmptyUploadIcon,
    NoSongsEmptyState,
    NoSearchResultsEmptyState,
    NoNotificationsEmptyState,
    ErrorEmptyState,
    OfflineEmptyState,
    UploadEmptyState,
    NoBeatmapsEmptyState,
    NoActivityEmptyState,
    IllustratedEmptyState,
    type EmptyStateProps,
    type IllustratedEmptyStateProps,
} from './EmptyStates'

// Timeline Controls
export {
    TimelineToolbar,
    ToolbarGroup,
    ToolbarDivider,
    ToolbarSpacer,
    ControlButton,
    PlaybackControls,
    TimeDisplay,
    SpeedSelector,
    VolumeSlider as TimelineVolumeSlider,
    SnapSelector,
    ToggleSwitch,
    EditStatsBadge,
    UndoRedoButtons,
    SelectionInfoBar,
    KeyboardShortcutsLegend,
    WaveformScaleControl,
    type TimelineToolbarProps,
    type ControlButtonProps,
    type PlaybackControlsProps,
    type TimeDisplayProps,
    type SpeedSelectorProps,
    type VolumeSliderProps as TimelineVolumeSliderProps,
    type SnapSelectorProps,
    type ToggleSwitchProps,
    type EditStatsBadgeProps,
    type UndoRedoButtonsProps,
    type SelectionInfoBarProps,
    type KeyboardShortcutsLegendProps,
    type WaveformScaleControlProps,
} from './TimelineControls'

// Feedback Components
export {
    Tooltip as SimpleTooltip,
    Badge as FeedbackBadge,
    NotificationDot,
    ToastProvider,
    useToast,
    ProgressRing as FeedbackProgressRing,
    StatusIndicator,
    HighlightTag,
    type TooltipProps as SimpleTooltipProps,
    type BadgeProps as FeedbackBadgeProps,
    type NotificationDotProps,
    type ToastProviderProps,
    type StatusIndicatorProps,
    type HighlightTagProps,
} from './Feedback'

// Form Input Components
export {
    TextInput,
    PasswordInput as FormPasswordInput,
    SearchInput as FormSearchInput,
    Textarea as FormTextarea,
    SelectInput,
    Checkbox as FormCheckbox,
    Radio,
    RadioGroup as FormRadioGroup,
    Switch as FormSwitch,
    Slider as FormSlider,
    NumberInput,
    FileInput,
    FormGroup as FormFieldGroup,
    type TextInputProps,
    type PasswordInputProps as FormPasswordInputProps,
    type SearchInputProps as FormSearchInputProps,
    type TextareaProps as FormTextareaProps,
    type SelectInputProps,
    type SelectOption as FormSelectOption,
    type CheckboxProps as FormCheckboxProps,
    type RadioProps,
    type RadioGroupProps as FormRadioGroupProps,
    type RadioGroupOption,
    type SwitchProps as FormSwitchProps,
    type SliderProps as FormSliderProps,
    type NumberInputProps,
    type FileInputProps,
    type FormGroupProps as FormFieldGroupProps,
} from './FormInputs'

// Cards & Data Display Components
export {
    Card as DisplayCard,
    TrackCard,
    StatCard as DisplayStatCard,
    UserCard,
    FeatureCard as DisplayFeatureCard,
    PricingCard,
    DataTable as DisplayDataTable,
    CodeBlock,
    LinkCard,
    QuickStats,
    type CardProps as DisplayCardProps,
    type TrackCardProps,
    type StatCardProps as DisplayStatCardProps,
    type UserCardProps,
    type FeatureCardProps as DisplayFeatureCardProps,
    type PricingCardProps,
    type DataTableProps as DisplayDataTableProps,
    type DataTableColumn,
    type CodeBlockProps,
    type LinkCardProps,
    type QuickStatsProps,
} from './Cards'

// Animated Components (Framer Motion powered)
export {
    AnimatedContainer,
    StaggerList,
    MagneticButton as FMagneticButton,
    FloatingCard,
    RevealText,
    GradientBorderCard,
    SpotlightCard as FSpotlightCard,
    AnimatedCounter as FAnimatedCounter,
    ScrollProgress,
    AnimatedListItem,
    ParallaxContainer as FParallaxContainer,
    MorphingBackground,
    PageTransition as FPageTransition,
    AnimatePresence,
    motion,
    fadeInUp,
    fadeInScale,
    staggerContainer,
    slideInFromLeft,
    slideInFromRight,
} from './AnimatedComponents'

// Toast Notifications (Sonner powered)
export {
    Toaster,
    toast,
    toastStyles,
} from './Toast'

// Glassmorphism Components
export {
    GlassPanel,
    GlassCard,
    GlassButton,
    GlassInput,
    GlassSelect,
    GlassNav,
    GlassOverlay,
    GlassBadge,
    GlassDivider,
    GlassSkeleton,
    GlassProgress,
} from './Glassmorphism'

// Data Visualization Components (Premium analytics)
export {
    StatCard as DataStatCard,
    ProgressRing as DataProgressRing,
    BarChart as DataBarChart,
    Sparkline,
    ActivityHeatmap,
    DonutChart as DataDonutChart,
    MetricComparison,
    ChartSkeleton,
    type StatCardProps as DataStatCardProps,
    type ProgressRingProps as DataProgressRingProps,
    type BarChartProps as DataBarChartProps,
    type BarChartData,
    type SparklineProps,
    type HeatmapData,
    type ActivityHeatmapProps,
    type DonutChartData,
    type DonutChartProps as DataDonutChartProps,
    type MetricComparisonProps,
    type ChartSkeletonProps,
} from './DataVisualization'

// Command Palette (⌘K style)
export {
    CommandPalette as CMDKPalette,
    useCommandPalette as useCMDKPalette,
    CommandIcons,
    type CommandItem as CMDKCommandItem,
    type CommandSection,
    type CommandPaletteProps as CMDKPaletteProps,
} from './CommandPalette'

// Premium Skeleton Loading Components (from Skeleton.tsx)
export {
    Skeleton as PremiumSkeleton,
    SkeletonText as PremiumSkeletonText,
    SkeletonAvatar as PremiumSkeletonAvatar,
    SkeletonCard as PremiumSkeletonCard,
    SkeletonTable as PremiumSkeletonTable,
    SkeletonTrackCard,
    SkeletonWaveform,
    SkeletonStatsCard,
    SkeletonProfile,
    SkeletonJobProgress,
    SkeletonBeatmapCard,
    SkeletonDashboard,
    type SkeletonProps as PremiumSkeletonProps,
    type SkeletonTextProps as PremiumSkeletonTextProps,
    type SkeletonAvatarProps as PremiumSkeletonAvatarProps,
    type SkeletonCardProps as PremiumSkeletonCardProps,
    type SkeletonTableProps as PremiumSkeletonTableProps,
} from './Skeleton'

