"""Multi-tenant support for SDMAS.

Provides tenant context extraction from authentication, tenant-scoped
repository base classes, and FastAPI dependencies for injecting the
current tenant into request handlers.
"""
