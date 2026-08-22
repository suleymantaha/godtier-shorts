"""Fail-fast validation for the production GPU worker image."""

from backend.runtime_validation import validate_runtime_configuration
from backend.system_validation import validate_accelerator_support_configuration


def main() -> None:
    validate_runtime_configuration()
    validate_accelerator_support_configuration()


if __name__ == "__main__":
    main()
