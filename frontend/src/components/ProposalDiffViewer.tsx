/**
 * ProposalDiffViewer Component
 * 
 * Displays a user-friendly visualization of beatmap edit proposals,
 * showing the changes proposed by community members for verifier review.
 */

import { useState } from 'react'

// Types matching backend diff_payload structure
interface Edit {
    time?: number
    lane?: number
    type?: string
    old_value?: unknown
    new_value?: unknown
    action?: 'add' | 'remove' | 'modify'
}

interface DiffPayload {
    edit_type: string
    edit_count: number
    edits: Edit[]
    bsm_content?: string
    comment: string
}

interface ProposalDiffViewerProps {
    diffPayload: DiffPayload
    className?: string
}

// Format edit type for display
function formatEditType(editType: string): string {
    return editType
        .split('_')
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(' ')
}

// Format time in milliseconds to readable format (mm:ss.xxx)
function formatTime(timeMs: number): string {
    const minutes = Math.floor(timeMs / 60000)
    const seconds = ((timeMs % 60000) / 1000).toFixed(3)
    return `${minutes}:${seconds.padStart(6, '0')}`
}

// Get action icon and color
function getActionStyle(action?: string): { icon: string; bgColor: string; textColor: string } {
    switch (action) {
        case 'add':
            return { icon: '+', bgColor: 'bg-green-100', textColor: 'text-green-800' }
        case 'remove':
            return { icon: '-', bgColor: 'bg-red-100', textColor: 'text-red-800' }
        case 'modify':
        default:
            return { icon: '~', bgColor: 'bg-yellow-100', textColor: 'text-yellow-800' }
    }
}

// Individual edit row component
function EditRow({ edit, index }: { edit: Edit; index: number }) {
    const style = getActionStyle(edit.action)

    return (
        <div className={`flex items-center gap-3 p-2 rounded ${style.bgColor} text-sm`}>
            <span className={`font-mono font-bold ${style.textColor} w-6 text-center`}>
                {style.icon}
            </span>
            <span className="text-gray-600 w-8">#{index + 1}</span>

            {edit.time !== undefined && (
                <span className="font-mono bg-white px-2 py-0.5 rounded text-gray-700">
                    {formatTime(edit.time)}
                </span>
            )}

            {edit.lane !== undefined && (
                <span className="text-gray-600">
                    Lane {edit.lane}
                </span>
            )}

            {edit.type && (
                <span className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded text-xs">
                    {edit.type}
                </span>
            )}

            {edit.old_value !== undefined && edit.new_value !== undefined && (
                <span className="text-gray-500">
                    <code className="bg-red-50 px-1 rounded line-through">
                        {JSON.stringify(edit.old_value)}
                    </code>
                    {' → '}
                    <code className="bg-green-50 px-1 rounded">
                        {JSON.stringify(edit.new_value)}
                    </code>
                </span>
            )}
        </div>
    )
}

export function ProposalDiffViewer({ diffPayload, className = '' }: ProposalDiffViewerProps) {
    const [showRawJson, setShowRawJson] = useState(false)
    const [showBsmContent, setShowBsmContent] = useState(false)

    const { edit_type, edit_count, edits, bsm_content, comment } = diffPayload

    // Group edits by action type
    const addedCount = edits.filter(e => e.action === 'add').length
    const removedCount = edits.filter(e => e.action === 'remove').length
    const modifiedCount = edits.filter(e => e.action === 'modify' || !e.action).length

    return (
        <div className={`space-y-4 ${className}`}>
            {/* Header with edit type and summary */}
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                    <span className="bg-purple-100 text-purple-800 px-3 py-1 rounded-full text-sm font-medium">
                        {formatEditType(edit_type)}
                    </span>
                    <span className="text-gray-600">
                        {edit_count} change{edit_count !== 1 ? 's' : ''}
                    </span>
                </div>

                {/* Quick stats */}
                <div className="flex items-center gap-2 text-sm">
                    {addedCount > 0 && (
                        <span className="bg-green-100 text-green-700 px-2 py-0.5 rounded">
                            +{addedCount}
                        </span>
                    )}
                    {removedCount > 0 && (
                        <span className="bg-red-100 text-red-700 px-2 py-0.5 rounded">
                            -{removedCount}
                        </span>
                    )}
                    {modifiedCount > 0 && (
                        <span className="bg-yellow-100 text-yellow-700 px-2 py-0.5 rounded">
                            ~{modifiedCount}
                        </span>
                    )}
                </div>
            </div>

            {/* Comment from proposer */}
            {comment && (
                <div className="bg-gray-50 border-l-4 border-gray-300 p-3 rounded-r">
                    <p className="text-sm text-gray-600 italic">"{comment}"</p>
                    <p className="text-xs text-gray-400 mt-1">— Proposer's notes</p>
                </div>
            )}

            {/* Edit list */}
            <div className="space-y-2">
                <h4 className="text-sm font-medium text-gray-700">Changes:</h4>
                <div className="space-y-1.5 max-h-64 overflow-y-auto">
                    {edits.slice(0, 20).map((edit, index) => (
                        <EditRow key={index} edit={edit} index={index} />
                    ))}

                    {edits.length > 20 && (
                        <div className="text-center text-sm text-gray-500 py-2">
                            ... and {edits.length - 20} more changes
                        </div>
                    )}
                </div>
            </div>

            {/* Toggle buttons for additional views */}
            <div className="flex gap-2 border-t pt-4">
                <button
                    onClick={() => setShowRawJson(prev => !prev)}
                    className="text-sm text-blue-600 hover:underline"
                >
                    {showRawJson ? 'Hide' : 'Show'} Raw JSON
                </button>

                {bsm_content && (
                    <button
                        onClick={() => setShowBsmContent(prev => !prev)}
                        className="text-sm text-blue-600 hover:underline"
                    >
                        {showBsmContent ? 'Hide' : 'View'} Full Beatmap
                    </button>
                )}
            </div>

            {/* Raw JSON view */}
            {showRawJson && (
                <div className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">
                    <pre className="text-xs">
                        {JSON.stringify({ edit_type, edit_count, edits }, null, 2)}
                    </pre>
                </div>
            )}

            {/* Full BSM content view */}
            {showBsmContent && bsm_content && (
                <div className="bg-gray-900 text-gray-100 p-4 rounded-lg overflow-x-auto">
                    <pre className="text-xs whitespace-pre-wrap">
                        {typeof bsm_content === 'string'
                            ? bsm_content.slice(0, 5000) + (bsm_content.length > 5000 ? '\n... (truncated)' : '')
                            : JSON.stringify(bsm_content, null, 2).slice(0, 5000)
                        }
                    </pre>
                </div>
            )}
        </div>
    )
}

export type { DiffPayload, Edit }
