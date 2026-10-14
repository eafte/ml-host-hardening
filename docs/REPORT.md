# Hardening an ML Inference Host: Before and After

## 1. Summary

I deployed a small FastAPI inference API on a default Ubuntu Server 24.04 VM in a deliberately weak configuration, scanned it from outside (nmap) and inside (Lynis), hardened it one justified change at a time, and scanned it again.

| Measure | Before | After |
|---|---|---|
| Open TCP ports (nmap, all 65,535) | 22 (OpenSSH), 8000 (Uvicorn) | 22 (OpenSSH), 80 (nginx) |
| API application port 8000, seen from the network | open | filtered |
| SSH login methods offered | publickey, password | publickey only |
| Lynis hardening index | 61 | 71 |
| Lynis warnings | 1 | 0 |
| Lynis suggestions | 47 | 41 |
| API service exposure (`systemd-analyze security`) | 9.2 UNSAFE | 1.4 OK |
| Pending package updates | 17 | 0 |
| Host firewall | inactive | active, default deny incoming |

Two things did not improve and are reported honestly in later sections: Lynis still flags four unused network protocols even though they are blocked, and API traffic is still plain HTTP.

## 2. Environment and method

- **Host:** Windows laptop running Oracle VirtualBox.
- **Target VM (`ml-host`):** Ubuntu Server 24.04.5 LTS, 2048 MB RAM, 15 GB disk, audio disabled, USB controller left enabled. Two network adapters: NAT (internet access for updates) and host-only (192.168.56.0/24), where the VM is 192.168.56.106 and the admin machine is 192.168.56.1. The host-only network keeps the deliberately weak baseline off any real network.
- **Application:** FastAPI served by Uvicorn, with a small logistic-regression scorer. The model is not the subject of this project. It is the workload being protected.
- **Scanners:** nmap 7.991 run from the Windows host (the external view), and Lynis 3.0.9 run on the VM (the internal audit). Lynis is the Ubuntu-packaged version, which is older than the latest release.
- **Baseline (deliberately weak):** SSH password login enabled, no firewall, 17 pending updates, the API started by hand as the admin user and listening on all interfaces (0.0.0.0:8000), no reverse proxy.
- **Method:** one change at a time. After each change I tested from a separate window and checked the live value, not only the config file. That habit found two settings silently overridden by other components (see the sysctl section).

## 3. Threat model

- **Assets:** the inference API and its model parameters, the host, and the admin credentials.
- **Attackers considered:** (1) a network attacker who scans and brute-forces exposed services; (2) an attacker who compromises the API process and tries to escalate or move sideways.
- **Trust boundary:** the network edge. After hardening, the only network-facing services are nginx (port 80) and SSH (port 22, reachable from the admin address only).
- **Out of scope:** physical access, application-layer bugs in the API code, and denial-of-service beyond basic rate limiting.

## 4. Evidence layout

All raw evidence is committed under [docs/evidence](/docs/evidence/):

| Folder | Contents |
|---|---|
| `before/` | Baseline nmap scan, SSH auth methods, Lynis report and findings, host facts |
| `after/` | First post-hardening Lynis run. It was taken while 7 security updates were still pending and before two later fixes, so it is kept for the record but is not the final result. |
| `after2/` | Final Lynis run and host facts |
| `after-nmap/` | Final external scans. `ssh-auth-superseded-ratelimit.txt` is kept but marked superseded: it shows port 22 as filtered because the firewall rate limit tripped during scanning, which is a scan artifact and not a result. |
| `metrics/` | Kernel-setting values before hardening and the systemd sandbox scores before and after |

## 5. Changes and justification

Each change records what it addresses, why this approach was chosen over the alternatives, and how it was verified.

### 5.1 Patching

