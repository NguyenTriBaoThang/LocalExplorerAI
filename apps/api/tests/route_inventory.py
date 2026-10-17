"""Enumerate every route the application serves, with its declared access policy."""

import importlib
import pkgutil

from fastapi.routing import APIRoute

import app.api.routes as routes_pkg
from app.main import app


def _policies(dependant) -> list:
    found = []
    for dep in dependant.dependencies:
        policy = getattr(dep.call, "__auth_policy__", None)
        if policy is not None:
            found.append(policy)
        found += _policies(dep)
    return found


def inventory() -> list[tuple[str, str, str, list]]:
    """[(module, METHOD, path, [policies])] for each route handler in app/api/routes plus app-level routes."""
    rows = []
    sources = [("main", app.router.routes)]
    for info in pkgutil.iter_modules(routes_pkg.__path__):
        module = importlib.import_module(f"{routes_pkg.__name__}.{info.name}")
        router = getattr(module, "router", None)
        if router is not None:
            sources.append((info.name, router.routes))
    for name, route_list in sources:
        for route in route_list:
            if isinstance(route, APIRoute):
                for method in sorted(route.methods - {"HEAD", "OPTIONS"}):
                    rows.append((name, method, route.path, _policies(route.dependant)))
    return rows
