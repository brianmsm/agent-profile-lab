# Security policy

Agent Profile Lab is an offline research and configuration planning utility. The public snapshot does not include live provider-account credentials or require API tokens. It does not install profiles in an agent runtime.

Do not post real API keys, cookies, authorization headers, account usage screenshots, private source datasets, personal home-directory names or unredacted provider traces in public Issues or PRs.

For vulnerabilities, use private GitHub vulnerability reporting if enabled.

Before contributing, run:

    python3 -B tools/verify_public_release.py

The scanner verifies known patterns and distribution boundaries; it does not prove that every sensitive or copyrighted fragment is absent.