- **Baseline:** 17 pending updates. The SSH banner reported the exact build (OpenSSH 9.6p1 Ubuntu 3ubuntu13.19), which lets an attacker match it against known vulnerabilities.
- **Change:** installed the pending updates, then enabled unattended upgrades (`/etc/apt/apt.conf.d/20auto-upgrades`).
- **Why security updates only:** the allowed origins on this host are the Ubuntu security pockets (noble-security and the ESM security pockets), not the general noble-updates pocket. A security fix should not wait for someone to remember it, and a general feature update should not change the server overnight.
- **Why no automatic reboot:** kernel updates apply only after a restart, and an unplanned reboot of a service host is a risk of its own. The cost is that a kernel patch can sit unapplied until someone reboots. I accepted that and reboot by hand.
- **What I learned:** seven more updates, including kernel 6.8.0-147, appeared after the first patching round. The first Lynis "after" run caught the server in that state and raised a vulnerable-packages warning (libx11-6, libx11-data, linux-libc-dev, linux-tools-common). Plain `apt upgrade` holds back updates that need new packages, such as a new kernel, so I used `apt full-upgrade` and rebooted. The warning was gone in the final Lynis run.
- **Verified:** `apt list --upgradable` shows 0, and the running kernel is 6.8.0-147-generic.

### 5.2 SSH: key-only login

- **Key:** a dedicated ed25519 key with a passphrase, used for this server only. If it is stolen it opens one VM, and the passphrase protects it if the laptop is stolen. The public half is in `~/.ssh/authorized_keys` with permissions 700 on the folder and 600 on the file, because sshd ignores keys in folders that other users can write to.
- **Order of work:** key login was proven first, with password fallback disabled in the test command, and only then were passwords turned off. Doing it the other way round is how people lock themselves out.
- **Where the settings live:** a drop-in file, `/etc/ssh/sshd_config.d/00-hardening.conf`. The `00-` prefix matters because sshd uses the first value it reads for each setting. The `sshd_config.d` folder was empty at baseline, so nothing could override it. The change was applied with a reload, not a restart, so the existing session stayed open.

| Setting | Baseline | Now | Reason |
|---|---|---|---|
| PasswordAuthentication | yes | no | Removes password guessing as an attack entirely |
| KbdInteractiveAuthentication | no | no (explicit) | Closes the second route to password-style login; already off, now stated so the intent is recorded |
| PermitRootLogin | without-password | no | Root is the first account every attacker tries |
| AllowUsers | unrestricted | mladmin | Only one account may attempt a login |
| MaxAuthTries | 6 | 3 | Fewer guesses per connection |
| LogLevel | INFO | VERBOSE | Logs the key fingerprint used, which helps forensics |
| AllowTcpForwarding | yes | no | Unused feature that a stolen session could use to pivot |
| X11Forwarding | yes | no | Unused feature, no graphical session on this server |
| AllowAgentForwarding | yes | no | Unused feature that exposes keys on forwarded connections |
| MaxSessions | 10 | 2 | Caps parallel sessions per connection |
| ClientAliveInterval / CountMax | default / 3 | 300 / 2 | Dead connections are dropped after about 10 minutes |

- **Verified:** nmap lists only `publickey` under the supported authentication methods (the baseline listed `publickey` and `password`), and a password-only attempt is refused with `Permission denied (publickey)` and no password prompt.

### 5.3 Firewall (UFW)

| Rule | Direction | Port / source | Reason |
|---|---|---|---|
| Default policy | incoming | all | **Deny.** A closed-by-default firewall means a forgotten or newly started service fails safe. |
| Default policy | outgoing | all | **Allow.** The server needs outbound traffic for updates and DNS. Restricting it is on the "not hardened" list. |
| `limit` | incoming | 22/tcp from 192.168.56.1 only | Only the admin machine can reach SSH. `limit` also temporarily blocks an address that opens 6 or more connections in 30 seconds. |
| `allow` | incoming | 80/tcp from anywhere | nginx is the only public entry point. UFW added the matching IPv6 rule automatically. |
| none | incoming | 443/tcp | Nothing listens there, because there is no TLS certificate (see the limitations section). A rule for a closed port is clutter. |
| none | incoming | 8000/tcp | The API listens on localhost only, so nobody should reach it from outside. |

