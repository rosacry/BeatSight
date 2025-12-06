"""
Dependency injection container utilities.

This module provides utilities for:
- Simple dependency injection container
- Service registration and resolution
- Scoped and singleton lifetimes
- Constructor injection support
- Async service factories
"""

from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
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
    get_type_hints,
)
from weakref import WeakValueDictionary


# Type variables
T = TypeVar("T")
F = TypeVar("F", bound=Callable[..., Any])


class ServiceLifetime(Enum):
    """Lifetime options for registered services."""
    
    TRANSIENT = "transient"  # New instance each time
    SINGLETON = "singleton"  # Same instance always
    SCOPED = "scoped"  # Same instance within a scope


class DependencyError(Exception):
    """Base exception for dependency injection errors."""
    pass


class ServiceNotFoundError(DependencyError):
    """Raised when a requested service is not registered."""
    
    def __init__(self, service_type: Type) -> None:
        self.service_type = service_type
        super().__init__(f"Service not found: {service_type.__name__}")


class CircularDependencyError(DependencyError):
    """Raised when a circular dependency is detected."""
    
    def __init__(self, chain: List[Type]) -> None:
        self.chain = chain
        names = " -> ".join(t.__name__ for t in chain)
        super().__init__(f"Circular dependency detected: {names}")


@dataclass
class ServiceDescriptor:
    """Describes how to create a service instance."""
    
    service_type: Type
    implementation_type: Optional[Type] = None
    factory: Optional[Callable[..., Any]] = None
    instance: Optional[Any] = None
    lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    
    def is_async_factory(self) -> bool:
        """Check if factory is async."""
        if self.factory is None:
            return False
        return asyncio.iscoroutinefunction(self.factory)


class ServiceScope:
    """
    A scope for scoped service instances.
    
    Services with SCOPED lifetime will return the same instance
    within a single scope.
    """
    
    def __init__(self, container: "Container") -> None:
        self._container = container
        self._instances: Dict[Type, Any] = {}
        self._is_disposed = False
    
    def get_or_create(
        self,
        service_type: Type[T],
        factory: Callable[[], T],
    ) -> T:
        """Get or create a scoped instance."""
        if self._is_disposed:
            raise DependencyError("Scope has been disposed")
        
        if service_type not in self._instances:
            self._instances[service_type] = factory()
        
        return self._instances[service_type]
    
    async def get_or_create_async(
        self,
        service_type: Type[T],
        factory: Callable[[], Awaitable[T]],
    ) -> T:
        """Get or create a scoped instance asynchronously."""
        if self._is_disposed:
            raise DependencyError("Scope has been disposed")
        
        if service_type not in self._instances:
            self._instances[service_type] = await factory()
        
        return self._instances[service_type]
    
    def dispose(self) -> None:
        """Dispose of the scope and its instances."""
        self._is_disposed = True
        
        for instance in self._instances.values():
            if hasattr(instance, "dispose"):
                instance.dispose()
            elif hasattr(instance, "close"):
                instance.close()
        
        self._instances.clear()
    
    async def dispose_async(self) -> None:
        """Dispose of the scope asynchronously."""
        self._is_disposed = True
        
        for instance in self._instances.values():
            if hasattr(instance, "dispose_async"):
                await instance.dispose_async()
            elif hasattr(instance, "close_async"):
                await instance.close_async()
            elif hasattr(instance, "aclose"):
                await instance.aclose()
            elif hasattr(instance, "dispose"):
                instance.dispose()
            elif hasattr(instance, "close"):
                instance.close()
        
        self._instances.clear()


