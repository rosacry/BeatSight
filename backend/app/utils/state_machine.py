"""
State machine utilities for workflow and status management.

This module provides utilities for:
- Finite state machine implementation
- State transition validation and hooks
- Workflow management with history tracking
- Hierarchical state machines
- Event-driven state transitions
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from functools import wraps
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Set,
    Type,
    TypeVar,
    Union,
)


# Type variables
S = TypeVar("S")  # State type
E = TypeVar("E")  # Event type
T = TypeVar("T")  # Entity type


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    
    def __init__(
        self,
        from_state: Any,
        to_state: Any,
        message: Optional[str] = None,
    ) -> None:
        self.from_state = from_state
        self.to_state = to_state
        self.message = message or f"Invalid transition from {from_state} to {to_state}"
        super().__init__(self.message)


class GuardError(Exception):
    """Raised when a transition guard fails."""
    
    def __init__(self, message: str) -> None:
        super().__init__(message)


@dataclass
class TransitionRecord:
    """Record of a state transition."""
    
    from_state: Any
    to_state: Any
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "from_state": str(self.from_state),
            "to_state": str(self.to_state),
            "timestamp": self.timestamp.isoformat(),
            "event": self.event,
            "metadata": self.metadata,
        }


@dataclass
class Transition(Generic[S]):
    """Definition of a state transition."""
    
    from_state: S
    to_state: S
    event: Optional[str] = None
    guard: Optional[Callable[..., bool]] = None
    before: Optional[Callable[..., None]] = None
    after: Optional[Callable[..., None]] = None
    
    def check_guard(self, context: Any = None) -> bool:
        """Check if the guard condition passes."""
        if self.guard is None:
            return True
        return self.guard(context) if context else self.guard()


class StateMachine(Generic[S]):
    """
    A finite state machine with transition validation.
    
    Example:
        class OrderState(Enum):
            PENDING = "pending"
            CONFIRMED = "confirmed"
            SHIPPED = "shipped"
            DELIVERED = "delivered"
            CANCELLED = "cancelled"
        
        sm = StateMachine(OrderState.PENDING)
        sm.add_transition(OrderState.PENDING, OrderState.CONFIRMED)
        sm.add_transition(OrderState.PENDING, OrderState.CANCELLED)
        sm.add_transition(OrderState.CONFIRMED, OrderState.SHIPPED)
        sm.add_transition(OrderState.SHIPPED, OrderState.DELIVERED)
        
        sm.transition(OrderState.CONFIRMED)  # OK
        sm.transition(OrderState.DELIVERED)  # Raises TransitionError
    """
    
    def __init__(
        self,
        initial_state: S,
        *,
        track_history: bool = True,
        max_history: int = 100,
    ) -> None:
        """
        Initialize the state machine.
        
        Args:
            initial_state: The initial state
            track_history: Whether to track transition history
            max_history: Maximum number of history entries to keep
        """
        self._state = initial_state
        self._track_history = track_history
        self._max_history = max_history
        self._transitions: Dict[S, Set[S]] = defaultdict(set)
        self._transition_defs: Dict[tuple, Transition] = {}
        self._history: List[TransitionRecord] = []
        self._on_enter: Dict[S, List[Callable]] = defaultdict(list)
        self._on_exit: Dict[S, List[Callable]] = defaultdict(list)
        self._on_any_transition: List[Callable] = []
    
    @property
    def state(self) -> S:
        """Get the current state."""
        return self._state
    
    @property
    def history(self) -> List[TransitionRecord]:
        """Get transition history."""
        return self._history.copy()
    
    def add_transition(
        self,
        from_state: S,
        to_state: S,
        *,
        event: Optional[str] = None,
        guard: Optional[Callable[..., bool]] = None,
        before: Optional[Callable[..., None]] = None,
        after: Optional[Callable[..., None]] = None,
    ) -> "StateMachine[S]":
        """
        Add a valid transition.
        
        Args:
            from_state: Source state
            to_state: Target state
            event: Optional event name that triggers this transition
            guard: Optional guard function that must return True
            before: Optional callback to run before transition
            after: Optional callback to run after transition
        
        Returns:
            Self for method chaining
        """
        self._transitions[from_state].add(to_state)
        self._transition_defs[(from_state, to_state)] = Transition(
            from_state=from_state,
            to_state=to_state,
            event=event,
            guard=guard,
            before=before,
            after=after,
        )
        return self
    
    def add_transitions(self, transitions: List[tuple]) -> "StateMachine[S]":
        """
        Add multiple transitions.
        
        Args:
            transitions: List of (from_state, to_state) tuples
        
        Returns:
            Self for method chaining
        """
        for t in transitions:
            if len(t) == 2:
                self.add_transition(t[0], t[1])
            elif len(t) >= 3:
                self.add_transition(t[0], t[1], event=t[2] if len(t) > 2 else None)
        return self
    
    def can_transition(
        self,
        to_state: S,
        *,
        context: Any = None,
    ) -> bool:
        """
        Check if a transition is valid.
        
        Args:
            to_state: Target state
            context: Optional context for guard evaluation
        
        Returns:
            True if transition is allowed
        """
        if to_state not in self._transitions[self._state]:
            return False
        
        trans_def = self._transition_defs.get((self._state, to_state))
        if trans_def and trans_def.guard:
            try:
                return trans_def.check_guard(context)
            except Exception:
                return False
        
        return True
    
    def transition(
        self,
        to_state: S,
        *,
        event: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Any = None,
    ) -> "StateMachine[S]":
        """
        Transition to a new state.
        
        Args:
            to_state: Target state
            event: Optional event name
            metadata: Optional metadata for the transition record
            context: Optional context for guards and callbacks
        
        Returns:
            Self for method chaining
        
        Raises:
            TransitionError: If transition is not allowed
            GuardError: If guard condition fails
        """
        if to_state not in self._transitions[self._state]:
            raise TransitionError(self._state, to_state)
        
        trans_def = self._transition_defs.get((self._state, to_state))
        
        # Check guard
        if trans_def and trans_def.guard:
            if not trans_def.check_guard(context):
                raise GuardError(f"Guard failed for transition {self._state} -> {to_state}")
        
        from_state = self._state
        
        # Run before callback
        if trans_def and trans_def.before:
            trans_def.before(context) if context else trans_def.before()
        
        # Run on_exit hooks
        for callback in self._on_exit[from_state]:
            callback(from_state, to_state, context)
        
        # Update state
        self._state = to_state
        
        # Run on_enter hooks
        for callback in self._on_enter[to_state]:
            callback(from_state, to_state, context)
        
        # Run after callback
        if trans_def and trans_def.after:
            trans_def.after(context) if context else trans_def.after()
        
        # Run global transition callbacks
        for callback in self._on_any_transition:
            callback(from_state, to_state, context)
        
        # Record history
        if self._track_history:
            record = TransitionRecord(
                from_state=from_state,
                to_state=to_state,
                event=event or (trans_def.event if trans_def else None),
                metadata=metadata or {},
            )
            self._history.append(record)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]
        
        return self
    
    def trigger(
        self,
        event: str,
        *,
        metadata: Optional[Dict[str, Any]] = None,
        context: Any = None,
    ) -> bool:
        """
        Trigger a transition by event name.
        
        Args:
            event: Event name
            metadata: Optional metadata
            context: Optional context
        
        Returns:
            True if a transition was triggered
        """
        for (from_state, to_state), trans_def in self._transition_defs.items():
            if from_state == self._state and trans_def.event == event:
                if trans_def.guard is None or trans_def.check_guard(context):
                    self.transition(to_state, event=event, metadata=metadata, context=context)
                    return True
        return False
    
    def on_enter(self, state: S) -> Callable:
        """
        Decorator for on_enter callbacks.
        
        Args:
            state: State to attach callback to
        """
        def decorator(func: Callable) -> Callable:
            self._on_enter[state].append(func)
            return func
        return decorator
    
    def on_exit(self, state: S) -> Callable:
        """
        Decorator for on_exit callbacks.
        
        Args:
            state: State to attach callback to
        """
        def decorator(func: Callable) -> Callable:
            self._on_exit[state].append(func)
            return func
        return decorator
    
    def on_transition(self, func: Callable) -> Callable:
        """Decorator for global transition callbacks."""
        self._on_any_transition.append(func)
        return func
    
    def get_available_transitions(self) -> Set[S]:
        """Get all states that can be transitioned to from current state."""
        return self._transitions[self._state].copy()
    
    def is_in_state(self, *states: S) -> bool:
        """Check if current state is one of the given states."""
        return self._state in states
    
    def reset(self, state: Optional[S] = None) -> "StateMachine[S]":
        """
        Reset the state machine.
        
        Args:
            state: State to reset to (defaults to first recorded state)
        
        Returns:
            Self for method chaining
        """
        if state is not None:
            self._state = state
        elif self._history:
            self._state = self._history[0].from_state
        self._history.clear()
        return self
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert state machine to dictionary."""
        return {
            "current_state": str(self._state),
            "available_transitions": [str(s) for s in self.get_available_transitions()],
            "history_length": len(self._history),
        }