- **Verified:** the final nmap scan shows only ports 22 and 80 open, and port 8000 as filtered.
- **Closed versus filtered:** at baseline the other 65,533 ports answered with a reset (closed). After hardening they are silently dropped (filtered). The same scan took 12 seconds at baseline and 98 seconds afterwards, because dropped packets make a scanner wait for timeouts. That is a small benefit, not a defence by itself.
- **Trade-off observed:** the `limit` rule throttles any address that makes many connections, including the admin machine. During the final scan, a version-detection run reported port 22 as `tcpwrapped`, and a second scan seconds later reported it as `filtered`. After waiting, the same checks returned `open ssh` with only `publickey`. This is consistent with the rate limit tripping. I kept both original files, one labelled as superseded, and I kept the rule. The admin machine is exempt from fail2ban but not from the UFW rate limit.

### 5.4 Application deployment

At baseline the API ran by hand as the admin user (`mladmin`), listening on all interfaces. It now runs as a managed service with a dedicated account, behind nginx.

- **Service account:** `mlapi`, a system user with no home folder and the shell `/usr/sbin/nologin`. Nobody can log in as it, and a compromised API process gets no shell and no home directory.
- **Code location:** `/opt/ml-api`, owned by root. The service account can read and run the code but cannot modify it, so a hijacked process cannot rewrite its own code. Verified: `sudo -u mlapi touch /opt/ml-api/test.txt` fails with `Permission denied`, while importing the application as `mlapi` succeeds.
- **Configuration:** the application reads settings only from environment variables. They live in `/etc/ml-api/ml-api.env`, owned by root with mode 600, outside the code folder so a code update cannot overwrite them. systemd reads the file as root before dropping privileges, so the running service cannot read its own config file from disk. Verified: `sudo -u mlapi cat` on that file fails with `Permission denied`. The file holds model parameters only, with no credentials, and the trade-off is that values handed to the process through the environment are visible to root.
- **Network binding:** Uvicorn listens on `127.0.0.1:8000` only. From the admin machine, port 8000 changed from open (baseline) to unreachable.
- **Production mode:** with `MLAPI_ENVIRONMENT=production` the application serves no interactive docs and no OpenAPI schema, which would otherwise describe the whole API to anyone who asks. This is covered by automated tests (16 tests pass).
- **Process management:** a systemd unit starts the service at boot and restarts it on failure. Across several reboots during this project, the service came back by itself every time.

**nginx reverse proxy.** nginx is the single public entry point on port 80.

| Setting | Reason | Observed |
|---|---|---|
| Only `/health` and `/predict` are proxied, every other path returns 404 | Even a route added to the app later would not be reachable by accident | `/docs` and `/openapi.json` return 404 through nginx |
| `server_tokens off` | The `Server` header does not announce the nginx version | Header reads `nginx` with no version, and nmap reports `nginx` with no version |
| `client_max_body_size 16k` | The largest valid request is 64 numbers, far below 16 KB, so anything bigger is refused before it reaches Python | A 20,000-byte body returns 413 |
| Rate limit of 10 requests per second per client address, burst 20 | Blunts floods and scripted abuse | Configured, not load-tested |
| `X-Content-Type-Options: nosniff` | Stops browsers from guessing content types | Configured |

The application also validates input itself (unknown fields, empty or oversized lists, NaN and infinity are all rejected with a 422), so nginx is a second layer and not the only one.

### 5.5 Service sandbox (systemd)

- **Measure:** `systemd-analyze security ml-api` reported an exposure level of **9.2 UNSAFE** before the change and **1.4 OK** after.
- **Change:** a drop-in file, `deploy/hardening/ml-api-10-sandbox.conf`, which leaves the original unit file untouched. The service writes nothing to disk and needs no privileges, so almost everything could be switched off.

