/**
 * Form validation utilities.
 * Provides reusable validation functions and patterns.
 * @module lib/validation
 */

export interface ValidationResult {
    valid: boolean
    error?: string
}

export interface FieldValidation {
    required?: boolean | string
    minLength?: number | { value: number; message: string }
    maxLength?: number | { value: number; message: string }
    pattern?: RegExp | { value: RegExp; message: string }
    custom?: (value: string) => ValidationResult
}

/**
 * Common validation patterns
 */
export const patterns = {
    /** RFC 5322 compliant email pattern */
    email: /^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/,

    /** Username: alphanumeric, underscores, hyphens, 3-30 chars */
    username: /^[a-zA-Z0-9_-]{3,30}$/,

    /** Display name: letters, numbers, spaces, common punctuation */
    displayName: /^[\p{L}\p{N}\p{Zs}._-]{2,50}$/u,

    /** URL pattern */
    url: /^https?:\/\/(www\.)?[-a-zA-Z0-9@:%._+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b([-a-zA-Z0-9()@:%_+.~#?&//=]*)$/,

    /** UUID v4 pattern */
    uuid: /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i,
}

/**
 * Validate an email address
 */
export function validateEmail(email: string): ValidationResult {
    if (!email.trim()) {
        return { valid: false, error: 'Email is required' }
    }
    if (!patterns.email.test(email)) {
        return { valid: false, error: 'Please enter a valid email address' }
    }
    if (email.length > 254) {
        return { valid: false, error: 'Email is too long' }
    }
    return { valid: true }
}

/**
 * Validate a password with configurable requirements
 */
export interface PasswordRequirements {
    minLength?: number
    maxLength?: number
    requireUppercase?: boolean
    requireLowercase?: boolean
    requireNumber?: boolean
    requireSpecial?: boolean
}

const DEFAULT_PASSWORD_REQUIREMENTS: PasswordRequirements = {
    minLength: 8,
    maxLength: 128,
    requireUppercase: false,
    requireLowercase: false,
    requireNumber: false,
    requireSpecial: false,
}

export function validatePassword(
    password: string,
    requirements: PasswordRequirements = {}
): ValidationResult {
    const reqs = { ...DEFAULT_PASSWORD_REQUIREMENTS, ...requirements }

    if (!password) {
        return { valid: false, error: 'Password is required' }
    }

    if (reqs.minLength && password.length < reqs.minLength) {
        return { valid: false, error: `Password must be at least ${reqs.minLength} characters` }
    }

    if (reqs.maxLength && password.length > reqs.maxLength) {
        return { valid: false, error: `Password must be at most ${reqs.maxLength} characters` }
    }

    if (reqs.requireUppercase && !/[A-Z]/.test(password)) {
        return { valid: false, error: 'Password must contain at least one uppercase letter' }
    }

    if (reqs.requireLowercase && !/[a-z]/.test(password)) {
        return { valid: false, error: 'Password must contain at least one lowercase letter' }
    }

    if (reqs.requireNumber && !/\d/.test(password)) {
        return { valid: false, error: 'Password must contain at least one number' }
    }

    if (reqs.requireSpecial && !/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password)) {
        return { valid: false, error: 'Password must contain at least one special character' }
    }

    return { valid: true }
}

/**
 * Check password strength (0-4 scale)
 */
export function getPasswordStrength(password: string): {
    score: 0 | 1 | 2 | 3 | 4
    label: 'Very Weak' | 'Weak' | 'Fair' | 'Strong' | 'Very Strong'
    feedback: string[]
} {
    const feedback: string[] = []
    let score = 0

    if (!password) {
        return { score: 0, label: 'Very Weak', feedback: ['Enter a password'] }
    }

    // Length check
    if (password.length >= 8) score++
    else feedback.push('Use at least 8 characters')

    if (password.length >= 12) score++

    // Character variety
    if (/[A-Z]/.test(password) && /[a-z]/.test(password)) {
        score++
    } else {
        feedback.push('Use both uppercase and lowercase letters')
    }

    if (/\d/.test(password)) {
        score += 0.5
    } else {
        feedback.push('Add numbers')
    }

    if (/[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password)) {
        score += 0.5
    } else {
        feedback.push('Add special characters (!@#$...)')
    }

    // Common patterns penalty
    if (/^[a-z]+$/i.test(password) || /^\d+$/.test(password)) {
        score = Math.max(0, score - 1)
        feedback.push('Avoid using only letters or only numbers')
    }

    // Round score
    const finalScore = Math.min(4, Math.floor(score)) as 0 | 1 | 2 | 3 | 4

    const labels: Record<0 | 1 | 2 | 3 | 4, 'Very Weak' | 'Weak' | 'Fair' | 'Strong' | 'Very Strong'> = {
        0: 'Very Weak',
        1: 'Weak',
        2: 'Fair',
        3: 'Strong',
        4: 'Very Strong',
    }

    return { score: finalScore, label: labels[finalScore], feedback }
}

/**
 * Validate display name
 */
export function validateDisplayName(name: string): ValidationResult {
    if (!name.trim()) {
        return { valid: false, error: 'Display name is required' }
    }
    if (name.length < 2) {
        return { valid: false, error: 'Display name must be at least 2 characters' }
    }
    if (name.length > 50) {
        return { valid: false, error: 'Display name must be at most 50 characters' }
    }
    if (!patterns.displayName.test(name)) {
        return { valid: false, error: 'Display name contains invalid characters' }
    }
    return { valid: true }
}

/**
 * Validate URL
 */
export function validateUrl(url: string, required = false): ValidationResult {
    if (!url.trim()) {
        return required
            ? { valid: false, error: 'URL is required' }
            : { valid: true }
    }
    if (!patterns.url.test(url)) {
        return { valid: false, error: 'Please enter a valid URL' }
    }
    return { valid: true }
}

/**
 * Validate password confirmation matches
 */
export function validatePasswordMatch(password: string, confirm: string): ValidationResult {
    if (password !== confirm) {
        return { valid: false, error: 'Passwords do not match' }
    }
    return { valid: true }
}

/**
 * Generic field validator
 */
export function validateField(value: string, rules: FieldValidation): ValidationResult {
    const trimmed = value.trim()

    // Required check
    if (rules.required) {
        if (!trimmed) {
            const msg = typeof rules.required === 'string' ? rules.required : 'This field is required'
            return { valid: false, error: msg }
        }
    } else if (!trimmed) {
        // Not required and empty is valid
        return { valid: true }
    }

    // Min length
    if (rules.minLength) {
        const { value: min, message } = typeof rules.minLength === 'number'
            ? { value: rules.minLength, message: `Must be at least ${rules.minLength} characters` }
            : rules.minLength
        if (trimmed.length < min) {
            return { valid: false, error: message }
        }
    }

    // Max length
    if (rules.maxLength) {
        const { value: max, message } = typeof rules.maxLength === 'number'
            ? { value: rules.maxLength, message: `Must be at most ${rules.maxLength} characters` }
            : rules.maxLength
        if (trimmed.length > max) {
            return { valid: false, error: message }
        }
    }

    // Pattern
    if (rules.pattern) {
        const { value: pattern, message } = rules.pattern instanceof RegExp
            ? { value: rules.pattern, message: 'Invalid format' }
            : rules.pattern
        if (!pattern.test(trimmed)) {
            return { valid: false, error: message }
        }
    }

    // Custom validation
    if (rules.custom) {
        return rules.custom(trimmed)
    }

    return { valid: true }
}

/**
 * Sanitize input to prevent XSS
 */
export function sanitizeInput(input: string): string {
    return input
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;')
}

/**
 * Validate and sanitize a form data object
 */
export interface FormValidationSchema {
    [field: string]: FieldValidation
}

export interface FormValidationResult<T extends Record<string, string>> {
    valid: boolean
    errors: Partial<Record<keyof T, string>>
    sanitized: T
}

export function validateForm<T extends Record<string, string>>(
    data: T,
    schema: FormValidationSchema
): FormValidationResult<T> {
    const errors: Partial<Record<keyof T, string>> = {}
    const sanitized = { ...data } as T

    for (const [field, rules] of Object.entries(schema)) {
        if (field in data) {
            const result = validateField(data[field], rules)
            if (!result.valid && result.error) {
                errors[field as keyof T] = result.error
            }
            // Sanitize the value
            sanitized[field as keyof T] = sanitizeInput(data[field]) as T[keyof T]
        }
    }

    return {
        valid: Object.keys(errors).length === 0,
        errors,
        sanitized,
    }
}
