"""Tests for state machine utilities in app/utils/state_machine.py."""

from __future__ import annotations

import asyncio
from enum import Enum

import pytest

from app.utils.state_machine import (
    # Core classes
    StateMachine,
    AsyncStateMachine,
    TransitionRecord,
    TransitionError,
    GuardError,
    # Workflow
    Workflow,
    WorkflowStep,
    WorkflowContext,
    # Decorators and utilities
    transition_method,
    async_transition_method,
    # Factory functions
    create_state_machine,
    create_async_state_machine,
    create_workflow,
)


# Test state enums
class OrderState(Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    PROCESSING = "processing"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"


class TaskState(Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    REVIEW = "review"
    DONE = "done"


class TestTransitionRecord:
    """Tests for TransitionRecord class."""

    def test_transition_record_creation(self):
        """Test creating a transition record."""
        record = TransitionRecord(
            from_state=OrderState.PENDING,
            to_state=OrderState.CONFIRMED,
            event="confirm",
            metadata={"user_id": 123},
        )

        assert record.from_state == OrderState.PENDING
        assert record.to_state == OrderState.CONFIRMED
        assert record.event == "confirm"
        assert record.metadata == {"user_id": 123}
        assert record.timestamp is not None

    def test_transition_record_to_dict(self):
        """Test transition record serialization."""
        record = TransitionRecord(
            from_state=OrderState.PENDING,
            to_state=OrderState.CONFIRMED,
        )

        data = record.to_dict()
        assert "from_state" in data
        assert "to_state" in data
        assert "timestamp" in data


class TestStateMachine:
    """Tests for StateMachine class."""

    def test_initial_state(self):
        """Test state machine initializes with correct state."""
        sm = StateMachine(OrderState.PENDING)
        assert sm.state == OrderState.PENDING

    def test_add_transition(self):
        """Test adding transitions."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        assert OrderState.CONFIRMED in sm.get_available_transitions()

    def test_add_multiple_transitions(self):
        """Test adding multiple transitions at once."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transitions(
            [
                (OrderState.PENDING, OrderState.CONFIRMED),
                (OrderState.PENDING, OrderState.CANCELLED),
                (OrderState.CONFIRMED, OrderState.PROCESSING),
            ]
        )

        available = sm.get_available_transitions()
        assert OrderState.CONFIRMED in available
        assert OrderState.CANCELLED in available

    def test_valid_transition(self):
        """Test valid state transition."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        sm.transition(OrderState.CONFIRMED)
        assert sm.state == OrderState.CONFIRMED

    def test_invalid_transition_raises(self):
        """Test invalid transition raises error."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        with pytest.raises(TransitionError) as exc_info:
            sm.transition(OrderState.SHIPPED)

        assert exc_info.value.from_state == OrderState.PENDING
        assert exc_info.value.to_state == OrderState.SHIPPED

    def test_can_transition(self):
        """Test can_transition check."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        assert sm.can_transition(OrderState.CONFIRMED)
        assert not sm.can_transition(OrderState.SHIPPED)

    def test_transition_with_guard(self):
        """Test transition with guard condition."""
        sm = StateMachine(OrderState.PENDING)

        def check_inventory(ctx):
            return ctx.get("in_stock", False)

        sm.add_transition(
            OrderState.PENDING,
            OrderState.CONFIRMED,
            guard=check_inventory,
        )

        # Guard fails
        assert not sm.can_transition(OrderState.CONFIRMED, context={"in_stock": False})

        # Guard passes
        assert sm.can_transition(OrderState.CONFIRMED, context={"in_stock": True})

    def test_guard_failure_raises(self):
        """Test that failing guard raises GuardError."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(
            OrderState.PENDING,
            OrderState.CONFIRMED,
            guard=lambda: False,
        )

        with pytest.raises(GuardError):
            sm.transition(OrderState.CONFIRMED)

    def test_before_callback(self):
        """Test before transition callback."""
        sm = StateMachine(OrderState.PENDING)
        called = []

        sm.add_transition(
            OrderState.PENDING,
            OrderState.CONFIRMED,
            before=lambda: called.append("before"),
        )

        sm.transition(OrderState.CONFIRMED)
        assert "before" in called

    def test_after_callback(self):
        """Test after transition callback."""
        sm = StateMachine(OrderState.PENDING)
        called = []

        sm.add_transition(
            OrderState.PENDING,
            OrderState.CONFIRMED,
            after=lambda: called.append("after"),
        )

        sm.transition(OrderState.CONFIRMED)
        assert "after" in called

    def test_on_enter_decorator(self):
        """Test on_enter state hook."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        entered = []

        @sm.on_enter(OrderState.CONFIRMED)
        def on_enter_confirmed(from_state, to_state, ctx):
            entered.append((from_state, to_state))

        sm.transition(OrderState.CONFIRMED)

        assert len(entered) == 1
        assert entered[0] == (OrderState.PENDING, OrderState.CONFIRMED)

    def test_on_exit_decorator(self):
        """Test on_exit state hook."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        exited = []

        @sm.on_exit(OrderState.PENDING)
        def on_exit_pending(from_state, to_state, ctx):
            exited.append((from_state, to_state))

        sm.transition(OrderState.CONFIRMED)

        assert len(exited) == 1
        assert exited[0] == (OrderState.PENDING, OrderState.CONFIRMED)

    def test_on_transition_decorator(self):
        """Test global transition hook."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)
        sm.add_transition(OrderState.CONFIRMED, OrderState.PROCESSING)

        transitions = []

        @sm.on_transition
        def track_transitions(from_state, to_state, ctx):
            transitions.append((from_state, to_state))

        sm.transition(OrderState.CONFIRMED)
        sm.transition(OrderState.PROCESSING)

        assert len(transitions) == 2

    def test_history_tracking(self):
        """Test transition history."""
        sm = StateMachine(OrderState.PENDING, track_history=True)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)
        sm.add_transition(OrderState.CONFIRMED, OrderState.PROCESSING)

        sm.transition(OrderState.CONFIRMED)
        sm.transition(OrderState.PROCESSING)

        history = sm.history
        assert len(history) == 2
        assert history[0].from_state == OrderState.PENDING
        assert history[0].to_state == OrderState.CONFIRMED
        assert history[1].from_state == OrderState.CONFIRMED
        assert history[1].to_state == OrderState.PROCESSING

    def test_history_disabled(self):
        """Test history tracking disabled."""
        sm = StateMachine(OrderState.PENDING, track_history=False)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        sm.transition(OrderState.CONFIRMED)

        assert len(sm.history) == 0

    def test_history_max_size(self):
        """Test history respects max size."""
        sm = StateMachine(TaskState.TODO, max_history=2)
        sm.add_transition(TaskState.TODO, TaskState.IN_PROGRESS)
        sm.add_transition(TaskState.IN_PROGRESS, TaskState.REVIEW)
        sm.add_transition(TaskState.REVIEW, TaskState.DONE)

        sm.transition(TaskState.IN_PROGRESS)
        sm.transition(TaskState.REVIEW)
        sm.transition(TaskState.DONE)

        assert len(sm.history) == 2
        # Should keep most recent
        assert sm.history[-1].to_state == TaskState.DONE

    def test_trigger_event(self):
        """Test event-based transitions."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED, event="confirm")
        sm.add_transition(OrderState.PENDING, OrderState.CANCELLED, event="cancel")

        triggered = sm.trigger("confirm")

        assert triggered
        assert sm.state == OrderState.CONFIRMED

    def test_trigger_event_not_found(self):
        """Test triggering non-existent event."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED, event="confirm")

        triggered = sm.trigger("unknown_event")

        assert not triggered
        assert sm.state == OrderState.PENDING

    def test_is_in_state(self):
        """Test is_in_state check."""
        sm = StateMachine(OrderState.PENDING)

        assert sm.is_in_state(OrderState.PENDING)
        assert sm.is_in_state(OrderState.PENDING, OrderState.CONFIRMED)
        assert not sm.is_in_state(OrderState.CONFIRMED, OrderState.SHIPPED)

    def test_reset(self):
        """Test state machine reset."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)
        sm.transition(OrderState.CONFIRMED)

        sm.reset(OrderState.PENDING)

        assert sm.state == OrderState.PENDING
        assert len(sm.history) == 0

    def test_to_dict(self):
        """Test state machine serialization."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)
        sm.add_transition(OrderState.PENDING, OrderState.CANCELLED)

        data = sm.to_dict()

        assert "current_state" in data
        assert "available_transitions" in data
        assert len(data["available_transitions"]) == 2

    def test_method_chaining(self):
        """Test fluent API with method chaining."""
        sm = (
            StateMachine(OrderState.PENDING)
            .add_transition(OrderState.PENDING, OrderState.CONFIRMED)
            .add_transition(OrderState.CONFIRMED, OrderState.PROCESSING)
            .add_transition(OrderState.PROCESSING, OrderState.SHIPPED)
            .transition(OrderState.CONFIRMED)
            .transition(OrderState.PROCESSING)
        )

        assert sm.state == OrderState.PROCESSING

    def test_transition_with_metadata(self):
        """Test transition with metadata."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        sm.transition(
            OrderState.CONFIRMED,
            metadata={"user": "admin", "reason": "approved"},
        )

        assert sm.history[0].metadata["user"] == "admin"
        assert sm.history[0].metadata["reason"] == "approved"


