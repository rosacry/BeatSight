import React, { forwardRef, useState, useId } from 'react';
import {
    SearchIcon as Search,
    CloseIcon as X,
    CheckIcon as Check,
    ChevronDownIcon as ChevronDown,
    InfoIcon
} from './Icons';

// Create missing icons inline
const Eye: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
        <circle cx="12" cy="12" r="3" />
    </svg>
);

const EyeOff: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
        <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
);

const AlertCircle: React.FC<{ className?: string }> = ({ className }) => (
    <svg className={className} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
);

// Alias Info for consistent naming
const Info = InfoIcon;

// ============================================================================
// Form Input Components - Text Fields, Selects, Checkboxes, etc.
// ============================================================================

// Shared form field styles
const baseInputStyles = `
  w-full px-4 py-3 bg-dark-400/50 border border-white/10/50 rounded-xl
  text-white placeholder-gray-400
  transition-all duration-200
  focus:outline-none focus:border-primary-500/50 focus:ring-2 focus:ring-primary-500/20
  disabled:opacity-50 disabled:cursor-not-allowed
`;

const errorInputStyles = 'border-red-500/50 focus:border-red-500/50 focus:ring-red-500/20';

// ============================================================================
// Text Input
// ============================================================================

export interface TextInputProps extends React.InputHTMLAttributes<HTMLInputElement> {
    label?: string;
    error?: string;
    hint?: string;
    leftIcon?: React.ReactNode;
    rightIcon?: React.ReactNode;
}

export const TextInput = forwardRef<HTMLInputElement, TextInputProps>(
    ({ label, error, hint, leftIcon, rightIcon, className = '', id, ...props }, ref) => {
        const generatedId = useId();
        const inputId = id || generatedId;

        return (
            <div className="space-y-1.5">
                {label && (
                    <label htmlFor={inputId} className="block text-sm font-medium text-gray-300">
                        {label}
                        {props.required && <span className="text-red-400 ml-1">*</span>}
                    </label>
                )}
                <div className="relative">
                    {leftIcon && (
                        <div className="absolute left-4 top-1/2 -translate-y-1/2 text-gray-400">
                            {leftIcon}
                        </div>
                    )}
                    <input
                        ref={ref}
                        id={inputId}
                        className={`
              ${baseInputStyles}
              ${leftIcon ? 'pl-11' : ''}
              ${rightIcon ? 'pr-11' : ''}
              ${error ? errorInputStyles : ''}
              ${className}
            `}
                        aria-invalid={!!error}
                        aria-describedby={error ? `${inputId}-error` : hint ? `${inputId}-hint` : undefined}
                        {...props}
                    />
                    {rightIcon && (
                        <div className="absolute right-4 top-1/2 -translate-y-1/2 text-gray-400">
                            {rightIcon}
                        </div>
                    )}
                </div>
                {error && (
                    <p id={`${inputId}-error`} className="flex items-center gap-1.5 text-sm text-red-400">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </p>
                )}
                {hint && !error && (
                    <p id={`${inputId}-hint`} className="flex items-center gap-1.5 text-sm text-gray-500">
                        <Info className="w-4 h-4" />
                        {hint}
                    </p>
                )}
            </div>
        );
    }
);

TextInput.displayName = 'TextInput';

// ============================================================================
// Password Input
// ============================================================================

export interface PasswordInputProps extends Omit<TextInputProps, 'type' | 'rightIcon'> {
    showStrengthMeter?: boolean;
}