| Group | Settings | Reason |
|---|---|---|
| Privileges | `NoNewPrivileges`, empty `CapabilityBoundingSet` and `AmbientCapabilities`, `RestrictSUIDSGID` | The process cannot gain privileges or any Linux capability. The API only uses an unprivileged port. |
| Filesystem | `ProtectSystem=strict`, `ProtectHome`, `PrivateTmp`, `PrivateDevices`, `UMask=0077` | The whole filesystem is read-only to the service, with no home folders and no device access |
| Kernel | `ProtectKernelTunables`, `ProtectKernelModules`, `ProtectKernelLogs`, `ProtectControlGroups`, `ProtectClock`, `ProtectHostname` | A hijacked API cannot tamper with kernel settings or the clock |
| Processes | `ProtectProc=invisible`, `ProcSubset=pid` | It cannot see other users' processes |
| Attack surface | `RestrictAddressFamilies=AF_INET AF_INET6 AF_UNIX`, `RestrictNamespaces`, `RestrictRealtime`, `LockPersonality` | Only the socket types it actually uses |
| Code execution | `MemoryDenyWriteExecute`, `SystemCallFilter=@system-service` with `~@privileged`, `SystemCallArchitectures=native` | Blocks memory that is both writable and executable, which injected code needs, and denies privileged system calls |

- **Risk accepted:** `MemoryDenyWriteExecute` and the system-call filter are the settings most likely to break a Python service, so they were the first I would have relaxed. The service started and answered normally with both enabled.
- **Verified:** the service is `active`, `/health` returns `ok`, and a prediction through nginx from the admin machine returns the same score as before the sandbox (0.9644).
- **Not investigated:** I did not look at which checks make up the remaining 1.4. It is in the OK band, and I judged further restrictions not worth the extra risk of breaking the service.

### 5.6 Kernel settings (sysctl)

The settings are in `deploy/hardening/sysctl-99-hardening.conf`. Only eight values were recorded before the change, so the table shows those. The file also sets the IPv6 and `default` variants, `accept_source_route` and `icmp_echo_ignore_broadcasts`, whose starting values I did not record.

| Setting | Before | After | Reason |
|---|---|---|---|
| `net.ipv4.conf.all.rp_filter` | 2 | 1 | Strict reverse-path filtering drops packets with source addresses that could not arrive on that interface (anti-spoofing) |
| `net.ipv4.conf.all.send_redirects` | 1 | 0 | This host is not a router |
| `net.ipv4.conf.all.log_martians` | 0 | 1 | Logs impossible source addresses, which helps the audit trail |
| `kernel.kptr_restrict` | 1 | 2 | Hides kernel addresses, which makes exploits harder to aim |
| `fs.suid_dumpable` | 2 | 0 | Privileged processes never write core dumps that could leak secrets |
| `net.ipv4.conf.all.accept_redirects` | 0 | 0 | A server must not let strangers rewrite its routing table. Already at the target, and the file pins it. |
| `net.ipv4.tcp_syncookies` | 1 | 1 | Keeps the server answering during a SYN flood. Already at the target. |
| `kernel.dmesg_restrict` | 1 | 1 | Unprivileged users cannot read kernel logs. Already at the target. |

Three settings were already correct because Ubuntu's defaults are partly sound. The file states them anyway so a later change cannot weaken them silently.

**Two settings were silently overridden.** After applying the file, a check showed that two live values did not match it. Both were found only because I compared the live value with the file, not because a scan flagged them.

1. **`fs.suid_dumpable` went back to 2 after a reboot.** The file was correct and no other sysctl file mentioned the setting. Ubuntu's crash reporter (apport) was enabled and active, and `core_pattern` piped crashes into it. After I disabled apport the value held at 0 across a reboot, which confirms the cause. Trade-off: a crash now leaves less diagnostic information. This server sends no crash reports anywhere and a crash dump of the API could hold model data, so I accepted that.
2. **`log_martians` read 0 in the final Lynis facts file, even though the file sets it to 1.** UFW loads its own file (`/etc/ufw/sysctl.conf`, pointed to by `IPT_SYSCTL` in `/etc/default/ufw`) whenever it starts, and that file set both values to 0. I changed those two lines (`deploy/hardening/ufw-sysctl.diff` shows the exact diff) and reloaded UFW. After a reboot, a check of every setting in the file against its live value found no mismatches.

