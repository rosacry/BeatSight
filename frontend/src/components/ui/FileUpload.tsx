// Copyright (c) BeatSight. Licensed under the MIT Licence.
// See the LICENCE file in the repository root for full licence text.

import * as React from 'react';
import { cva, type VariantProps } from 'class-variance-authority';
import { cn } from '../../lib/utils';

const fileUploadVariants = cva(
    'relative flex flex-col items-center justify-center rounded-lg border-2 border-dashed transition-all duration-200',
    {
        variants: {
            variant: {
                default: 'border-white/10 bg-dark-500/50 hover:border-primary/50 hover:bg-dark-400/50',
                success: 'border-green-500 bg-green-500/10',
                error: 'border-red-500 bg-red-500/10',
            },
            size: {
                sm: 'min-h-32 p-4',
                md: 'min-h-48 p-6',
                lg: 'min-h-64 p-8',
            },
        },
        defaultVariants: {
            variant: 'default',
            size: 'md',
        },
    }
);

export interface FileUploadProps
    extends Omit<React.HTMLAttributes<HTMLDivElement>, 'onDrop' | 'onError'>,
    VariantProps<typeof fileUploadVariants> {
    /** Accepted file types (e.g., '.mp3,.wav,audio/*') */
    accept?: string;
    /** Maximum file size in bytes */
    maxSize?: number;
    /** Maximum number of files */
    maxFiles?: number;
    /** Whether multiple files are allowed */
    multiple?: boolean;
    /** Whether the upload is disabled */
    disabled?: boolean;
    /** Callback when files are selected/dropped */
    onFilesSelected?: (files: File[]) => void;
    /** Callback when file validation fails */
    onValidationError?: (error: string) => void;
    /** Custom label text */
    label?: string;
    /** Custom description text */
    description?: string;
    /** Show file preview */
    showPreview?: boolean;
}

export interface FilePreviewProps {
    file: File;
    onRemove?: () => void;
}

// Icons
const UploadIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg
        className={className}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
    >
        <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
        <polyline points="17 8 12 3 7 8" />
        <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
);

const MusicIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg
        className={className}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
    >
        <path d="M9 18V5l12-2v13" />
        <circle cx="6" cy="18" r="3" />
        <circle cx="18" cy="16" r="3" />
    </svg>
);

const FileIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg
        className={className}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
    >
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
    </svg>
);

const XIcon: React.FC<{ className?: string }> = ({ className }) => (
    <svg
        className={className}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
    >
        <line x1="18" y1="6" x2="6" y2="18" />
        <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
);

/**
 * FilePreview - Displays a preview of an uploaded file
 */
export const FilePreview: React.FC<FilePreviewProps> = ({ file, onRemove }) => {
    const [preview, setPreview] = React.useState<string | null>(null);

    React.useEffect(() => {
        if (file.type.startsWith('image/')) {
            const reader = new FileReader();
            reader.onload = (e) => setPreview(e.target?.result as string);
            reader.readAsDataURL(file);
        }
        return () => setPreview(null);
    }, [file]);

    const formatFileSize = (bytes: number): string => {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    };

    const isAudio = file.type.startsWith('audio/');
    const isImage = file.type.startsWith('image/');

    return (
        <div className="flex items-center gap-3 p-3 bg-dark-400/50 rounded-lg border border-white/10">
            {/* Icon/Preview */}
            <div className="flex-shrink-0 w-12 h-12 rounded-lg bg-dark-500 flex items-center justify-center overflow-hidden">
                {isImage && preview ? (
                    <img src={preview} alt={file.name} className="w-full h-full object-cover" />
                ) : isAudio ? (
                    <MusicIcon className="w-6 h-6 text-primary" />
                ) : (
                    <FileIcon className="w-6 h-6 text-gray-400" />
                )}
            </div>

            {/* File Info */}
            <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-white truncate">{file.name}</p>
                <p className="text-xs text-gray-400">{formatFileSize(file.size)}</p>
            </div>

            {/* Remove Button */}
            {onRemove && (
                <button
                    type="button"
                    onClick={onRemove}
                    className="flex-shrink-0 p-1 rounded-full hover:bg-dark-300 transition-colors"
                >
                    <XIcon className="w-4 h-4 text-gray-400" />
                </button>
            )}
        </div>
    );
};

/**
 * FileUpload - Drag and drop file upload component
 */