class TestAsyncStateMachine:
    """Tests for AsyncStateMachine class."""

    @pytest.mark.asyncio
    async def test_async_basic_transition(self):
        """Test basic async transition."""
        sm = AsyncStateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        await sm.transition(OrderState.CONFIRMED)
        assert sm.state == OrderState.CONFIRMED

    @pytest.mark.asyncio
    async def test_async_guard(self):
        """Test async guard condition."""
        sm = AsyncStateMachine(OrderState.PENDING)

        async def async_check():
            await asyncio.sleep(0.01)
            return True

        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED, guard=async_check)

        can = await sm.can_transition(OrderState.CONFIRMED)
        assert can

    @pytest.mark.asyncio
    async def test_async_callbacks(self):
        """Test async before/after callbacks."""
        sm = AsyncStateMachine(OrderState.PENDING)
        called = []

        async def before_cb():
            await asyncio.sleep(0.01)
            called.append("before")

        async def after_cb():
            await asyncio.sleep(0.01)
            called.append("after")

        sm.add_transition(
            OrderState.PENDING,
            OrderState.CONFIRMED,
            before=before_cb,
            after=after_cb,
        )

        await sm.transition(OrderState.CONFIRMED)

        assert "before" in called
        assert "after" in called

    @pytest.mark.asyncio
    async def test_async_on_enter(self):
        """Test async on_enter hook."""
        sm = AsyncStateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)

        entered = []

        @sm.on_enter(OrderState.CONFIRMED)
        async def on_enter(from_s, to_s, ctx):
            await asyncio.sleep(0.01)
            entered.append(to_s)

        await sm.transition(OrderState.CONFIRMED)

        assert OrderState.CONFIRMED in entered

    @pytest.mark.asyncio
    async def test_async_concurrent_transitions(self):
        """Test concurrent transitions are serialized."""
        sm = AsyncStateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)
        sm.add_transition(OrderState.CONFIRMED, OrderState.PROCESSING)
        sm.add_transition(OrderState.PROCESSING, OrderState.SHIPPED)

        # Multiple concurrent transition attempts
        async def do_transitions():
            if sm.state == OrderState.PENDING:
                await sm.transition(OrderState.CONFIRMED)
            if sm.state == OrderState.CONFIRMED:
                await sm.transition(OrderState.PROCESSING)

        await asyncio.gather(do_transitions(), do_transitions())

        # Should not crash and end in valid state
        assert sm.state in [OrderState.CONFIRMED, OrderState.PROCESSING]