class Container:
    """
    A simple dependency injection container.
    
    Example:
        container = Container()
        
        # Register services
        container.register(IUserRepository, SqlUserRepository)
        container.register_singleton(ICache, RedisCache)
        container.register_factory(IDbConnection, create_connection)
        
        # Resolve services
        repo = container.resolve(IUserRepository)
        
        # With scopes
        with container.create_scope() as scope:
            service = container.resolve(IScopedService, scope=scope)
    """
    
    def __init__(self) -> None:
        self._services: Dict[Type, ServiceDescriptor] = {}
        self._singletons: Dict[Type, Any] = {}
        self._resolution_stack: List[Type] = []
    
    def register(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
        *,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> "Container":
        """
        Register a service with its implementation.
        
        Args:
            service_type: The service interface/type
            implementation_type: The concrete implementation (default: service_type)
            lifetime: Service lifetime
        
        Returns:
            Self for method chaining
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            implementation_type=implementation_type or service_type,
            lifetime=lifetime,
        )
        return self
    
    def register_singleton(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
    ) -> "Container":
        """Register a singleton service."""
        return self.register(
            service_type,
            implementation_type,
            lifetime=ServiceLifetime.SINGLETON,
        )
    
    def register_scoped(
        self,
        service_type: Type[T],
        implementation_type: Optional[Type[T]] = None,
    ) -> "Container":
        """Register a scoped service."""
        return self.register(
            service_type,
            implementation_type,
            lifetime=ServiceLifetime.SCOPED,
        )
    
    def register_instance(
        self,
        service_type: Type[T],
        instance: T,
    ) -> "Container":
        """
        Register an existing instance.
        
        The instance will be used for all resolutions (singleton-like).
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            instance=instance,
            lifetime=ServiceLifetime.SINGLETON,
        )
        self._singletons[service_type] = instance
        return self
    
    def register_factory(
        self,
        service_type: Type[T],
        factory: Callable[..., T],
        *,
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT,
    ) -> "Container":
        """
        Register a factory function to create instances.
        
        The factory can accept Container as a parameter for sub-resolutions.
        """
        self._services[service_type] = ServiceDescriptor(
            service_type=service_type,
            factory=factory,
            lifetime=lifetime,
        )
        return self
    
    def is_registered(self, service_type: Type) -> bool:
        """Check if a service type is registered."""
        return service_type in self._services
    
    def resolve(
        self,
        service_type: Type[T],
        *,
        scope: Optional[ServiceScope] = None,
    ) -> T:
        """
        Resolve a service instance.
        
        Args:
            service_type: The service type to resolve
            scope: Optional scope for scoped services
        
        Returns:
            The resolved service instance
        
        Raises:
            ServiceNotFoundError: If service is not registered
            CircularDependencyError: If circular dependency detected
        """
        if service_type not in self._services:
            raise ServiceNotFoundError(service_type)
        
        # Check for circular dependencies
        if service_type in self._resolution_stack:
            self._resolution_stack.append(service_type)
            chain = self._resolution_stack.copy()
            self._resolution_stack.clear()
            raise CircularDependencyError(chain)
        
        self._resolution_stack.append(service_type)
        
        try:
            descriptor = self._services[service_type]
            
            # Handle pre-existing instance
            if descriptor.instance is not None:
                return descriptor.instance
            
            # Handle singleton
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                if service_type in self._singletons:
                    return self._singletons[service_type]
                
                instance = self._create_instance(descriptor, scope)
                self._singletons[service_type] = instance
                return instance
            
            # Handle scoped
            if descriptor.lifetime == ServiceLifetime.SCOPED:
                if scope is None:
                    raise DependencyError(
                        f"Scoped service {service_type.__name__} requires a scope"
                    )
                return scope.get_or_create(
                    service_type,
                    lambda: self._create_instance(descriptor, scope),
                )
            
            # Transient - always create new
            return self._create_instance(descriptor, scope)
        
        finally:
            if self._resolution_stack:
                self._resolution_stack.pop()
    
    async def resolve_async(
        self,
        service_type: Type[T],
        *,
        scope: Optional[ServiceScope] = None,
    ) -> T:
        """Resolve a service instance asynchronously."""
        if service_type not in self._services:
            raise ServiceNotFoundError(service_type)
        
        if service_type in self._resolution_stack:
            self._resolution_stack.append(service_type)
            chain = self._resolution_stack.copy()
            self._resolution_stack.clear()
            raise CircularDependencyError(chain)
        
        self._resolution_stack.append(service_type)
        
        try:
            descriptor = self._services[service_type]
            
            if descriptor.instance is not None:
                return descriptor.instance
            
            if descriptor.lifetime == ServiceLifetime.SINGLETON:
                if service_type in self._singletons:
                    return self._singletons[service_type]
                
                instance = await self._create_instance_async(descriptor, scope)
                self._singletons[service_type] = instance
                return instance
            
            if descriptor.lifetime == ServiceLifetime.SCOPED:
                if scope is None:
                    raise DependencyError(
                        f"Scoped service {service_type.__name__} requires a scope"
                    )
                return await scope.get_or_create_async(
                    service_type,
                    lambda: self._create_instance_async(descriptor, scope),
                )
            
            return await self._create_instance_async(descriptor, scope)
        
        finally:
            if self._resolution_stack:
                self._resolution_stack.pop()
    
    def _create_instance(
        self,
        descriptor: ServiceDescriptor,
        scope: Optional[ServiceScope],
    ) -> Any:
        """Create an instance from a descriptor."""
        if descriptor.factory:
            sig = inspect.signature(descriptor.factory)
            if "container" in sig.parameters:
                return descriptor.factory(container=self)
            return descriptor.factory()
        
        impl_type = descriptor.implementation_type or descriptor.service_type
        return self._construct(impl_type, scope)
    
    async def _create_instance_async(
        self,
        descriptor: ServiceDescriptor,
        scope: Optional[ServiceScope],
    ) -> Any:
        """Create an instance from a descriptor asynchronously."""
        if descriptor.factory:
            sig = inspect.signature(descriptor.factory)
            if "container" in sig.parameters:
                result = descriptor.factory(container=self)
            else:
                result = descriptor.factory()
            
            if asyncio.iscoroutine(result):
                return await result
            return result
        
        impl_type = descriptor.implementation_type or descriptor.service_type
        return await self._construct_async(impl_type, scope)
    
    def _construct(
        self,
        impl_type: Type[T],
        scope: Optional[ServiceScope],
    ) -> T:
        """Construct an instance, resolving constructor dependencies."""
        try:
            hints = get_type_hints(impl_type.__init__)
        except Exception:
            # Fall back to no type hints
            hints = {}
        
        # Remove 'return' key if present
        hints.pop("return", None)
        
        kwargs = {}
        for name, hint in hints.items():
            if self.is_registered(hint):
                kwargs[name] = self.resolve(hint, scope=scope)
        
        return impl_type(**kwargs)
    
    async def _construct_async(
        self,
        impl_type: Type[T],
        scope: Optional[ServiceScope],
    ) -> T:
        """Construct an instance asynchronously."""
        try:
            hints = get_type_hints(impl_type.__init__)
        except Exception:
            hints = {}
        
        hints.pop("return", None)
        
        kwargs = {}
        for name, hint in hints.items():
            if self.is_registered(hint):
                kwargs[name] = await self.resolve_async(hint, scope=scope)
        
        return impl_type(**kwargs)
    
    def create_scope(self) -> ServiceScope:
        """Create a new service scope."""
        return ServiceScope(self)
    
    @contextmanager
    def scope(self):
        """Context manager for creating a scope."""
        scope = self.create_scope()
        try:
            yield scope
        finally:
            scope.dispose()
    
    @asynccontextmanager
    async def scope_async(self):
        """Async context manager for creating a scope."""
        scope = self.create_scope()
        try:
            yield scope
        finally:
            await scope.dispose_async()
    
    def clear(self) -> None:
        """Clear all registrations."""
        self._services.clear()
        self._singletons.clear()
        self._resolution_stack.clear()
    
    def get_registered_types(self) -> Set[Type]:
        """Get all registered service types."""
        return set(self._services.keys())