**Timing matters for reading the evidence.** The `log_martians` fix came after the final Lynis run (`after2`). So `docs/evidence/after2/after2-facts.txt` correctly records `log_martians = 0`, the value live at that time. Everything else in that file reflects the final state. The final nmap scans in `after-nmap/` were taken after the fix.

**Lesson:** a configuration file is not proof of the running state. Both overrides were components with a legitimate reason to touch the setting, which is why they are easy to miss.

### 5.7 fail2ban

- **Why it still earns a place:** with password login off, nobody can guess their way in, so fail2ban is not stopping a break-in. It adds defence in depth: it reduces scanner noise in the logs and bans sources that keep opening connections without authenticating.
- **Settings** (`deploy/hardening/fail2ban-00-hardening.local`): the `sshd` jail reads the systemd journal, `maxretry = 3`, `findtime = 10m`, `bantime = 1h`, and `mode = aggressive`. Aggressive mode also counts dropped pre-authentication connections, which is how most scanners show up once passwords are disabled. The trade-off is that it can ban a client with a misconfigured key, which is why the admin address (192.168.56.1) is on the ignore list.
- **Verified:** the jail is active and reads the journal. A manual test ban of a reserved documentation address (203.0.113.7) raised the jail's total-banned counter to 1. I did not capture the resulting firewall rule, so I cannot show that the ban became a firewall rule.
- **Unresolved:** at one point the jail showed 2 failed attempts that I could not trace to a source. Counters reset on restart, and I did not investigate further. The admin address is on the ignore list, so it cannot have been banned.

### 5.8 Core dumps and unused network protocols

- **Core dumps:** `* hard core 0` in `/etc/security/limits.d/99-no-core.conf` for login sessions, and `LimitCORE=0` in the service drop-in. A crash dump of the API could hold model parameters or request data, and nobody needs one on this server. Lynis `KRNL-5820` no longer appears in the final scan.
- **Protocols:** `install <module> /bin/false` entries in `/etc/modprobe.d/99-disable-protocols.conf` block DCCP, SCTP, RDS and TIPC. They are rarely used and have a history of kernel bugs, and this server uses none of them. Verified: `modprobe -n -v dccp` reports `install /bin/false`, and none of the four modules is loaded.
- **Not resolved:** Lynis `NETW-3200` still flags all four protocols in the final scan, although they are blocked. Lynis evidently checks for something other than what I did. I did not investigate which mechanism it expects, and I do not claim these findings as fixed.

## 6. Results

### 6.1 Lynis across three runs

| Run | Hardening index | Warnings | Suggestions | Note |
|---|---|---|---|---|
| Before | 61 | 1 | 47 | Baseline |
| After 1 | 67 | 1 | 42 | Taken while 7 security updates were pending and before the apport fix. Kept for the record. |
| After 2 | 71 | 0 | 41 | Final result for Lynis |

The Lynis index is a heuristic score from a configuration checklist, so I rely on it alongside the nmap scans, the `systemd-analyze` score and the host facts, not instead of them.

### 6.2 Which findings changed (baseline compared with After 2)

Of the 48 baseline findings, 10 are gone and 3 are new, which leaves the 41 reported by the final scan.

