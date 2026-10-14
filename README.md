# ml-host-hardening

Deploy a small ML inference API on a default Ubuntu Server VM, scan it, harden it one justified change at a time, and scan it again. The before/after difference is the result.

The full write-up, with the reasoning for every change, is in [docs/REPORT.md](docs/REPORT.md).

## Headline results

| Measure | Before | After |
|---|---|---|
| Open TCP ports (nmap, all 65,535) | 22, 8000 | 22, 80 |
| Application port 8000 from the network | open | filtered |
| SSH login methods | publickey, password | publickey only |
| Lynis hardening index | 61 | 71 |
| Lynis warnings | 1 | 0 |
| API service exposure (`systemd-analyze security`) | 9.2 UNSAFE | 1.4 OK |
| Pending updates | 17 | 0 |
| Host firewall | inactive | active, default deny |

Raw scan output for every stage is in [docs/evidence/](docs/evidence/).

## What is not done

I report these as gaps and not as accepted risks (details in the report, sections 7 and 8):

- API traffic is plain HTTP. There is no TLS certificate.
- Lynis still flags four network protocols (DCCP, SCTP, RDS, TIPC) that are blocked with `modprobe`. I did not find out which mechanism Lynis expects.
- The VM's USB controller is still enabled.
- `deploy/hardening/apply.sh` documents the order of the changes. It has not been tested end to end on a fresh machine.
- fail2ban was verified to run and count a manual ban, but not against a real brute-force attempt.
- Each scan was run once, on a host-only lab network that was never exposed to the internet.

## Repository layout

| Path | Contents |
|---|---|
| `app/` | FastAPI application, split into config, logging, schemas, service and routes |
| `tests/` | Automated tests (16) for the API and the service layer |
| `deploy/systemd/`, `deploy/nginx/` | Service unit and reverse-proxy configuration |
| `deploy/hardening/` | Every hardening file applied, plus `apply.sh` |
| `docs/REPORT.md` | The report |
| `docs/evidence/` | Before and after scan output |

## Run the application locally

Tests were run on Python 3.14. The deployed service runs on Python 3.12.

    python3 -m venv .venv
    source .venv/bin/activate
    pip install -r requirements-dev.txt
    cp .env.example .env
    python -m pytest
    uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000

Settings are read only from `MLAPI_` environment variables (see `.env.example`). The model parameters have no defaults on purpose, so the service refuses to start without them.

With the example settings, a request looks like this:

    curl -s -X POST http://127.0.0.1:8000/predict -H 'Content-Type: application/json' -d '{"features":[1.0,2.0,3.0]}'

It returns a score of about 0.9644. In production mode the interactive docs are disabled, while the example settings use development mode, where they are served at `/docs`.

## Scope

Everything here was built and tested on my own VM, on a host-only network. Nothing was scanned or tested against third-party systems.