def inject(func: F) -> F:
    """
    Decorator that injects dependencies into function parameters.
    
    Uses the global container to resolve type-hinted parameters.
    
    Example:
        @inject
        def my_function(service: IMyService):
            service.do_something()
    """
    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        hints = get_type_hints(func)
        hints.pop("return", None)
        
        container = get_container()
        
        for name, hint in hints.items():
            if name not in kwargs and container.is_registered(hint):
                kwargs[name] = container.resolve(hint)
        
        return func(*args, **kwargs)
    
    return wrapper  # type: ignore


def inject_async(func: F) -> F:
    """Async version of the inject decorator."""
    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> Any:
        hints = get_type_hints(func)
        hints.pop("return", None)
        
        container = get_container()
        
        for name, hint in hints.items():
            if name not in kwargs and container.is_registered(hint):
                kwargs[name] = await container.resolve_async(hint)
        
        return await func(*args, **kwargs)
    
    return wrapper  # type: ignore


class ServiceProviderMixin:
    """
    Mixin class that provides dependency resolution.
    
    Classes inheriting from this mixin get a `services` property
    that can resolve dependencies.
    
    Example:
        class MyClass(ServiceProviderMixin):
            def do_work(self):
                cache = self.services.resolve(ICache)
    """
    
    _container: Optional[Container] = None
    
    @property
    def services(self) -> Container:
        """Get the service container."""
        if self._container is None:
            return get_container()
        return self._container
    
    @services.setter
    def services(self, container: Container) -> None:
        """Set the service container."""
        self._container = container


# Global container instance
_global_container: Optional[Container] = None


def get_container() -> Container:
    """Get the global container instance."""
    global _global_container
    if _global_container is None:
        _global_container = Container()
    return _global_container


def set_container(container: Container) -> None:
    """Set the global container instance."""
    global _global_container
    _global_container = container


def reset_container() -> None:
    """Reset the global container."""
    global _global_container
    if _global_container:
        _global_container.clear()
    _global_container = None


# Factory functions
def create_container() -> Container:
    """Create a new container instance."""
    return Container()


def create_scope(container: Optional[Container] = None) -> ServiceScope:
    """Create a new scope from the given or global container."""
    c = container or get_container()
    return c.create_scope()