export const PasswordInput = forwardRef<HTMLInputElement, PasswordInputProps>(
    ({ showStrengthMeter, value, ...props }, ref) => {
        const [showPassword, setShowPassword] = useState(false);

        const calculateStrength = (password: string): { score: number; label: string; color: string } => {
            let score = 0;
            if (password.length >= 8) score++;
            if (password.length >= 12) score++;
            if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
            if (/\d/.test(password)) score++;
            if (/[^a-zA-Z0-9]/.test(password)) score++;

            const levels = [
                { label: 'Very Weak', color: 'bg-red-500' },
                { label: 'Weak', color: 'bg-orange-500' },
                { label: 'Fair', color: 'bg-yellow-500' },
                { label: 'Good', color: 'bg-lime-500' },
                { label: 'Strong', color: 'bg-emerald-500' },
            ];

            return { score, ...levels[Math.min(score, 4)] };
        };

        const strength = showStrengthMeter && typeof value === 'string' ? calculateStrength(value) : null;

        return (
            <div className="space-y-2">
                <TextInput
                    ref={ref}
                    type={showPassword ? 'text' : 'password'}
                    value={value}
                    rightIcon={
                        <button
                            type="button"
                            onClick={() => setShowPassword(!showPassword)}
                            className="text-gray-400 hover:text-white transition-colors"
                            aria-label={showPassword ? 'Hide password' : 'Show password'}
                        >
                            {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                        </button>
                    }
                    {...props}
                />
                {strength && typeof value === 'string' && value.length > 0 && (
                    <div className="space-y-1">
                        <div className="flex gap-1">
                            {[0, 1, 2, 3, 4].map((i) => (
                                <div
                                    key={i}
                                    className={`h-1 flex-1 rounded-full transition-colors ${i < strength.score ? strength.color : 'bg-dark-300'
                                        }`}
                                />
                            ))}
                        </div>
                        <p className="text-xs text-gray-500">{strength.label}</p>
                    </div>
                )}
            </div>
        );
    }
);

PasswordInput.displayName = 'PasswordInput';

// ============================================================================
// Search Input
// ============================================================================

export interface SearchInputProps extends Omit<TextInputProps, 'leftIcon' | 'rightIcon'> {
    onClear?: () => void;
}

export const SearchInput = forwardRef<HTMLInputElement, SearchInputProps>(
    ({ onClear, value, ...props }, ref) => {
        return (
            <TextInput
                ref={ref}
                type="search"
                value={value}
                leftIcon={<Search className="w-5 h-5" />}
                rightIcon={
                    value && onClear ? (
                        <button
                            type="button"
                            onClick={onClear}
                            className="text-gray-400 hover:text-white transition-colors"
                            aria-label="Clear search"
                        >
                            <X className="w-5 h-5" />
                        </button>
                    ) : undefined
                }
                {...props}
            />
        );
    }
);

SearchInput.displayName = 'SearchInput';

// ============================================================================
// Textarea
// ============================================================================

export interface TextareaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
    label?: string;
    error?: string;
    hint?: string;
    maxLength?: number;
    showCount?: boolean;
}

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
    ({ label, error, hint, maxLength, showCount, className = '', id, value, ...props }, ref) => {
        const generatedId = useId();
        const textareaId = id || generatedId;
        const charCount = typeof value === 'string' ? value.length : 0;

        return (
            <div className="space-y-1.5">
                {label && (
                    <label htmlFor={textareaId} className="block text-sm font-medium text-gray-300">
                        {label}
                        {props.required && <span className="text-red-400 ml-1">*</span>}
                    </label>
                )}
                <textarea
                    ref={ref}
                    id={textareaId}
                    value={value}
                    maxLength={maxLength}
                    className={`
            ${baseInputStyles}
            min-h-[100px] resize-y
            ${error ? errorInputStyles : ''}
            ${className}
          `}
                    aria-invalid={!!error}
                    aria-describedby={error ? `${textareaId}-error` : hint ? `${textareaId}-hint` : undefined}
                    {...props}
                />
                <div className="flex justify-between items-center">
                    {error ? (
                        <p id={`${textareaId}-error`} className="flex items-center gap-1.5 text-sm text-red-400">
                            <AlertCircle className="w-4 h-4" />
                            {error}
                        </p>
                    ) : hint ? (
                        <p id={`${textareaId}-hint`} className="text-sm text-gray-500">{hint}</p>
                    ) : (
                        <span />
                    )}
                    {showCount && maxLength && (
                        <span className={`text-xs ${charCount >= maxLength ? 'text-red-400' : 'text-gray-500'}`}>
                            {charCount}/{maxLength}
                        </span>
                    )}
                </div>
            </div>
        );
    }
);

