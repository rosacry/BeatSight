import { describe, it, expect } from 'vitest'
import type { HitObject, NoteDiff } from '../../../types/beatmap'
import { LANE_COLORS, LANE_LABELS } from '../../../types/beatmap'

describe('Beatmap Types', () => {
    describe('LANE_COLORS', () => {
        it('should have colors for all drum components', () => {
            const expectedComponents = [
                'kick',
                'snare',
                'hihat_closed',
                'hihat_open',
                'tom_high',
                'tom_mid',
                'tom_low',
                'ride',
                'crash',
                'china',
                'splash',
            ]

            for (const component of expectedComponents) {
                expect(LANE_COLORS[component as keyof typeof LANE_COLORS]).toBeDefined()
                expect(LANE_COLORS[component as keyof typeof LANE_COLORS]).toMatch(/^#[0-9a-f]{6}$/i)
            }
        })
    })

    describe('LANE_LABELS', () => {
        it('should have labels for all drum components', () => {
            const expectedComponents = [
                'kick',
                'snare',
                'hihat_closed',
                'hihat_open',
                'tom_high',
                'tom_mid',
                'tom_low',
                'ride',
                'crash',
                'china',
                'splash',
            ]

            for (const component of expectedComponents) {
                expect(LANE_LABELS[component as keyof typeof LANE_LABELS]).toBeDefined()
                expect(typeof LANE_LABELS[component as keyof typeof LANE_LABELS]).toBe('string')
            }
        })

        it('should have human-readable labels', () => {
            expect(LANE_LABELS.kick).toBe('Kick')
            expect(LANE_LABELS.snare).toBe('Snare')
            expect(LANE_LABELS.hihat_closed).toBe('HH (C)')
            expect(LANE_LABELS.hihat_open).toBe('HH (O)')
        })
    })

    describe('HitObject', () => {
        it('should represent a note correctly', () => {
            const note: HitObject = {
                id: 'note-1',
                time: 1000,
                component: 'kick',
                velocity: 0.9,
                lane: 3,
            }

            expect(note.id).toBe('note-1')
            expect(note.time).toBe(1000)
            expect(note.component).toBe('kick')
            expect(note.velocity).toBeGreaterThanOrEqual(0)
            expect(note.velocity).toBeLessThanOrEqual(1)
        })
    })

    describe('NoteDiff', () => {
        it('should represent an added note', () => {
            const diff: NoteDiff = {
                type: 'added',
                editedNote: {
                    id: 'note-new',
                    time: 2000,
                    component: 'snare',
                    velocity: 0.8,
                    lane: 2,
                },
            }

            expect(diff.type).toBe('added')
            expect(diff.editedNote).toBeDefined()
            expect(diff.originalNote).toBeUndefined()
        })

        it('should represent a removed note', () => {
            const diff: NoteDiff = {
                type: 'removed',
                originalNote: {
                    id: 'note-old',
                    time: 1500,
                    component: 'hihat_closed',
                    velocity: 0.7,
                    lane: 1,
                },
            }

            expect(diff.type).toBe('removed')
            expect(diff.originalNote).toBeDefined()
            expect(diff.editedNote).toBeUndefined()
        })

        it('should represent a modified note', () => {
            const diff: NoteDiff = {
                type: 'modified',
                originalNote: {
                    id: 'note-1',
                    time: 1000,
                    component: 'kick',
                    velocity: 0.9,
                    lane: 3,
                },
                editedNote: {
                    id: 'note-1',
                    time: 1050, // Moved 50ms forward
                    component: 'kick',
                    velocity: 0.9,
                    lane: 3,
                },
                timeDelta: 50,
                laneDelta: 0,
                velocityDelta: 0,
            }

            expect(diff.type).toBe('modified')
            expect(diff.timeDelta).toBe(50)
            expect(diff.laneDelta).toBe(0)
        })
    })
})