| Finding | Status | Cause |
|---|---|---|
| FIRE-4512 (warning: no firewall rules) | Fixed | UFW, default deny |
| DEB-0880 "install fail2ban" | Fixed | fail2ban |
| KRNL-5820 core dumps | Fixed | Limits file and `LimitCORE=0` |
| SSH-7408, seven items (AllowTcpForwarding, ClientAliveCountMax, LogLevel, MaxAuthTries, MaxSessions, X11Forwarding, AllowAgentForwarding) | Fixed | SSH drop-in file |
| FIRE-4513 "check unused iptables rules" | New | Appears because a firewall now exists. It is UFW's own rule set, not a defect. |
| DEB-0880 "copy jail.conf to jail.local" | New | By my reasoning it does not apply, because the jail settings are in `jail.d/`, which package updates do not overwrite. I did not test that. |
| HTTP-6710 "add HTTPS to nginx" | New, real gap | nginx was not installed at baseline, so the test did not run then. See section 8. |

### 6.3 What each tool saw, and what each missed

| Weakness | nmap | Lynis | Found by |
|---|---|---|---|
| SSH password login enabled | Yes (auth-methods script) | No | nmap and the host facts |
| API application port exposed on all interfaces | Yes (8000 open) | No | nmap and `ss` |
| 17 pending updates | Indirectly (service version string) | Only once updates were pending alongside a library flagged as vulnerable | Package manager |
| No firewall | Closed ports answered with resets | Yes (warning FIRE-4512) | All three |
| Two sysctl values overridden by other components | No | No | Comparing live values with the config file by hand |

Lynis checks configuration against a profile, so it cannot know what a server is for and did not flag two of the largest remote risks. The two overridden kernel settings were not reported by any scanner at all. Using several tools, and checking the live state, found more than any one of them.

### 6.4 External view (nmap)

| | Before | After |
|---|---|---|
| Open ports | 22 (OpenSSH 9.6p1), 8000 (Uvicorn) | 22 (OpenSSH 9.6p1), 80 (nginx, no version) |
| Port 8000 | open | filtered |
| Other 65,533 ports | closed (reset) | filtered (no response) |
| SSH login methods | publickey, password | publickey |
| Scan time | 12 seconds | 98 seconds |

The SSH version string is still visible after hardening. I did not try to hide it, because the protocol announces it and the real defences are the patched build, key-only login and the firewall.

## 7. What I chose not to harden, and why

| Item | Reason |
|---|---|
| GRUB boot-loader password (BOOT-5122) | Physical access is out of scope, and on a headless VM it adds a lockout risk |
| Separate partitions for /home, /tmp, /var (FILE-6310) | Set at install time and would need a reinstall. They only reduce the impact of a full disk, and this VM is disposable. |
| USB storage drivers (USB-1000) | Not hardened. The VM has a virtual USB (OHCI) controller enabled in VirtualBox. I intended to disable it in the VM setup, but the setting did not take effect. Inside the guest, `lsusb` shows only the root hub and a VirtualBox USB tablet, with no storage device attached, and the USB storage driver is not blocked. |
| Password hashing, strength and ageing (AUTH-9229, 9230, 9262, 9282, 9286) | Remote password login is turned off. Forced periodic rotation is also discouraged by current NIST guidance (SP 800-63B). |
| Moving SSH off port 22 (SSH-7408 Port) | Obscurity. Keys, the firewall limit and fail2ban already cover the real threat. |
| SSH TCPKeepAlive (SSH-7408) | Marginal gain and debated, and it can drop legitimate sessions |
| Central or external logging (LOGG-2154) | There is no log server for a single lab host. In production, logs would ship off the box. |
| auditd and process accounting (ACCT-9622, 9626, 9628) | Useful, but I did not have time to design rules and a retention policy, so I chose not to enable a default setup with no one reading it |
| File-integrity tool and malware scanner (FINT-4350, HRDN-7230) | Noise and maintenance cost that is not justified on a disposable VM |
| Restricting compilers (HRDN-7222) | Could break package builds when dependencies are updated |
| Custom AppArmor profile for the API | systemd sandboxing gave most of the benefit (exposure 9.2 to 1.4), and a hand-written profile costs more than it adds here |
| Restricting outbound traffic | The server needs outbound traffic for updates and DNS. Production would use an egress proxy. |
| Full-disk encryption | The VM is disposable and holds no sensitive data, and it adds friction at boot |
| HTTPS | Not done. See section 8. |
| Admin conveniences and banners (DEB-0280, 0810, 0811, PKGS-7370, 7394, TOOL-5002, NAME-4028, BANN-7126, 7130, LYNIS) | No effect on this server's risk. The LYNIS note only reports that the packaged Lynis 3.0.9 is old, which is a limitation of these results. |

