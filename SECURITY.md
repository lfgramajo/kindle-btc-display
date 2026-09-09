# Security Policy

## Deployment boundary

Kindle Bitcoin Price Display is designed for **LAN-only** use. The default project does not provide authentication and should not be exposed directly to the public internet.

## Secrets

The default Bitcoin display requires **no secrets**.

Weather support is optional. If enabled, provider keys belong only in the runtime file:

```text
config/weather.conf
```

That file is ignored by Git and must never be committed. The public repository contains only `config/weather.conf.example` with empty key fields.

Weather-provider failures are logged without the exception URL so API-key query parameters are not written to application logs.

## Container hardening

The default Docker deployment:

- runs as UID/GID 10001, not root;
- uses a read-only root filesystem;
- drops all Linux capabilities;
- enables `no-new-privileges`;
- does not mount the Docker socket;
- limits PIDs, memory, and CPU;
- exposes only TCP 8787 on the configured host address; and
- serves only explicit application routes.

Writable bind mounts are limited to runtime config/cache, logs, and output.

## LAN trigger surface

Any host that can reach port 8787 can call `/refresh` and `/refresh?force=1`. On a trusted LAN this is intentional. If the service is placed on a less-trusted network, add a firewall or authenticated reverse proxy before allowing access.

## Public-repository hygiene

Never commit or publish:

- `.env`
- `config/coins.config`
- `config/extras.config`
- `config/weather.conf`
- `config/cache/`
- `logs/`
- `output/`
- private hostnames, LAN addresses, usernames, or local paths
- API keys, tokens, credentials, cookies, or certificates

## Vulnerability reports

For a public release, use GitHub's private vulnerability reporting feature when available rather than opening an issue containing exploit details or secrets.
