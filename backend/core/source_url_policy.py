"""Central SSRF policy for user-controlled source URLs."""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse, urlunparse


SUPPORTED_SOURCE_HOSTS = frozenset(
    {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
    }
)


class SourceUrlPolicyError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ValidatedSourceUrl:
    url: str
    host: str
    resolved_addresses: tuple[str, ...]


Resolver = Callable[[str], Iterable[str]]


def _system_resolver(host: str) -> tuple[str, ...]:
    try:
        records = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise SourceUrlPolicyError("Source hostname could not resolve") from exc
    return tuple(dict.fromkeys(str(record[4][0]) for record in records))


class SourceUrlPolicy:
    def __init__(
        self,
        *,
        allowed_hosts: Iterable[str] = SUPPORTED_SOURCE_HOSTS,
        resolver: Resolver | None = None,
    ) -> None:
        self._allowed_hosts = frozenset(host.strip().lower().rstrip(".") for host in allowed_hosts)
        self._resolver = resolver or _system_resolver

    def _validate_structure(self, raw_url: str):
        value = str(raw_url or "").strip()
        if not value or any(ord(character) < 32 for character in value):
            raise SourceUrlPolicyError("Source URL is empty or malformed")

        parsed = urlparse(value)
        try:
            port = parsed.port
        except ValueError as exc:
            raise SourceUrlPolicyError("Source URL port is invalid") from exc

        host = (parsed.hostname or "").lower().rstrip(".")
        if parsed.scheme.lower() != "https":
            raise SourceUrlPolicyError("Source URL must use HTTPS")
        if parsed.username is not None or parsed.password is not None:
            raise SourceUrlPolicyError("Source URL userinfo is forbidden")
        if port not in (None, 443):
            raise SourceUrlPolicyError("Source URL may only use port 443")
        if host not in self._allowed_hosts:
            raise SourceUrlPolicyError("Source hostname is not supported")

        normalized_netloc = host if port in (None, 443) else f"{host}:{port}"
        normalized_url = urlunparse(
            ("https", normalized_netloc, parsed.path or "/", parsed.params, parsed.query, parsed.fragment)
        )
        return parsed, host, normalized_url

    def validate_structure(self, raw_url: str) -> ValidatedSourceUrl:
        _parsed, host, normalized_url = self._validate_structure(raw_url)
        return ValidatedSourceUrl(normalized_url, host, ())

    def validate(self, raw_url: str) -> ValidatedSourceUrl:
        _parsed, host, normalized_url = self._validate_structure(raw_url)

        try:
            addresses = tuple(dict.fromkeys(str(address) for address in self._resolver(host)))
        except SourceUrlPolicyError:
            raise
        except Exception as exc:
            raise SourceUrlPolicyError("Source hostname could not resolve") from exc
        if not addresses:
            raise SourceUrlPolicyError("Source hostname could not resolve")
        for address in addresses:
            try:
                parsed_address = ipaddress.ip_address(address)
            except ValueError as exc:
                raise SourceUrlPolicyError("Source hostname returned an invalid address") from exc
            if not parsed_address.is_global:
                raise SourceUrlPolicyError("Source hostname must resolve only to public addresses")

        return ValidatedSourceUrl(normalized_url, host, addresses)

    def validate_redirect_chain(
        self,
        initial_url: str,
        redirect_destinations: Sequence[str],
    ) -> ValidatedSourceUrl:
        current = self.validate(initial_url)
        for destination in redirect_destinations:
            next_url = urljoin(current.url, str(destination or "").strip())
            current = self.validate(next_url)
        return current


DEFAULT_SOURCE_URL_POLICY = SourceUrlPolicy()


def validate_source_url(url: str) -> ValidatedSourceUrl:
    return DEFAULT_SOURCE_URL_POLICY.validate(url)