Textarea.displayName = 'Textarea';

// ============================================================================
// Select Input
// ============================================================================

export interface SelectOption {
    value: string;
    label: string;
    disabled?: boolean;
}

export interface SelectInputProps extends Omit<React.SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
    label?: string;
    error?: string;
    hint?: string;
    options: SelectOption[];
    placeholder?: string;
}

export const SelectInput = forwardRef<HTMLSelectElement, SelectInputProps>(
    ({ label, error, hint, options, placeholder, className = '', id, ...props }, ref) => {
        const generatedId = useId();
        const selectId = id || generatedId;

        return (
            <div className="space-y-1.5">
                {label && (
                    <label htmlFor={selectId} className="block text-sm font-medium text-gray-300">
                        {label}
                        {props.required && <span className="text-red-400 ml-1">*</span>}
                    </label>
                )}
                <div className="relative">
                    <select
                        ref={ref}
                        id={selectId}
                        className={`
              ${baseInputStyles}
              appearance-none pr-10 cursor-pointer
              ${error ? errorInputStyles : ''}
              ${className}
            `}
                        aria-invalid={!!error}
                        {...props}
                    >
                        {placeholder && (
                            <option value="" disabled>
                                {placeholder}
                            </option>
                        )}
                        {options.map((option) => (
                            <option key={option.value} value={option.value} disabled={option.disabled}>
                                {option.label}
                            </option>
                        ))}
                    </select>
                    <ChevronDown className="absolute right-4 top-1/2 -translate-y-1/2 w-5 h-5 text-gray-400 pointer-events-none" />
                </div>
                {error && (
                    <p className="flex items-center gap-1.5 text-sm text-red-400">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </p>
                )}
                {hint && !error && (
                    <p className="text-sm text-gray-500">{hint}</p>
                )}
            </div>
        );
    }
);

SelectInput.displayName = 'SelectInput';

// ============================================================================
// Checkbox
// ============================================================================

export interface CheckboxProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
    label?: string;
    description?: string;
}

export const Checkbox = forwardRef<HTMLInputElement, CheckboxProps>(
    ({ label, description, className = '', id, ...props }, ref) => {
        const generatedId = useId();
        const checkboxId = id || generatedId;

        return (
            <label htmlFor={checkboxId} className={`flex items-start gap-3 cursor-pointer group ${className}`}>
                <div className="relative flex-shrink-0 mt-0.5">
                    <input
                        ref={ref}
                        type="checkbox"
                        id={checkboxId}
                        className="peer sr-only"
                        {...props}
                    />
                    <div className="
            w-5 h-5 rounded border-2 border-white/10
            peer-checked:bg-primary-500 peer-checked:border-primary-500
            peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500/50
            peer-disabled:opacity-50 peer-disabled:cursor-not-allowed
            transition-colors group-hover:border-white/10
          ">
                        <Check className="w-full h-full text-white scale-0 peer-checked:scale-100 transition-transform" />
                    </div>
                    <Check className="
            absolute inset-0 w-full h-full text-white p-0.5
            opacity-0 scale-0 peer-checked:opacity-100 peer-checked:scale-100
            transition-all
          " />
                </div>
                {(label || description) && (
                    <div>
                        {label && <div className="text-sm font-medium text-white">{label}</div>}
                        {description && <div className="text-sm text-gray-400">{description}</div>}
                    </div>
                )}
            </label>
        );
    }
);

Checkbox.displayName = 'Checkbox';

// ============================================================================
// Radio Button
// ============================================================================

export interface RadioProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
    label?: string;
    description?: string;
}