class AsyncStateMachine(Generic[S]):
    """
    Async version of the state machine.
    
    Supports async guards, callbacks, and hooks.
    """
    
    def __init__(
        self,
        initial_state: S,
        *,
        track_history: bool = True,
        max_history: int = 100,
    ) -> None:
        self._state = initial_state
        self._track_history = track_history
        self._max_history = max_history
        self._transitions: Dict[S, Set[S]] = defaultdict(set)
        self._transition_defs: Dict[tuple, Transition] = {}
        self._history: List[TransitionRecord] = []
        self._on_enter: Dict[S, List[Callable]] = defaultdict(list)
        self._on_exit: Dict[S, List[Callable]] = defaultdict(list)
        self._on_any_transition: List[Callable] = []
        self._lock = asyncio.Lock()
    
    @property
    def state(self) -> S:
        """Get the current state."""
        return self._state
    
    @property
    def history(self) -> List[TransitionRecord]:
        """Get transition history."""
        return self._history.copy()
    
    def add_transition(
        self,
        from_state: S,
        to_state: S,
        *,
        event: Optional[str] = None,
        guard: Optional[Callable[..., Union[bool, Awaitable[bool]]]] = None,
        before: Optional[Callable[..., Union[None, Awaitable[None]]]] = None,
        after: Optional[Callable[..., Union[None, Awaitable[None]]]] = None,
    ) -> "AsyncStateMachine[S]":
        """Add a valid transition with optional async callbacks."""
        self._transitions[from_state].add(to_state)
        self._transition_defs[(from_state, to_state)] = Transition(
            from_state=from_state,
            to_state=to_state,
            event=event,
            guard=guard,
            before=before,
            after=after,
        )
        return self
    
    async def _run_callback(self, callback: Callable, *args: Any) -> Any:
        """Run a callback, handling both sync and async."""
        result = callback(*args)
        if asyncio.iscoroutine(result):
            return await result
        return result
    
    async def can_transition(
        self,
        to_state: S,
        *,
        context: Any = None,
    ) -> bool:
        """Check if a transition is valid."""
        if to_state not in self._transitions[self._state]:
            return False
        
        trans_def = self._transition_defs.get((self._state, to_state))
        if trans_def and trans_def.guard:
            try:
                result = trans_def.guard(context) if context else trans_def.guard()
                if asyncio.iscoroutine(result):
                    return await result
                return result
            except Exception:
                return False
        
        return True
    
    async def transition(
        self,
        to_state: S,
        *,
        event: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        context: Any = None,
    ) -> "AsyncStateMachine[S]":
        """Transition to a new state (async-safe)."""
        async with self._lock:
            if to_state not in self._transitions[self._state]:
                raise TransitionError(self._state, to_state)
            
            trans_def = self._transition_defs.get((self._state, to_state))
            
            # Check guard
            if trans_def and trans_def.guard:
                guard_result = trans_def.guard(context) if context else trans_def.guard()
                if asyncio.iscoroutine(guard_result):
                    guard_result = await guard_result
                if not guard_result:
                    raise GuardError(f"Guard failed for transition {self._state} -> {to_state}")
            
            from_state = self._state
            
            # Run before callback
            if trans_def and trans_def.before:
                await self._run_callback(trans_def.before, context) if context else await self._run_callback(trans_def.before)
            
            # Run on_exit hooks
            for callback in self._on_exit[from_state]:
                await self._run_callback(callback, from_state, to_state, context)
            
            # Update state
            self._state = to_state
            
            # Run on_enter hooks
            for callback in self._on_enter[to_state]:
                await self._run_callback(callback, from_state, to_state, context)
            
            # Run after callback
            if trans_def and trans_def.after:
                await self._run_callback(trans_def.after, context) if context else await self._run_callback(trans_def.after)
            
            # Run global transition callbacks
            for callback in self._on_any_transition:
                await self._run_callback(callback, from_state, to_state, context)
            
            # Record history
            if self._track_history:
                record = TransitionRecord(
                    from_state=from_state,
                    to_state=to_state,
                    event=event or (trans_def.event if trans_def else None),
                    metadata=metadata or {},
                )
                self._history.append(record)
                if len(self._history) > self._max_history:
                    self._history = self._history[-self._max_history:]
            
            return self
    
    def on_enter(self, state: S) -> Callable:
        """Decorator for on_enter callbacks."""
        def decorator(func: Callable) -> Callable:
            self._on_enter[state].append(func)
            return func
        return decorator
    
    def on_exit(self, state: S) -> Callable:
        """Decorator for on_exit callbacks."""
        def decorator(func: Callable) -> Callable:
            self._on_exit[state].append(func)
            return func
        return decorator
    
    def get_available_transitions(self) -> Set[S]:
        """Get all states that can be transitioned to from current state."""
        return self._transitions[self._state].copy()