export const FileUpload = React.forwardRef<HTMLDivElement, FileUploadProps>(
    (
        {
            className,
            variant,
            size,
            accept,
            maxSize = 100 * 1024 * 1024, // 100MB default
            maxFiles = 1,
            multiple = false,
            disabled = false,
            onFilesSelected,
            onValidationError,
            label = 'Drag and drop files here',
            description,
            showPreview = true,
            ...props
        },
        ref
    ) => {
        const [isDragOver, setIsDragOver] = React.useState(false);
        const [files, setFiles] = React.useState<File[]>([]);
        const [uploadVariant, setUploadVariant] = React.useState<'default' | 'success' | 'error'>(
            variant as 'default' | 'success' | 'error' || 'default'
        );
        const inputRef = React.useRef<HTMLInputElement>(null);

        const validateFile = (file: File): string | null => {
            // Check file size
            if (file.size > maxSize) {
                return `File "${file.name}" exceeds maximum size of ${formatBytes(maxSize)}`;
            }

            // Check file type
            if (accept) {
                const acceptedTypes = accept.split(',').map((t) => t.trim().toLowerCase());
                const fileExtension = '.' + file.name.split('.').pop()?.toLowerCase();
                const fileType = file.type.toLowerCase();

                const isAccepted = acceptedTypes.some((accepted) => {
                    if (accepted.startsWith('.')) {
                        return fileExtension === accepted;
                    }
                    if (accepted.endsWith('/*')) {
                        return fileType.startsWith(accepted.replace('/*', '/'));
                    }
                    return fileType === accepted;
                });

                if (!isAccepted) {
                    return `File "${file.name}" has an unsupported type`;
                }
            }

            return null;
        };

        const formatBytes = (bytes: number): string => {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
        };

        const handleFiles = (newFiles: FileList | null) => {
            if (!newFiles || disabled) return;

            const fileArray = Array.from(newFiles);
            const validFiles: File[] = [];
            const errors: string[] = [];

            for (const file of fileArray) {
                if (validFiles.length + files.length >= maxFiles) {
                    errors.push(`Maximum of ${maxFiles} files allowed`);
                    break;
                }

                const error = validateFile(file);
                if (error) {
                    errors.push(error);
                } else {
                    validFiles.push(file);
                }
            }

            if (errors.length > 0) {
                setUploadVariant('error');
                onValidationError?.(errors.join('\n'));
                setTimeout(() => setUploadVariant('default'), 2000);
            }

            if (validFiles.length > 0) {
                const updatedFiles = multiple ? [...files, ...validFiles] : validFiles;
                setFiles(updatedFiles);
                setUploadVariant('success');
                onFilesSelected?.(updatedFiles);
                setTimeout(() => setUploadVariant('default'), 1000);
            }
        };

        const handleDragOver = (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            if (!disabled) setIsDragOver(true);
        };

        const handleDragLeave = (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragOver(false);
        };

        const handleDrop = (e: React.DragEvent) => {
            e.preventDefault();
            e.stopPropagation();
            setIsDragOver(false);
            handleFiles(e.dataTransfer.files);
        };

        const handleClick = () => {
            if (!disabled) inputRef.current?.click();
        };

        const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
            handleFiles(e.target.files);
            // Reset input value to allow selecting the same file again
            e.target.value = '';
        };

        const handleRemoveFile = (index: number) => {
            const updatedFiles = files.filter((_, i) => i !== index);
            setFiles(updatedFiles);
            onFilesSelected?.(updatedFiles);
        };

        const defaultDescription =
            description ||
            `${accept ? `Supported formats: ${accept}` : 'All file types supported'} • Max ${formatBytes(maxSize)}`;

        return (
            <div className="w-full space-y-3">
                <div
                    ref={ref}
                    className={cn(
                        fileUploadVariants({ variant: uploadVariant, size }),
                        isDragOver && 'border-primary bg-primary/10 scale-[1.02]',
                        disabled && 'opacity-50 cursor-not-allowed',
                        !disabled && 'cursor-pointer',
                        className
                    )}
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={handleClick}
                    {...props}
                >
                    <input
                        ref={inputRef}
                        type="file"
                        accept={accept}
                        multiple={multiple}
                        disabled={disabled}
                        onChange={handleChange}
                        className="hidden"
                    />

                    {/* Upload Icon */}
                    <div
                        className={cn(
                            'p-4 rounded-full mb-4 transition-all',
                            uploadVariant === 'success'
                                ? 'bg-green-500/20'
                                : uploadVariant === 'error'
                                    ? 'bg-red-500/20'
                                    : 'bg-dark-400'
                        )}
                    >
                        <UploadIcon
                            className={cn(
                                'w-8 h-8 transition-all',
                                uploadVariant === 'success'
                                    ? 'text-green-500'
                                    : uploadVariant === 'error'
                                        ? 'text-red-500'
                                        : 'text-gray-400',
                                isDragOver && 'text-primary scale-110'
                            )}
                        />
                    </div>

                    {/* Label */}
                    <p
                        className={cn(
                            'text-base font-medium text-center transition-colors',
                            uploadVariant === 'success'
                                ? 'text-green-400'
                                : uploadVariant === 'error'
                                    ? 'text-red-400'
                                    : 'text-gray-300'
                        )}
                    >
                        {uploadVariant === 'success'
                            ? 'Upload complete!'
                            : uploadVariant === 'error'
                                ? 'Upload failed'
                                : label}
                    </p>

                    {/* Description */}
                    <p className="text-sm text-gray-500 text-center mt-2">{defaultDescription}</p>

                    {/* Or divider with browse button */}
                    <div className="flex items-center gap-4 mt-4">
                        <span className="text-xs text-gray-600">or</span>
                        <span className="text-sm text-primary hover:underline">Browse files</span>
                    </div>
                </div>

                {/* File Previews */}
                {showPreview && files.length > 0 && (
                    <div className="space-y-2">
                        {files.map((file, index) => (
                            <FilePreview key={`${file.name}-${index}`} file={file} onRemove={() => handleRemoveFile(index)} />
                        ))}
                    </div>
                )}
            </div>
        );
    }
);
FileUpload.displayName = 'FileUpload';

