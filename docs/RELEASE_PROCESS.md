# Release Process

A public release is GREEN only after:

1. the field-tested source lineage is frozen and hashed;
2. the public candidate passes the OPSEC scan;
3. unit and syntax tests pass;
4. Docker builds successfully;
5. installation succeeds from a fresh clone on a clean supported host;
6. `/healthz`, `/status.json`, and the 800×600 PNG are verified;
7. host cron refresh executes successfully;
8. no private hostnames, LAN IPs, logs, caches, output, or secrets are tracked; and
9. the release tarball SHA256 is verified after a clean extraction.

The field-tested runtime should not be modified merely to prepare documentation. Public-release changes are staged separately and validated before tagging.