export const Radio = forwardRef<HTMLInputElement, RadioProps>(
    ({ label, description, className = '', id, ...props }, ref) => {
        const generatedId = useId();
        const radioId = id || generatedId;

        return (
            <label htmlFor={radioId} className={`flex items-start gap-3 cursor-pointer group ${className}`}>
                <div className="relative flex-shrink-0 mt-0.5">
                    <input
                        ref={ref}
                        type="radio"
                        id={radioId}
                        className="peer sr-only"
                        {...props}
                    />
                    <div className="
            w-5 h-5 rounded-full border-2 border-white/10
            peer-checked:border-primary-500
            peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500/50
            peer-disabled:opacity-50 peer-disabled:cursor-not-allowed
            transition-colors group-hover:border-white/10
          " />
                    <div className="
            absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2
            w-2.5 h-2.5 rounded-full bg-primary-500
            scale-0 peer-checked:scale-100
            transition-transform
          " />
                </div>
                {(label || description) && (
                    <div>
                        {label && <div className="text-sm font-medium text-white">{label}</div>}
                        {description && <div className="text-sm text-gray-400">{description}</div>}
                    </div>
                )}
            </label>
        );
    }
);

Radio.displayName = 'Radio';

// ============================================================================
// Radio Group
// ============================================================================

export interface RadioGroupOption {
    value: string;
    label: string;
    description?: string;
    disabled?: boolean;
}

export interface RadioGroupProps {
    name: string;
    value?: string;
    onChange?: (value: string) => void;
    options: RadioGroupOption[];
    label?: string;
    error?: string;
    orientation?: 'horizontal' | 'vertical';
}

export const RadioGroup: React.FC<RadioGroupProps> = ({
    name,
    value,
    onChange,
    options,
    label,
    error,
    orientation = 'vertical',
}) => {
    return (
        <div className="space-y-2">
            {label && <div className="text-sm font-medium text-gray-300">{label}</div>}
            <div className={`flex ${orientation === 'vertical' ? 'flex-col gap-3' : 'flex-row flex-wrap gap-6'}`}>
                {options.map((option) => (
                    <Radio
                        key={option.value}
                        name={name}
                        value={option.value}
                        checked={value === option.value}
                        onChange={() => onChange?.(option.value)}
                        label={option.label}
                        description={option.description}
                        disabled={option.disabled}
                    />
                ))}
            </div>
            {error && (
                <p className="flex items-center gap-1.5 text-sm text-red-400">
                    <AlertCircle className="w-4 h-4" />
                    {error}
                </p>
            )}
        </div>
    );
};

// ============================================================================
// Switch/Toggle
// ============================================================================

export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
    label?: string;
    description?: string;
}

export const Switch = forwardRef<HTMLInputElement, SwitchProps>(
    ({ label, description, className = '', id, ...props }, ref) => {
        const generatedId = useId();
        const switchId = id || generatedId;

        return (
            <label htmlFor={switchId} className={`flex items-center justify-between gap-4 cursor-pointer ${className}`}>
                {(label || description) && (
                    <div className="flex-1">
                        {label && <div className="text-sm font-medium text-white">{label}</div>}
                        {description && <div className="text-sm text-gray-400">{description}</div>}
                    </div>
                )}
                <div className="relative flex-shrink-0">
                    <input
                        ref={ref}
                        type="checkbox"
                        id={switchId}
                        className="peer sr-only"
                        {...props}
                    />
                    <div className="
            w-11 h-6 rounded-full bg-dark-300
            peer-checked:bg-primary-500
            peer-focus-visible:ring-2 peer-focus-visible:ring-primary-500/50
            peer-disabled:opacity-50 peer-disabled:cursor-not-allowed
            transition-colors
          " />
                    <div className="
            absolute top-0.5 left-0.5 w-5 h-5 rounded-full bg-white
            shadow-sm transform transition-transform
            peer-checked:translate-x-5
          " />
                </div>
            </label>
        );
    }
);