/**
 * AudioFileUpload - Specialized file upload for audio files
 */
export interface AudioFileUploadProps extends Omit<FileUploadProps, 'accept'> {
    /** Accepted audio formats */
    audioFormats?: string[];
}

export const AudioFileUpload = React.forwardRef<HTMLDivElement, AudioFileUploadProps>(
    ({ audioFormats = ['.mp3', '.wav', '.ogg', '.flac', '.m4a'], label = 'Drop audio files here', ...props }, ref) => {
        return (
            <FileUpload
                ref={ref}
                accept={[...audioFormats, 'audio/*'].join(',')}
                label={label}
                description={`Supported formats: ${audioFormats.join(', ')}`}
                {...props}
            />
        );
    }
);
AudioFileUpload.displayName = 'AudioFileUpload';

/**
 * UploadProgress - Progress indicator for file uploads
 */
export interface UploadProgressProps {
    /** Progress value (0-100) */
    progress: number;
    /** File name */
    fileName?: string;
    /** Upload status */
    status?: 'uploading' | 'processing' | 'complete' | 'error';
    /** Error message (when status is 'error') */
    errorMessage?: string;
    /** Callback when cancel is clicked */
    onCancel?: () => void;
    /** Callback when retry is clicked */
    onRetry?: () => void;
}

export const UploadProgress: React.FC<UploadProgressProps> = ({
    progress,
    fileName,
    status = 'uploading',
    errorMessage,
    onCancel,
    onRetry,
}) => {
    const getStatusColor = () => {
        switch (status) {
            case 'complete':
                return 'bg-green-500';
            case 'error':
                return 'bg-red-500';
            case 'processing':
                return 'bg-yellow-500';
            default:
                return 'bg-primary';
        }
    };

    const getStatusText = () => {
        switch (status) {
            case 'complete':
                return 'Complete';
            case 'error':
                return errorMessage || 'Upload failed';
            case 'processing':
                return 'Processing...';
            default:
                return `${progress}%`;
        }
    };

    return (
        <div className="w-full p-4 bg-dark-400/50 rounded-lg border border-white/10">
            <div className="flex items-center justify-between mb-2">
                {fileName && <span className="text-sm font-medium text-white truncate">{fileName}</span>}
                <span className={cn('text-xs', status === 'error' ? 'text-red-400' : 'text-gray-400')}>{getStatusText()}</span>
            </div>

            {/* Progress bar */}
            <div className="h-2 bg-dark-300 rounded-full overflow-hidden">
                <div
                    className={cn('h-full transition-all duration-300 rounded-full', getStatusColor())}
                    style={{ width: `${progress}%` }}
                />
            </div>

            {/* Actions */}
            {(onCancel || onRetry) && (
                <div className="flex justify-end gap-2 mt-2">
                    {status === 'error' && onRetry && (
                        <button onClick={onRetry} className="text-xs text-primary hover:underline">
                            Retry
                        </button>
                    )}
                    {status !== 'complete' && onCancel && (
                        <button onClick={onCancel} className="text-xs text-gray-400 hover:text-white">
                            Cancel
                        </button>
                    )}
                </div>
            )}
        </div>
    );
};

export default FileUpload;