class TestWorkflowContext:
    """Tests for WorkflowContext class."""

    def test_context_data(self):
        """Test context data access."""
        ctx = WorkflowContext()
        ctx.set("key", "value")

        assert ctx.get("key") == "value"
        assert ctx.get("missing", "default") == "default"

    def test_context_errors(self):
        """Test context error handling."""
        ctx = WorkflowContext()

        assert not ctx.has_errors

        ctx.add_error("Something went wrong")

        assert ctx.has_errors
        assert "Something went wrong" in ctx.errors

    def test_context_initial_data(self):
        """Test context with initial data."""
        ctx = WorkflowContext(data={"user_id": 123})

        assert ctx.get("user_id") == 123


class TestWorkflow:
    """Tests for Workflow class."""

    def test_basic_workflow(self):
        """Test basic workflow execution."""
        workflow = Workflow("test")

        @workflow.step("step1", on_success="step2")
        def step1(ctx):
            ctx.set("step1_done", True)
            return True

        @workflow.step("step2")
        def step2(ctx):
            ctx.set("step2_done", True)
            return True

        result = workflow.execute()

        assert result.get("step1_done")
        assert result.get("step2_done")
        assert not result.has_errors

    def test_workflow_with_failure(self):
        """Test workflow with step failure."""
        workflow = Workflow("test")

        @workflow.step("step1", on_failure="error_handler")
        def step1(ctx):
            raise ValueError("Step failed")

        @workflow.step("error_handler")
        def handle_error(ctx):
            ctx.set("handled", True)
            return True

        result = workflow.execute()

        assert result.has_errors
        assert result.get("handled")

    def test_workflow_with_initial_data(self):
        """Test workflow with initial context data."""
        workflow = Workflow("test")

        @workflow.step("process")
        def process(ctx):
            return ctx.get("value") > 0

        result = workflow.execute({"value": 10})

        assert result.step_results.get("process") is True

    def test_workflow_branching(self):
        """Test workflow with conditional branching."""
        workflow = Workflow("test")

        @workflow.step("check", on_success="success_path", on_failure="failure_path")
        def check(ctx):
            return ctx.get("should_succeed", False)

        @workflow.step("success_path")
        def success(ctx):
            ctx.set("path", "success")
            return True

        @workflow.step("failure_path")
        def failure(ctx):
            ctx.set("path", "failure")
            return True

        # Test success path
        result1 = workflow.execute({"should_succeed": True})
        assert result1.get("path") == "success"

        # Test failure path
        result2 = workflow.execute({"should_succeed": False})
        assert result2.get("path") == "failure"

    def test_workflow_add_step_programmatic(self):
        """Test adding steps programmatically."""
        workflow = Workflow("test")

        workflow.add_step("step1", lambda ctx: ctx.set("done", True))

        result = workflow.execute()

        assert result.get("done")

    def test_workflow_set_first_step(self):
        """Test setting first step."""
        workflow = Workflow("test")

        @workflow.step("second")
        def second(ctx):
            ctx.set("second", True)
            return True

        @workflow.step("first", on_success="second")
        def first(ctx):
            ctx.set("first", True)
            return True

        workflow.set_first_step("first")

        result = workflow.execute()

        assert result.get("first")
        assert result.get("second")

    def test_workflow_missing_step(self):
        """Test workflow handles missing step."""
        workflow = Workflow("test")

        @workflow.step("step1", on_success="missing_step")
        def step1(ctx):
            return True

        result = workflow.execute()

        assert result.has_errors
        assert "missing_step" in result.errors[0]

    def test_workflow_no_steps(self):
        """Test workflow with no steps."""
        workflow = Workflow("test")
        result = workflow.execute()

        assert result.has_errors
        assert "No steps defined" in result.errors[0]

    @pytest.mark.asyncio
    async def test_workflow_async_execution(self):
        """Test async workflow execution."""
        workflow = Workflow("test")

        @workflow.step("async_step")
        async def async_step(ctx):
            await asyncio.sleep(0.01)
            ctx.set("async_done", True)
            return True

        result = await workflow.execute_async()

        assert result.get("async_done")

    @pytest.mark.asyncio
    async def test_workflow_async_timeout(self):
        """Test async workflow with timeout."""
        workflow = Workflow("test")

        step = WorkflowStep(
            name="slow_step",
            action=lambda ctx: asyncio.sleep(1.0),
            timeout=0.01,
            on_failure="timeout_handler",
        )
        workflow._steps["slow_step"] = step
        workflow._first_step = "slow_step"

        @workflow.step("timeout_handler")
        def handle_timeout(ctx):
            ctx.set("timed_out", True)
            return True

        result = await workflow.execute_async()

        assert result.has_errors
        assert result.get("timed_out")