Switch.displayName = 'Switch';

// ============================================================================
// Slider / Range Input
// ============================================================================

export interface SliderProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
    label?: string;
    showValue?: boolean;
    valueFormatter?: (value: number) => string;
}

export const Slider = forwardRef<HTMLInputElement, SliderProps>(
    ({ label, showValue = true, valueFormatter, className = '', id, value, min = 0, max = 100, ...props }, ref) => {
        const generatedId = useId();
        const sliderId = id || generatedId;
        const numValue = typeof value === 'number' ? value : Number(value) || 0;
        const percentage = ((numValue - Number(min)) / (Number(max) - Number(min))) * 100;

        return (
            <div className={`space-y-2 ${className}`}>
                {(label || showValue) && (
                    <div className="flex justify-between items-center">
                        {label && (
                            <label htmlFor={sliderId} className="text-sm font-medium text-gray-300">
                                {label}
                            </label>
                        )}
                        {showValue && (
                            <span className="text-sm text-primary-400 font-medium">
                                {valueFormatter ? valueFormatter(numValue) : numValue}
                            </span>
                        )}
                    </div>
                )}
                <div className="relative">
                    <input
                        ref={ref}
                        type="range"
                        id={sliderId}
                        value={value}
                        min={min}
                        max={max}
                        className="
              w-full h-2 bg-dark-300 rounded-full appearance-none cursor-pointer
              [&::-webkit-slider-thumb]:appearance-none
              [&::-webkit-slider-thumb]:w-5 [&::-webkit-slider-thumb]:h-5
              [&::-webkit-slider-thumb]:bg-primary-500 [&::-webkit-slider-thumb]:rounded-full
              [&::-webkit-slider-thumb]:shadow-lg [&::-webkit-slider-thumb]:cursor-grab
              [&::-webkit-slider-thumb]:transition-transform [&::-webkit-slider-thumb]:hover:scale-110
              [&::-moz-range-thumb]:w-5 [&::-moz-range-thumb]:h-5
              [&::-moz-range-thumb]:bg-primary-500 [&::-moz-range-thumb]:rounded-full
              [&::-moz-range-thumb]:border-0
              disabled:opacity-50 disabled:cursor-not-allowed
            "
                        style={{
                            background: `linear-gradient(to right, rgb(6 182 212) 0%, rgb(6 182 212) ${percentage}%, rgb(51 65 85) ${percentage}%, rgb(51 65 85) 100%)`,
                        }}
                        {...props}
                    />
                </div>
            </div>
        );
    }
);

Slider.displayName = 'Slider';

// ============================================================================
// Number Input with Stepper
// ============================================================================

export interface NumberInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
    label?: string;
    error?: string;
    step?: number;
    onIncrement?: () => void;
    onDecrement?: () => void;
}

export const NumberInput = forwardRef<HTMLInputElement, NumberInputProps>(
    ({ label, error, step = 1, onIncrement, onDecrement, className = '', id, ...props }, ref) => {
        const generatedId = useId();
        const inputId = id || generatedId;

        return (
            <div className="space-y-1.5">
                {label && (
                    <label htmlFor={inputId} className="block text-sm font-medium text-gray-300">
                        {label}
                    </label>
                )}
                <div className="flex">
                    <button
                        type="button"
                        onClick={onDecrement}
                        className="px-3 py-2 bg-dark-300 border border-white/10 rounded-l-xl text-white hover:bg-dark-300 transition-colors"
                        aria-label="Decrease"
                    >
                        -
                    </button>
                    <input
                        ref={ref}
                        type="number"
                        id={inputId}
                        step={step}
                        className={`
              flex-1 px-4 py-2 bg-dark-400/50 border-y border-white/10/50
              text-white text-center
              focus:outline-none focus:border-primary-500/50
              [appearance:textfield] [&::-webkit-outer-spin-button]:appearance-none [&::-webkit-inner-spin-button]:appearance-none
              ${error ? 'border-red-500/50' : ''}
              ${className}
            `}
                        {...props}
                    />
                    <button
                        type="button"
                        onClick={onIncrement}
                        className="px-3 py-2 bg-dark-300 border border-white/10 rounded-r-xl text-white hover:bg-dark-300 transition-colors"
                        aria-label="Increase"
                    >
                        +
                    </button>
                </div>
                {error && (
                    <p className="flex items-center gap-1.5 text-sm text-red-400">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </p>
                )}
            </div>
        );
    }
);

