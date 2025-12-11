import { useEffect, useState, useCallback } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { TimelineEditor } from '../components/timeline'
import { Layout } from '../components/NavigationShell'
import { useDocumentTitle } from '../hooks/useDocumentTitle'
import { PageContentWrapper } from '@/components/ui/UnifiedTransitions'
import type { Beatmap, NoteEdit } from '../types/beatmap'
import { api } from '../lib/api'

interface MapEditPageParams {
    mapId: string
}

interface MapVersion {
    id: string
    map_id: string
    version_number: number
    bsm_content: Beatmap
    audio_url: string
    is_canonical: boolean
    created_at: string
}

type SubmitState = 'idle' | 'submitting' | 'success' | 'error'

export function MapEditPage() {
    const { mapId } = useParams<keyof MapEditPageParams>()
    const navigate = useNavigate()
    useDocumentTitle('edit beatmap')

    const [loading, setLoading] = useState(true)
    const [error, setError] = useState<string | null>(null)
    const [mapVersion, setMapVersion] = useState<MapVersion | null>(null)
    const [canonicalVersion, setCanonicalVersion] = useState<MapVersion | null>(null)
    const [editedBeatmap, setEditedBeatmap] = useState<Beatmap | null>(null)
    const [submitState, setSubmitState] = useState<SubmitState>('idle')
    const [submitError, setSubmitError] = useState<string | null>(null)
    const [comment, setComment] = useState('')

    // Fetch map data
    useEffect(() => {
        async function fetchMap() {
            if (!mapId) return

            setLoading(true)
            setError(null)

            try {
                // Fetch the map version to edit
                const response = await api.get<MapVersion>(`/maps/${mapId}/latest`)
                setMapVersion(response)
                setEditedBeatmap(response.bsm_content)

                // If this is not the canonical version, also fetch canonical for diff
                if (!response.is_canonical) {
                    try {
                        const canonicalResponse = await api.get<MapVersion>(`/maps/${mapId}/canonical`)
                        setCanonicalVersion(canonicalResponse)
                    } catch {
                        // Canonical version might not exist yet
                    }
                }
            } catch (err) {
                setError(err instanceof Error ? err.message : 'Failed to load map')
            } finally {
                setLoading(false)
            }
        }

        fetchMap()
    }, [mapId])

    // Handle beatmap changes
    const handleBeatmapChange = useCallback((beatmap: Beatmap) => {
        setEditedBeatmap(beatmap)
    }, [])

    // Handle edit submission
    const handleSubmit = useCallback(
        async (edits: NoteEdit[]) => {
            if (!mapId || !editedBeatmap || edits.length === 0) return

            setSubmitState('submitting')
            setSubmitError(null)

            try {
                // Create a map edit proposal
                await api.post('/map-edit-proposals', {
                    map_id: mapId,
                    proposed_changes: {
                        edits,
                        bsm_content: editedBeatmap,
                    },
                    comment: comment || 'Submitted via Timeline Editor',
                    edit_type: 'timing_fix', // or 'note_correction', 'lane_adjustment', etc.
                })

                setSubmitState('success')

                // Navigate to the proposal detail or back to the map
                setTimeout(() => {
                    navigate(`/maps/${mapId}`)
                }, 2000)
            } catch (err) {
                setSubmitState('error')
                setSubmitError(err instanceof Error ? err.message : 'Failed to submit proposal')
            }
        },
        [mapId, editedBeatmap, comment, navigate]
    )

    if (loading) {
        return (
            <Layout>
                <PageContentWrapper isLoading={true}>
                    <div className="flex h-96 items-center justify-center">
                        <div className="text-center">
                            <div className="mb-4 h-8 w-8 animate-spin rounded-full border-4 border-orange-500 border-t-transparent" />
                            <p className="text-gray-400">Loading map...</p>
                        </div>
                    </div>
                </PageContentWrapper>
            </Layout>
        )
    }

    if (error || !mapVersion || !editedBeatmap) {
        return (
            <Layout>
                <PageContentWrapper>
                    <div className="flex h-96 flex-col items-center justify-center gap-4">
                        <div className="text-center">
                            <h2 className="mb-2 text-xl font-semibold text-red-400">Failed to Load Map</h2>
                            <p className="text-gray-400">{error || 'Map not found'}</p>
                        </div>
                        <Link
                            to="/library"
                            className="rounded bg-dark-300 px-4 py-2 text-sm hover:bg-gray-600"
                        >
                            Back to Library
                        </Link>
                    </div>
                </PageContentWrapper>
            </Layout>
        )
    }

    return (
        <Layout>
            <PageContentWrapper>
                {/* Header */}
                <div className="flex items-start justify-between">
                    <div>
                        <div className="mb-1 flex items-center gap-2">
                            <Link to="/library" className="text-sm text-gray-400 hover:text-gray-300">
                                Library
                            </Link>
                            <span className="text-gray-600">/</span>
                            <Link
                                to={`/maps/${mapId}`}
                                className="text-sm text-gray-400 hover:text-gray-300"
                            >
                                {editedBeatmap.metadata.title}
                            </Link>
                            <span className="text-gray-600">/</span>
                            <span className="text-sm text-gray-300">Edit</span>
                        </div>
                        <h1 className="text-2xl font-bold">
                            {editedBeatmap.metadata.title}
                        </h1>
                        <p className="text-gray-400">
                            by {editedBeatmap.metadata.artist} • {editedBeatmap.timing.bpm} BPM
                        </p>
                    </div>

                    <div className="flex items-center gap-3">
                        <Link
                            to={`/maps/${mapId}`}
                            className="rounded bg-dark-300 px-4 py-2 text-sm hover:bg-gray-600"
                        >
                            Cancel
                        </Link>
                    </div>
                </div>

                {/* Submit status banner */}
                {submitState === 'success' && (
                    <div className="rounded-lg bg-green-900/50 border border-green-700 p-4">
                        <p className="text-green-400">
                            ✓ Your edit proposal has been submitted for review! Redirecting...
                        </p>
                    </div>
                )}

                {submitState === 'error' && (
                    <div className="rounded-lg bg-red-900/50 border border-red-700 p-4">
                        <p className="text-red-400">
                            ✗ Failed to submit: {submitError}
                        </p>
                    </div>
                )}

                {/* Comment input */}
                <div className="rounded-lg bg-dark-400 p-4">
                    <label className="mb-2 block text-sm font-medium text-gray-300">
                        Edit Comment (optional)
                    </label>
                    <textarea
                        value={comment}
                        onChange={(e) => setComment(e.target.value)}
                        placeholder="Describe what you changed and why..."
                        className="w-full rounded bg-dark-300 px-3 py-2 text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-orange-500"
                        rows={2}
                    />
                </div>

                {/* Timeline Editor */}
                <TimelineEditor
                    beatmap={editedBeatmap}
                    comparisonBeatmap={canonicalVersion?.bsm_content}
                    audioUrl={mapVersion.audio_url}
                    onBeatmapChange={handleBeatmapChange}
                    onSubmit={handleSubmit}
                    showDiff={!!canonicalVersion}
                />

                {/* Help text */}
                <div className="rounded-lg bg-dark-400/50 p-4 text-sm text-gray-400">
                    <h3 className="mb-2 font-medium text-gray-300">How to Edit</h3>
                    <ul className="list-inside list-disc space-y-1">
                        <li>Click on notes to select them</li>
                        <li>Drag notes to move them in time or across lanes</li>
                        <li>Press Delete to remove selected notes</li>
                        <li>Use Ctrl+Z / Ctrl+Y to undo/redo</li>
                        <li>Enable "Show Diff" to see changes compared to the canonical version</li>
                        <li>Click "Submit Edits" when done to create a proposal for verifier review</li>
                    </ul>
                </div>
            </PageContentWrapper>
        </Layout>
    )
}
