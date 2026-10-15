import ipaddress

from fastapi import Request


def request_scheme(request: Request, trusted_proxy_ips: str = "") -> str:
    """The scheme the browser used: ``X-Forwarded-Proto`` is believed only when the direct peer is a trusted proxy."""
    scheme = request.url.scheme
    peer = request.client.host if request.client else ""
    try:
        peer_ip = ipaddress.ip_address(peer)
        trusted = any(peer_ip in ipaddress.ip_network(item.strip(), strict=False) for item in trusted_proxy_ips.split(",") if item.strip())
    except ValueError:
        return scheme
    forwarded = request.headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower()
    return forwarded if trusted and forwarded in {"http", "https"} else scheme


def client_ip(request: Request, trusted_proxy_ips: str = "") -> str:
    peer = request.client.host if request.client else "unknown"
    if not trusted_proxy_ips.strip():
        return peer
    try:
        trusted_networks = [
            ipaddress.ip_network(item.strip(), strict=False)
            for item in trusted_proxy_ips.split(",") if item.strip()
        ]
        peer_ip = ipaddress.ip_address(peer)
    except ValueError:
        return peer
    if not any(peer_ip in network for network in trusted_networks):
        return peer
    forwarded = request.headers.get("X-Forwarded-For", "")
    chain = [item.strip() for item in forwarded.split(",") if item.strip()] + [peer]
    for item in reversed(chain):
        try:
            address = ipaddress.ip_address(item)
        except ValueError:
            return peer
        if any(address in network for network in trusted_networks):
            continue
        return str(address)
    return peer