class TestTransitionDecorator:
    """Tests for transition_method decorator."""

    def test_transition_method_success(self):
        """Test successful transition via method."""

        class Order:
            def __init__(self):
                self.state = OrderState.PENDING

            @transition_method({OrderState.PENDING}, OrderState.CONFIRMED)
            def confirm(self):
                return "confirmed"

        order = Order()
        result = order.confirm()

        assert order.state == OrderState.CONFIRMED
        assert result == "confirmed"

    def test_transition_method_invalid_state(self):
        """Test transition method from invalid state."""

        class Order:
            def __init__(self):
                self.state = OrderState.CANCELLED

            @transition_method({OrderState.PENDING}, OrderState.CONFIRMED)
            def confirm(self):
                return "confirmed"

        order = Order()

        with pytest.raises(TransitionError):
            order.confirm()

    @pytest.mark.asyncio
    async def test_async_transition_method(self):
        """Test async transition method."""

        class Order:
            def __init__(self):
                self.state = OrderState.PENDING

            @async_transition_method({OrderState.PENDING}, OrderState.CONFIRMED)
            async def confirm(self):
                await asyncio.sleep(0.01)
                return "confirmed"

        order = Order()
        result = await order.confirm()

        assert order.state == OrderState.CONFIRMED
        assert result == "confirmed"


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_state_machine(self):
        """Test create_state_machine factory."""
        sm = create_state_machine(
            OrderState.PENDING,
            transitions=[
                (OrderState.PENDING, OrderState.CONFIRMED),
                (OrderState.CONFIRMED, OrderState.SHIPPED),
            ],
        )

        assert sm.state == OrderState.PENDING
        assert sm.can_transition(OrderState.CONFIRMED)

    def test_create_state_machine_no_history(self):
        """Test create_state_machine without history."""
        sm = create_state_machine(
            OrderState.PENDING,
            track_history=False,
        )

        assert sm._track_history is False

    def test_create_async_state_machine(self):
        """Test create_async_state_machine factory."""
        sm = create_async_state_machine(
            OrderState.PENDING,
            transitions=[
                (OrderState.PENDING, OrderState.CONFIRMED),
            ],
        )

        assert sm.state == OrderState.PENDING
        assert OrderState.CONFIRMED in sm.get_available_transitions()

    def test_create_workflow(self):
        """Test create_workflow factory."""
        workflow = create_workflow("test_workflow")

        assert workflow.name == "test_workflow"


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_self_transition(self):
        """Test transition to same state."""
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.PENDING)

        sm.transition(OrderState.PENDING)

        assert sm.state == OrderState.PENDING
        assert len(sm.history) == 1

    def test_transition_error_message(self):
        """Test TransitionError message."""
        error = TransitionError(
            OrderState.PENDING,
            OrderState.SHIPPED,
            "Custom message",
        )

        assert "Custom message" in str(error)
        assert error.from_state == OrderState.PENDING
        assert error.to_state == OrderState.SHIPPED

    def test_guard_exception_returns_false(self):
        """Test guard exception is treated as False."""
        sm = StateMachine(OrderState.PENDING)

        def bad_guard():
            raise ValueError("Guard error")

        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED, guard=bad_guard)

        assert not sm.can_transition(OrderState.CONFIRMED)

    def test_multiple_guards_same_transition(self):
        """Test that only one transition definition exists per pair."""
        sm = StateMachine(OrderState.PENDING)

        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED, guard=lambda: True)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED, guard=lambda: False)

        # Last definition wins
        assert not sm.can_transition(OrderState.CONFIRMED)

    def test_context_in_callbacks(self):
        """Test context is passed to all callbacks."""
        sm = StateMachine(OrderState.PENDING)
        received_contexts = []

        def guard(ctx):
            received_contexts.append(("guard", ctx))
            return True

        def before(ctx):
            received_contexts.append(("before", ctx))

        def after(ctx):
            received_contexts.append(("after", ctx))

        sm.add_transition(
            OrderState.PENDING,
            OrderState.CONFIRMED,
            guard=guard,
            before=before,
            after=after,
        )

        @sm.on_enter(OrderState.CONFIRMED)
        def on_enter(from_s, to_s, ctx):
            received_contexts.append(("enter", ctx))

        context = {"test": True}
        sm.transition(OrderState.CONFIRMED, context=context)

        assert len(received_contexts) == 4
        for name, ctx in received_contexts:
            assert ctx == context

    def test_workflow_step_results(self):
        """Test workflow stores step results."""
        workflow = Workflow("test")

        @workflow.step("step1", on_success="step2")
        def step1(ctx):
            return {"data": "from_step1"}

        @workflow.step("step2")
        def step2(ctx):
            return {"data": "from_step2"}

        result = workflow.execute()

        assert result.step_results["step1"] == {"data": "from_step1"}
        assert result.step_results["step2"] == {"data": "from_step2"}

    def test_string_states(self):
        """Test state machine with string states."""
        sm = StateMachine("pending")
        sm.add_transition("pending", "confirmed")
        sm.add_transition("confirmed", "shipped")

        sm.transition("confirmed")

        assert sm.state == "confirmed"

    def test_integer_states(self):
        """Test state machine with integer states."""
        sm = StateMachine(0)
        sm.add_transition(0, 1)
        sm.add_transition(1, 2)

        sm.transition(1)
        sm.transition(2)

        assert sm.state == 2