## 8. Limitations and unresolved items

### 8.1 HTTPS is not implemented

API requests travel over plain HTTP on port 80. I chose not to add a certificate in this project, for three reasons:

- Adding TLS means opening port 443 and changing nginx and the firewall. That would make the final nmap and Lynis scans describe a different server, so they would have to be repeated.
- A self-signed certificate adds little here. Clients cannot verify its identity, so it would encrypt traffic without proving who is on the other end. A trusted certificate needs a public domain name and a certificate authority.
- The lab network is host-only, so the only machine that can see the traffic is the admin machine.

The risk is real outside that lab. On a shared or public network, requests and responses could be read or modified in transit. Lynis flags this as HTTP-6710, and I list it as a gap, not as an accepted risk.

### 8.2 What the evidence does not show

- **One scan per stage.** Each scan was run once, so I have no measure of how much results vary between runs. The Lynis index moved from 61 to 71, which I treat as indicative only.
- **Old Lynis release.** The Ubuntu-packaged Lynis 3.0.9 reported itself as more than four months old. A newer release may include checks that this one lacks.
- **Lab network only.** The server was never exposed to the internet, so the results say nothing about internet-scale scanning or real attack traffic.
- **fail2ban was only partly tested.** I proved the jail runs and counts a manual ban. I did not run a real brute-force attempt against it, and I did not capture the firewall rule that the test ban created.
- **Rate limits not load-tested.** The nginx request limit and the UFW SSH limit are configured. Only the UFW limit was observed in action, and only by accident, when a scan tripped it.
- **`apply.sh` is untested.** It documents the order I followed. I have not run it end to end on a fresh machine, and its `patch` step is the part I am least sure of.
- **Kernel-setting baseline is partial.** Only eight values were recorded before hardening, so the table shows only those.
- **The first Lynis "after" run is superseded.** It was taken before two fixes and before the final patching, and it is kept for the record only.
- **Application code was not reviewed.** A security review of the API itself is out of scope here.

### 8.3 Unresolved findings

- **NETW-3200:** Lynis still flags DCCP, SCTP, RDS and TIPC, although `modprobe` reports them blocked. I did not find out which mechanism Lynis expects.
- **Two failed SSH attempts:** fail2ban once showed two failures that I could not trace to a source, and a restart cleared the counters. I did not investigate further.
- **Kernel patching needs a manual reboot.** I chose not to enable automatic reboots, so a kernel fix can sit unapplied until someone restarts the host.

## 9. What I would do next

1. Add TLS with a trusted certificate (a public domain name and an ACME client), open 443, redirect 80 to it, and repeat both scans.
2. Ship logs off the host and add auditd rules with someone responsible for reading them.
3. Run a real brute-force test against the SSH jail, and capture the resulting firewall rule.
4. Load-test the nginx rate limit and tune it against legitimate traffic.
5. Test `apply.sh` on a fresh VM, fix what breaks, and run both scans on the result. That would show whether the hardening is reproducible.
6. Find out which mechanism Lynis expects for NETW-3200, and repeat the audit with a current Lynis release.
7. Review the API code itself, which this project deliberately left out.

## 10. Reproducing this work

- `deploy/systemd/` and `deploy/nginx/` hold the service unit and the proxy config.
- `deploy/hardening/` holds every hardening file and `apply.sh`, which records the order of the changes.
- `docs/evidence/` holds the raw scan output for every stage.
- The VM was built from the Ubuntu Server 24.04.5 LTS ISO. Its SHA-256 checksum was compared with the value Ubuntu publishes before installing, and the two matched.
