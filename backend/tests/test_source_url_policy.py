from __future__ import annotations

import pytest

from backend.core.source_url_policy import SourceUrlPolicy, SourceUrlPolicyError


PUBLIC_IP = "142.250.184.206"


def policy(*, addresses=(PUBLIC_IP,)) -> SourceUrlPolicy:
    return SourceUrlPolicy(resolver=lambda _host: addresses)


@pytest.mark.parametrize(
    "url",
    [
        "http://youtube.com/watch?v=abc123DEF45",
        "file:///etc/passwd",
        "ftp://youtube.com/video",
        "gopher://youtube.com/_payload",
        "custom://youtube.com/video",
        "https://user:pass@youtube.com/watch?v=abc123DEF45",
        "https://youtube.com:8443/watch?v=abc123DEF45",
        "https://youtube.com.evil.example/watch?v=abc123DEF45",
        "https://evil-youtu.be/abc123DEF45",
        "https://localhost/watch?v=abc123DEF45",
        "https://127.0.0.1/watch?v=abc123DEF45",
        "https://[::1]/watch?v=abc123DEF45",
        "https://169.254.169.254/latest/meta-data/",
        "https://metadata.google.internal/computeMetadata/v1/",
    ],
)
def test_source_policy_rejects_unsafe_schemes_authorities_and_hosts(url: str) -> None:
    with pytest.raises(SourceUrlPolicyError):
        policy().validate(url)


@pytest.mark.parametrize(
    "address",
    [
        "127.0.0.1",
        "10.0.0.1",
        "172.16.0.1",
        "192.168.1.1",
        "169.254.169.254",
        "0.0.0.0",
        "::1",
        "fc00::1",
        "fe80::1",
    ],
)
def test_source_policy_rejects_allowlisted_hostname_resolving_to_non_public_ip(address: str) -> None:
    with pytest.raises(SourceUrlPolicyError, match="public"):
        policy(addresses=(address,)).validate(
            "https://www.youtube.com/watch?v=abc123DEF45"
        )


def test_source_policy_accepts_exact_supported_youtube_hosts_with_public_dns() -> None:
    validator = policy()
    assert validator.validate("https://youtube.com/watch?v=abc123DEF45").host == "youtube.com"
    assert validator.validate("https://www.youtube.com/shorts/abc123DEF45").host == "www.youtube.com"
    assert validator.validate("https://m.youtube.com/watch?v=abc123DEF45").host == "m.youtube.com"
    assert validator.validate("https://youtu.be/abc123DEF45").host == "youtu.be"


def test_every_redirect_destination_is_revalidated_before_use() -> None:
    validator = policy()
    validated = validator.validate_redirect_chain(
        "https://youtube.com/watch?v=abc123DEF45",
        ["https://www.youtube.com/watch?v=abc123DEF45", "/shorts/abc123DEF45"],
    )
    assert validated.url == "https://www.youtube.com/shorts/abc123DEF45"

    with pytest.raises(SourceUrlPolicyError):
        validator.validate_redirect_chain(
            "https://youtube.com/watch?v=abc123DEF45",
            ["https://127.0.0.1/internal"],
        )


def test_dns_resolution_failure_is_fail_closed() -> None:
    validator = SourceUrlPolicy(resolver=lambda _host: ())
    with pytest.raises(SourceUrlPolicyError, match="resolve"):
        validator.validate("https://youtube.com/watch?v=abc123DEF45")