NumberInput.displayName = 'NumberInput';

// ============================================================================
// File Input
// ============================================================================

export interface FileInputProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'type'> {
    label?: string;
    hint?: string;
    error?: string;
    acceptText?: string;
    onFilesSelected?: (files: FileList) => void;
}

export const FileInput = forwardRef<HTMLInputElement, FileInputProps>(
    ({ label, hint, error, acceptText, onFilesSelected, className = '', id, ...props }, ref) => {
        const generatedId = useId();
        const inputId = id || generatedId;
        const [dragActive, setDragActive] = useState(false);

        const handleDrag = (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            if (e.type === 'dragenter' || e.type === 'dragover') {
                setDragActive(true);
            } else if (e.type === 'dragleave') {
                setDragActive(false);
            }
        };

        const handleDrop = (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setDragActive(false);
            if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
                onFilesSelected?.(e.dataTransfer.files);
            }
        };

        const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            if (e.target.files && e.target.files.length > 0) {
                onFilesSelected?.(e.target.files);
            }
        };

        return (
            <div className="space-y-1.5">
                {label && (
                    <label className="block text-sm font-medium text-gray-300">{label}</label>
                )}
                <div
                    onDragEnter={handleDrag}
                    onDragLeave={handleDrag}
                    onDragOver={handleDrag}
                    onDrop={handleDrop}
                    className={`
            relative border-2 border-dashed rounded-xl p-8 text-center transition-colors
            ${dragActive
                            ? 'border-primary-500 bg-primary-500/10'
                            : error
                                ? 'border-red-500/50 bg-red-500/5'
                                : 'border-white/10 hover:border-white/10 bg-dark-400/30'
                        }
            ${className}
          `}
                >
                    <input
                        ref={ref}
                        type="file"
                        id={inputId}
                        onChange={handleChange}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        {...props}
                    />
                    <div className="space-y-2">
                        <div className="mx-auto w-12 h-12 rounded-full bg-dark-300 flex items-center justify-center">
                            <svg className="w-6 h-6 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                            </svg>
                        </div>
                        <div>
                            <p className="text-white font-medium">
                                Drop files here or <span className="text-primary-400">browse</span>
                            </p>
                            {acceptText && (
                                <p className="text-sm text-gray-500 mt-1">{acceptText}</p>
                            )}
                        </div>
                    </div>
                </div>
                {error && (
                    <p className="flex items-center gap-1.5 text-sm text-red-400">
                        <AlertCircle className="w-4 h-4" />
                        {error}
                    </p>
                )}
                {hint && !error && (
                    <p className="text-sm text-gray-500">{hint}</p>
                )}
            </div>
        );
    }
);

FileInput.displayName = 'FileInput';

// ============================================================================
// Form Group - Utility wrapper for form sections
// ============================================================================

export interface FormGroupProps {
    children: React.ReactNode;
    title?: string;
    description?: string;
    className?: string;
}

export const FormGroup: React.FC<FormGroupProps> = ({
    children,
    title,
    description,
    className = '',
}) => {
    return (
        <fieldset className={`space-y-4 ${className}`}>
            {(title || description) && (
                <div className="space-y-1">
                    {title && <legend className="text-lg font-semibold text-white">{title}</legend>}
                    {description && <p className="text-sm text-gray-400">{description}</p>}
                </div>
            )}
            {children}
        </fieldset>
    );
};

export default TextInput;
