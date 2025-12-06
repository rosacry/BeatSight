"""Tests for dependency injection utilities in app/utils/dependency_injection.py."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod

import pytest

from app.utils.dependency_injection import (
    # Core classes
    Container,
    ServiceScope,
    ServiceDescriptor,
    ServiceLifetime,
    # Exceptions
    DependencyError,
    ServiceNotFoundError,
    CircularDependencyError,
    # Decorators and mixins
    inject,
    inject_async,
    ServiceProviderMixin,
    # Global functions
    get_container,
    set_container,
    reset_container,
    create_container,
    create_scope,
)


# Test interfaces and implementations
class IRepository(ABC):
    @abstractmethod
    def get(self, id: int) -> dict:
        pass


class ICache(ABC):
    @abstractmethod
    def get(self, key: str) -> str | None:
        pass

    @abstractmethod
    def set(self, key: str, value: str) -> None:
        pass


class ILogger(ABC):
    @abstractmethod
    def log(self, message: str) -> None:
        pass


class InMemoryRepository(IRepository):
    def __init__(self) -> None:
        self.data = {1: {"name": "test"}}

    def get(self, id: int) -> dict:
        return self.data.get(id, {})


class InMemoryCache(ICache):
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str) -> str | None:
        return self.data.get(key)

    def set(self, key: str, value: str) -> None:
        self.data[key] = value


class ConsoleLogger(ILogger):
    def __init__(self) -> None:
        self.messages: list[str] = []

    def log(self, message: str) -> None:
        self.messages.append(message)


class ServiceWithDependency:
    """Service that depends on other services."""

    def __init__(self, cache: ICache, logger: ILogger) -> None:
        self.cache = cache
        self.logger = logger


class ServiceA:
    """Service for circular dependency test."""

    def __init__(self, b: "ServiceB") -> None:
        self.b = b


class ServiceB:
    """Service for circular dependency test."""

    def __init__(self, a: ServiceA) -> None:
        self.a = a


class DisposableService:
    """Service with dispose method."""

    def __init__(self) -> None:
        self.disposed = False

    def dispose(self) -> None:
        self.disposed = True


class AsyncDisposableService:
    """Service with async dispose method."""

    def __init__(self) -> None:
        self.disposed = False

    async def dispose_async(self) -> None:
        await asyncio.sleep(0.01)
        self.disposed = True


class TestServiceDescriptor:
    """Tests for ServiceDescriptor class."""

    def test_descriptor_creation(self):
        """Test creating a service descriptor."""
        descriptor = ServiceDescriptor(
            service_type=ICache,
            implementation_type=InMemoryCache,
            lifetime=ServiceLifetime.SINGLETON,
        )

        assert descriptor.service_type == ICache
        assert descriptor.implementation_type == InMemoryCache
        assert descriptor.lifetime == ServiceLifetime.SINGLETON

    def test_descriptor_with_factory(self):
        """Test descriptor with factory."""

        def create_cache():
            return InMemoryCache()

        descriptor = ServiceDescriptor(
            service_type=ICache,
            factory=create_cache,
        )

        assert descriptor.factory is not None
        assert not descriptor.is_async_factory()

    def test_descriptor_async_factory(self):
        """Test detecting async factory."""

        async def create_cache():
            return InMemoryCache()

        descriptor = ServiceDescriptor(
            service_type=ICache,
            factory=create_cache,
        )

        assert descriptor.is_async_factory()


class TestContainer:
    """Tests for Container class."""

    def test_register_and_resolve(self):
        """Test basic registration and resolution."""
        container = Container()
        container.register(IRepository, InMemoryRepository)

        repo = container.resolve(IRepository)

        assert isinstance(repo, InMemoryRepository)

    def test_register_same_type(self):
        """Test registering type as its own implementation."""
        container = Container()
        container.register(InMemoryCache)

        cache = container.resolve(InMemoryCache)

        assert isinstance(cache, InMemoryCache)

    def test_register_singleton(self):
        """Test singleton registration."""
        container = Container()
        container.register_singleton(ICache, InMemoryCache)

        cache1 = container.resolve(ICache)
        cache2 = container.resolve(ICache)

        assert cache1 is cache2

    def test_register_transient(self):
        """Test transient registration (default)."""
        container = Container()
        container.register(ICache, InMemoryCache)

        cache1 = container.resolve(ICache)
        cache2 = container.resolve(ICache)

        assert cache1 is not cache2

    def test_register_instance(self):
        """Test registering existing instance."""
        container = Container()
        cache = InMemoryCache()
        cache.set("key", "value")

        container.register_instance(ICache, cache)

        resolved = container.resolve(ICache)

        assert resolved is cache
        assert resolved.get("key") == "value"

    def test_register_factory(self):
        """Test factory registration."""
        container = Container()
        call_count = [0]

        def create_cache():
            call_count[0] += 1
            return InMemoryCache()

        container.register_factory(ICache, create_cache)

        container.resolve(ICache)
        container.resolve(ICache)

        assert call_count[0] == 2  # Factory called each time

    def test_factory_with_container(self):
        """Test factory that receives container."""
        container = Container()
        container.register(ILogger, ConsoleLogger)

        def create_service(container: Container):
            logger = container.resolve(ILogger)
            return {"logger": logger}

        container.register_factory(dict, create_service)

        result = container.resolve(dict)

        assert isinstance(result["logger"], ConsoleLogger)

    def test_service_not_found(self):
        """Test resolving unregistered service."""
        container = Container()

        with pytest.raises(ServiceNotFoundError) as exc_info:
            container.resolve(ICache)

        assert exc_info.value.service_type == ICache

    def test_circular_dependency(self):
        """Test circular dependency detection."""
        container = Container()
        container.register(ServiceA)
        container.register(ServiceB)

        with pytest.raises(CircularDependencyError) as exc_info:
            container.resolve(ServiceA)

        assert ServiceA in exc_info.value.chain
        assert ServiceB in exc_info.value.chain

    def test_constructor_injection(self):
        """Test automatic constructor injection."""
        container = Container()
        container.register(ICache, InMemoryCache)
        container.register(ILogger, ConsoleLogger)
        container.register(ServiceWithDependency)

        service = container.resolve(ServiceWithDependency)

        assert isinstance(service.cache, InMemoryCache)
        assert isinstance(service.logger, ConsoleLogger)

    def test_is_registered(self):
        """Test is_registered check."""
        container = Container()
        container.register(ICache, InMemoryCache)

        assert container.is_registered(ICache)
        assert not container.is_registered(ILogger)

    def test_clear(self):
        """Test clearing container."""
        container = Container()
        container.register_singleton(ICache, InMemoryCache)
        container.resolve(ICache)  # Create singleton

        container.clear()

        assert not container.is_registered(ICache)

    def test_get_registered_types(self):
        """Test getting registered types."""
        container = Container()
        container.register(ICache, InMemoryCache)
        container.register(ILogger, ConsoleLogger)

        types = container.get_registered_types()

        assert ICache in types
        assert ILogger in types

    def test_method_chaining(self):
        """Test fluent API with method chaining."""
        container = (
            Container()
            .register(ICache, InMemoryCache)
            .register_singleton(ILogger, ConsoleLogger)
            .register_instance(IRepository, InMemoryRepository())
        )

        assert container.is_registered(ICache)
        assert container.is_registered(ILogger)
        assert container.is_registered(IRepository)


class TestServiceScope:
    """Tests for ServiceScope class."""

    def test_scoped_service(self):
        """Test scoped service returns same instance in scope."""
        container = Container()
        container.register_scoped(ICache, InMemoryCache)

        with container.scope() as scope:
            cache1 = container.resolve(ICache, scope=scope)
            cache2 = container.resolve(ICache, scope=scope)

            assert cache1 is cache2

    def test_scoped_different_scopes(self):
        """Test different scopes get different instances."""
        container = Container()
        container.register_scoped(ICache, InMemoryCache)

        with container.scope() as scope1:
            cache1 = container.resolve(ICache, scope=scope1)

        with container.scope() as scope2:
            cache2 = container.resolve(ICache, scope=scope2)

        assert cache1 is not cache2

    def test_scoped_requires_scope(self):
        """Test scoped service requires scope."""
        container = Container()
        container.register_scoped(ICache, InMemoryCache)

        with pytest.raises(DependencyError, match="requires a scope"):
            container.resolve(ICache)

    def test_scope_dispose(self):
        """Test scope disposal calls dispose on services."""
        container = Container()
        container.register_scoped(DisposableService)

        with container.scope() as scope:
            service = container.resolve(DisposableService, scope=scope)
            assert not service.disposed

        assert service.disposed

    def test_disposed_scope_raises(self):
        """Test using disposed scope raises error."""
        container = Container()
        container.register_scoped(ICache, InMemoryCache)

        scope = container.create_scope()
        scope.dispose()

        with pytest.raises(DependencyError, match="disposed"):
            scope.get_or_create(ICache, InMemoryCache)


class TestAsyncContainer:
    """Tests for async container operations."""

    @pytest.mark.asyncio
    async def test_resolve_async(self):
        """Test async resolution."""
        container = Container()
        container.register(ICache, InMemoryCache)

        cache = await container.resolve_async(ICache)

        assert isinstance(cache, InMemoryCache)

    @pytest.mark.asyncio
    async def test_async_factory(self):
        """Test async factory function."""
        container = Container()

        async def create_cache():
            await asyncio.sleep(0.01)
            return InMemoryCache()

        container.register_factory(ICache, create_cache)

        cache = await container.resolve_async(ICache)

        assert isinstance(cache, InMemoryCache)

    @pytest.mark.asyncio
    async def test_async_singleton(self):
        """Test async singleton resolution."""
        container = Container()

        async def create_cache():
            return InMemoryCache()

        container.register_factory(
            ICache,
            create_cache,
            lifetime=ServiceLifetime.SINGLETON,
        )

        cache1 = await container.resolve_async(ICache)
        cache2 = await container.resolve_async(ICache)

        assert cache1 is cache2

    @pytest.mark.asyncio
    async def test_async_scope(self):
        """Test async scope context manager."""
        container = Container()
        container.register_scoped(AsyncDisposableService)

        async with container.scope_async() as scope:
            service = await container.resolve_async(
                AsyncDisposableService,
                scope=scope,
            )
            assert not service.disposed

        assert service.disposed


class TestInjectDecorator:
    """Tests for inject decorator."""

    def setup_method(self):
        """Set up fresh container for each test."""
        reset_container()

    def teardown_method(self):
        """Clean up global container."""
        reset_container()

    def test_inject_decorator(self):
        """Test inject decorator injects dependencies."""
        container = get_container()
        container.register(ICache, InMemoryCache)

        @inject
        def my_function(cache: ICache):
            return cache

        result = my_function()

        assert isinstance(result, InMemoryCache)

    def test_inject_with_explicit_args(self):
        """Test inject decorator respects explicit arguments."""
        container = get_container()
        container.register(ICache, InMemoryCache)

        custom_cache = InMemoryCache()
        custom_cache.set("key", "custom")

        @inject
        def my_function(cache: ICache):
            return cache

        result = my_function(cache=custom_cache)

        assert result is custom_cache
        assert result.get("key") == "custom"

    @pytest.mark.asyncio
    async def test_inject_async_decorator(self):
        """Test async inject decorator."""
        container = get_container()
        container.register(ICache, InMemoryCache)

        @inject_async
        async def my_function(cache: ICache):
            return cache

        result = await my_function()

        assert isinstance(result, InMemoryCache)


class TestServiceProviderMixin:
    """Tests for ServiceProviderMixin."""

    def setup_method(self):
        """Set up fresh container for each test."""
        reset_container()

    def teardown_method(self):
        """Clean up global container."""
        reset_container()

    def test_mixin_uses_global_container(self):
        """Test mixin uses global container by default."""
        container = get_container()
        container.register(ICache, InMemoryCache)

        class MyClass(ServiceProviderMixin):
            def get_cache(self):
                return self.services.resolve(ICache)

        obj = MyClass()
        cache = obj.get_cache()

        assert isinstance(cache, InMemoryCache)

    def test_mixin_custom_container(self):
        """Test mixin with custom container."""
        custom_container = Container()
        custom_container.register(ICache, InMemoryCache)

        class MyClass(ServiceProviderMixin):
            pass

        obj = MyClass()
        obj.services = custom_container

        cache = obj.services.resolve(ICache)

        assert isinstance(cache, InMemoryCache)


class TestGlobalContainer:
    """Tests for global container functions."""

    def setup_method(self):
        """Reset global container before each test."""
        reset_container()

    def teardown_method(self):
        """Clean up global container."""
        reset_container()

    def test_get_container_creates_singleton(self):
        """Test get_container creates singleton."""
        container1 = get_container()
        container2 = get_container()

        assert container1 is container2

    def test_set_container(self):
        """Test setting custom global container."""
        custom = Container()
        custom.register(ICache, InMemoryCache)

        set_container(custom)

        assert get_container() is custom

    def test_reset_container(self):
        """Test resetting global container."""
        container = get_container()
        container.register(ICache, InMemoryCache)

        reset_container()

        new_container = get_container()

        assert new_container is not container
        assert not new_container.is_registered(ICache)


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_create_container(self):
        """Test create_container function."""
        container = create_container()

        assert isinstance(container, Container)
        assert len(container.get_registered_types()) == 0

    def test_create_scope(self):
        """Test create_scope function."""
        container = Container()
        scope = create_scope(container)

        assert isinstance(scope, ServiceScope)

    def test_create_scope_uses_global(self):
        """Test create_scope uses global container if none provided."""
        reset_container()
        scope = create_scope()

        assert isinstance(scope, ServiceScope)


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_resolve_after_registration_override(self):
        """Test resolving after overriding registration."""
        container = Container()

        class CacheV1(ICache):
            version = 1

            def get(self, key):
                return None

            def set(self, key, value):
                pass

        class CacheV2(ICache):
            version = 2

            def get(self, key):
                return None

            def set(self, key, value):
                pass

        container.register(ICache, CacheV1)
        cache1 = container.resolve(ICache)

        container.register(ICache, CacheV2)
        cache2 = container.resolve(ICache)

        assert cache1.version == 1
        assert cache2.version == 2

    def test_singleton_not_affected_by_override(self):
        """Test singleton is not affected by later registration."""
        container = Container()

        container.register_singleton(ICache, InMemoryCache)
        cache1 = container.resolve(ICache)
        cache1.set("key", "value")

        # Override registration
        container.register_singleton(ICache, InMemoryCache)
        cache2 = container.resolve(ICache)

        # Still same instance
        assert cache2.get("key") == "value"

    def test_service_without_type_hints(self):
        """Test constructing service without type hints."""

        class SimpleService:
            def __init__(self):
                self.value = 42

        container = Container()
        container.register(SimpleService)

        service = container.resolve(SimpleService)

        assert service.value == 42

    def test_multiple_scopes_concurrent(self):
        """Test multiple concurrent scopes don't interfere."""
        container = Container()
        container.register_scoped(ICache, InMemoryCache)

        with container.scope() as scope1:
            cache1 = container.resolve(ICache, scope=scope1)
            cache1.set("key", "value1")

            with container.scope() as scope2:
                cache2 = container.resolve(ICache, scope=scope2)
                cache2.set("key", "value2")

                # Each scope has its own instance
                assert cache1.get("key") == "value1"
                assert cache2.get("key") == "value2"

    def test_service_lifetime_values(self):
        """Test ServiceLifetime enum values."""
        assert ServiceLifetime.TRANSIENT.value == "transient"
        assert ServiceLifetime.SINGLETON.value == "singleton"
        assert ServiceLifetime.SCOPED.value == "scoped"

    def test_dependency_error_base(self):
        """Test DependencyError is base exception."""
        error = DependencyError("test error")
        assert str(error) == "test error"

        assert issubclass(ServiceNotFoundError, DependencyError)
        assert issubclass(CircularDependencyError, DependencyError)
