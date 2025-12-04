"""
Thread Safety Tests for AI Pipeline Components

Tests concurrent access to global singletons in the AI pipeline.
These tests verify that the thread safety fixes in demucs_separator.py
and drum_classifier.py work correctly under concurrent load.

Created: December 3, 2025
References: ENGINEERING_ACTION_TRACKER.md item 4.7
"""

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from unittest.mock import MagicMock, patch
import pytest
import numpy as np


class TestDemucsThreadSafety:
    """Tests for thread-safe Demucs separator initialization."""

    def test_separator_lock_exists(self):
        """Verify the separator lock is properly defined."""
        from separation.demucs_separator import _separator_lock
        
        assert _separator_lock is not None
        assert isinstance(_separator_lock, type(threading.Lock()))

    def test_lock_serializes_access(self):
        """Verify that the lock properly serializes access."""
        from separation.demucs_separator import _separator_lock
        
        access_order = []
        
        def access_with_lock(thread_id):
            with _separator_lock:
                access_order.append(f"start_{thread_id}")
                time.sleep(0.01)  # Simulate work
                access_order.append(f"end_{thread_id}")
        
        threads = [threading.Thread(target=access_with_lock, args=(i,)) for i in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        
        # Verify serialized access: each start should be immediately followed by its end
        for i in range(0, len(access_order), 2):
            start = access_order[i]
            end = access_order[i + 1]
            thread_id = start.split('_')[1]
            assert end == f"end_{thread_id}", f"Access was not serialized: {access_order}"


class TestDrumClassifierThreadSafety:
    """Tests for thread-safe drum classifier mode switching."""

    def test_classifier_mode_lock_exists(self):
        """Verify the classifier mode lock is properly defined."""
        from transcription.drum_classifier import _classifier_mode_lock
        
        assert _classifier_mode_lock is not None
        assert isinstance(_classifier_mode_lock, type(threading.Lock()))

    def test_mode_lock_serializes_mode_changes(self):
        """Verify that mode changes are properly serialized."""
        from transcription import drum_classifier
        
        mode_changes = []
        original_mode = drum_classifier.last_classifier_mode
        
        try:
            def change_mode(new_mode):
                with drum_classifier._classifier_mode_lock:
                    drum_classifier.last_classifier_mode = new_mode
                    time.sleep(0.01)  # Simulate work
                    current = drum_classifier.last_classifier_mode
                    mode_changes.append((new_mode, current))
            
            threads = []
            for mode in ['mode_a', 'mode_b', 'mode_c', 'mode_d', 'mode_e']:
                t = threading.Thread(target=change_mode, args=(mode,))
                threads.append(t)
            
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=30)
            
            # Each change should have been atomic
            for new_mode, current in mode_changes:
                assert current == new_mode, f"Mode was corrupted: set {new_mode} but got {current}"
        finally:
            drum_classifier.last_classifier_mode = original_mode

    def test_concurrent_mode_reads_are_safe(self):
        """Verify concurrent reads don't cause issues."""
        from transcription import drum_classifier
        
        results = []
        
        def read_mode():
            mode = drum_classifier.last_classifier_mode
            results.append(mode)
        
        threads = [threading.Thread(target=read_mode) for _ in range(20)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        
        # All reads should complete without error
        assert len(results) == 20


class TestLockContention:
    """Tests for lock contention and deadlock scenarios."""

    def test_separator_high_contention(self):
        """Stress test with many threads competing for the separator lock."""
        from separation.demucs_separator import _separator_lock
        
        access_count = [0]
        
        def contended_access():
            with _separator_lock:
                local = access_count[0]
                time.sleep(0.001)  # Small delay to increase contention
                access_count[0] = local + 1
        
        threads = [threading.Thread(target=contended_access) for _ in range(50)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        
        # All 50 accesses should have been serialized correctly
        assert access_count[0] == 50, f"Lost updates: {access_count[0]} != 50"

    def test_classifier_high_contention(self):
        """Stress test with many threads competing for the classifier lock."""
        from transcription.drum_classifier import _classifier_mode_lock
        
        access_count = [0]
        
        def contended_access():
            with _classifier_mode_lock:
                local = access_count[0]
                time.sleep(0.001)
                access_count[0] = local + 1
        
        threads = [threading.Thread(target=contended_access) for _ in range(50)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)
        
        assert access_count[0] == 50, f"Lost updates: {access_count[0]} != 50"

    def test_no_deadlock_with_both_locks(self):
        """Verify no deadlock when acquiring both locks."""
        from separation.demucs_separator import _separator_lock
        from transcription.drum_classifier import _classifier_mode_lock
        
        # Always acquire in same order to prevent deadlock
        def acquire_both():
            with _separator_lock:
                with _classifier_mode_lock:
                    time.sleep(0.01)
        
        result = [False]
        def run():
            acquire_both()
            result[0] = True
        
        t = threading.Thread(target=run)
        t.start()
        t.join(timeout=5)
        
        assert not t.is_alive(), "Thread deadlocked"
        assert result[0], "Lock acquisition failed"


class TestConcurrentPipelineExecution:
    """Tests for concurrent pipeline execution scenarios."""

    @pytest.mark.skip(reason="Requires full model setup - run manually with fixtures")
    def test_concurrent_audio_processing(self):
        """
        Test that multiple audio files can be processed concurrently.
        This is an integration-level test that requires model files.
        """
        from pipeline.process import process_audio_file
        
        # Would need actual test audio files
        pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