class WorkflowStep:
    """A step in a workflow with conditions and actions."""
    
    def __init__(
        self,
        name: str,
        *,
        action: Optional[Callable[..., Any]] = None,
        condition: Optional[Callable[..., bool]] = None,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> None:
        self.name = name
        self.action = action
        self.condition = condition
        self.on_success = on_success
        self.on_failure = on_failure
        self.timeout = timeout


@dataclass
class WorkflowContext:
    """Context passed through workflow execution."""
    
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    step_results: Dict[str, Any] = field(default_factory=dict)
    
    def set(self, key: str, value: Any) -> None:
        """Set a context value."""
        self.data[key] = value
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get a context value."""
        return self.data.get(key, default)
    
    def add_error(self, error: str) -> None:
        """Add an error message."""
        self.errors.append(error)
    
    @property
    def has_errors(self) -> bool:
        """Check if there are any errors."""
        return len(self.errors) > 0


class Workflow:
    """
    A workflow engine for executing a series of steps.
    
    Example:
        workflow = Workflow("order_processing")
        
        @workflow.step("validate")
        def validate_order(ctx):
            return ctx.data.get("order") is not None
        
        @workflow.step("process", on_success="notify", on_failure="error")
        def process_order(ctx):
            # Process the order
            return True
        
        @workflow.step("notify")
        def notify_customer(ctx):
            # Send notification
            pass
        
        result = workflow.execute({"order": order_data})
    """
    
    def __init__(self, name: str) -> None:
        self.name = name
        self._steps: Dict[str, WorkflowStep] = {}
        self._first_step: Optional[str] = None
        self._current_step: Optional[str] = None
    
    def step(
        self,
        name: str,
        *,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
        timeout: Optional[float] = None,
    ) -> Callable:
        """
        Decorator to define a workflow step.
        
        Args:
            name: Step name
            on_success: Next step on success (None = end)
            on_failure: Step to go to on failure (None = end with error)
            timeout: Optional timeout in seconds
        """
        def decorator(func: Callable) -> Callable:
            step = WorkflowStep(
                name=name,
                action=func,
                on_success=on_success,
                on_failure=on_failure,
                timeout=timeout,
            )
            self._steps[name] = step
            if self._first_step is None:
                self._first_step = name
            return func
        return decorator
    
    def add_step(
        self,
        name: str,
        action: Callable[..., Any],
        *,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
    ) -> "Workflow":
        """Add a workflow step programmatically."""
        step = WorkflowStep(
            name=name,
            action=action,
            on_success=on_success,
            on_failure=on_failure,
        )
        self._steps[name] = step
        if self._first_step is None:
            self._first_step = name
        return self
    
    def set_first_step(self, name: str) -> "Workflow":
        """Set the first step of the workflow."""
        if name not in self._steps:
            raise ValueError(f"Step '{name}' not found")
        self._first_step = name
        return self
    
    def execute(
        self,
        initial_data: Optional[Dict[str, Any]] = None,
        *,
        start_step: Optional[str] = None,
    ) -> WorkflowContext:
        """
        Execute the workflow.
        
        Args:
            initial_data: Initial context data
            start_step: Step to start from (default: first step)
        
        Returns:
            WorkflowContext with results
        """
        context = WorkflowContext(data=initial_data or {})
        current = start_step or self._first_step
        
        if current is None:
            context.add_error("No steps defined")
            return context
        
        visited: Set[str] = set()
        max_iterations = len(self._steps) * 2  # Prevent infinite loops
        iterations = 0
        
        while current and iterations < max_iterations:
            if current in visited and current not in [s.on_failure for s in self._steps.values()]:
                # Potential infinite loop (excluding error handlers)
                break
            
            visited.add(current)
            iterations += 1
            
            step = self._steps.get(current)
            if step is None:
                context.add_error(f"Step '{current}' not found")
                break
            
            self._current_step = current
            
            try:
                if step.action:
                    result = step.action(context)
                    context.step_results[current] = result
                    
                    if result:
                        current = step.on_success
                    else:
                        current = step.on_failure
                else:
                    current = step.on_success
            except Exception as e:
                context.add_error(f"Step '{current}' failed: {str(e)}")
                context.step_results[current] = {"error": str(e)}
                current = step.on_failure
        
        return context
    
    async def execute_async(
        self,
        initial_data: Optional[Dict[str, Any]] = None,
        *,
        start_step: Optional[str] = None,
    ) -> WorkflowContext:
        """Execute the workflow asynchronously."""
        context = WorkflowContext(data=initial_data or {})
        current = start_step or self._first_step
        
        if current is None:
            context.add_error("No steps defined")
            return context
        
        visited: Set[str] = set()
        max_iterations = len(self._steps) * 2
        iterations = 0
        
        while current and iterations < max_iterations:
            if current in visited and current not in [s.on_failure for s in self._steps.values()]:
                break
            
            visited.add(current)
            iterations += 1
            
            step = self._steps.get(current)
            if step is None:
                context.add_error(f"Step '{current}' not found")
                break
            
            self._current_step = current
            
            try:
                if step.action:
                    result = step.action(context)
                    if asyncio.iscoroutine(result):
                        if step.timeout:
                            result = await asyncio.wait_for(result, timeout=step.timeout)
                        else:
                            result = await result
                    
                    context.step_results[current] = result
                    
                    if result:
                        current = step.on_success
                    else:
                        current = step.on_failure
                else:
                    current = step.on_success
            except asyncio.TimeoutError:
                context.add_error(f"Step '{current}' timed out")
                context.step_results[current] = {"error": "timeout"}
                current = step.on_failure
            except Exception as e:
                context.add_error(f"Step '{current}' failed: {str(e)}")
                context.step_results[current] = {"error": str(e)}
                current = step.on_failure
        
        return context


def state_property(
    attr_name: str,
    allowed_states: Optional[Set] = None,
    denied_states: Optional[Set] = None,
) -> property:
    """
    Create a property that validates state before access.
    
    Args:
        attr_name: Name of the underlying attribute
        allowed_states: States where access is allowed
        denied_states: States where access is denied
    
    Example:
        class Order:
            state = OrderState.PENDING
            
            @state_property("_tracking_number", allowed_states={OrderState.SHIPPED, OrderState.DELIVERED})
            def tracking_number(self): ...
    """
    def getter(self: Any) -> Any:
        current_state = getattr(self, "state", None)
        
        if allowed_states and current_state not in allowed_states:
            raise ValueError(f"Cannot access {attr_name} in state {current_state}")
        
        if denied_states and current_state in denied_states:
            raise ValueError(f"Cannot access {attr_name} in state {current_state}")
        
        return getattr(self, f"_{attr_name}", None)
    
    def setter(self: Any, value: Any) -> None:
        current_state = getattr(self, "state", None)
        
        if allowed_states and current_state not in allowed_states:
            raise ValueError(f"Cannot set {attr_name} in state {current_state}")
        
        if denied_states and current_state in denied_states:
            raise ValueError(f"Cannot set {attr_name} in state {current_state}")
        
        setattr(self, f"_{attr_name}", value)
    
    return property(getter, setter)


def transition_method(
    from_states: Set,
    to_state: Any,
    state_attr: str = "state",
) -> Callable:
    """
    Decorator that validates and updates state on method call.
    
    Args:
        from_states: Valid source states
        to_state: Target state after method completes
        state_attr: Name of the state attribute
    
    Example:
        class Order:
            state = OrderState.PENDING
            
            @transition_method({OrderState.PENDING}, OrderState.CONFIRMED)
            def confirm(self):
                # Confirm the order
                pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            current_state = getattr(self, state_attr)
            if current_state not in from_states:
                raise TransitionError(
                    current_state,
                    to_state,
                    f"Cannot call {func.__name__} from state {current_state}",
                )
            
            result = func(self, *args, **kwargs)
            setattr(self, state_attr, to_state)
            return result
        
        return wrapper
    return decorator


def async_transition_method(
    from_states: Set,
    to_state: Any,
    state_attr: str = "state",
) -> Callable:
    """Async version of transition_method decorator."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            current_state = getattr(self, state_attr)
            if current_state not in from_states:
                raise TransitionError(
                    current_state,
                    to_state,
                    f"Cannot call {func.__name__} from state {current_state}",
                )
            
            result = await func(self, *args, **kwargs)
            setattr(self, state_attr, to_state)
            return result
        
        return wrapper
    return decorator


# Factory functions
def create_state_machine(
    initial_state: S,
    transitions: Optional[List[tuple]] = None,
    *,
    track_history: bool = True,
) -> StateMachine[S]:
    """
    Create a state machine with optional initial transitions.
    
    Args:
        initial_state: Initial state
        transitions: List of (from, to) tuples
        track_history: Whether to track history
    
    Returns:
        Configured StateMachine
    """
    sm = StateMachine(initial_state, track_history=track_history)
    if transitions:
        sm.add_transitions(transitions)
    return sm


def create_async_state_machine(
    initial_state: S,
    transitions: Optional[List[tuple]] = None,
    *,
    track_history: bool = True,
) -> AsyncStateMachine[S]:
    """Create an async state machine with optional initial transitions."""
    sm = AsyncStateMachine(initial_state, track_history=track_history)
    if transitions:
        for t in transitions:
            if len(t) >= 2:
                sm.add_transition(t[0], t[1])
    return sm


def create_workflow(name: str) -> Workflow:
    """Create a new workflow."""
    return Workflow(name)
