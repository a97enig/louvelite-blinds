# Louvelite Blinds (Neo Smart Controller) for Home Assistant

A minimal-by-design Home Assistant custom integration for blinds driven by
the Neo Smart Controller hub. Designed as a replacement for
`mtgeekman/Home_Assistant_NeoSmartBlinds` for the case where you just want
roller-blind up / down / stop without YAML, percentage sliders or tilt
controls that don't do anything on your hardware.

## What this does

- **No YAML.** Setup and management are entirely in the HA UI.
- **Two-tier model.** Register each physical remote once (its `ID1.ID2`
  prefix), then add blinds under it by channel — mirroring how you'd
  think about it in the Neo app, and avoiding repeated typing of the
  prefix for blinds that live behind the same remote.
- **Type-aware UI.** When you add a blind you pick a type:
    - **Roller** — exposes Open / Close / Stop only. No tilt. No position
      slider.
    - **Venetian** — Open / Close / Stop plus tilt up / tilt down / tilt
      stop.
    - **TDBU (Top-Down / Bottom-Up)** — creates two covers (top rail and
      bottom rail), each with Open / Close / Stop.
- **TCP (8839) or HTTP (8838).** Either protocol works; TCP is the
  default because it's been more reliable in practice. Hub
  connectivity is probed during setup so a wrong IP or hub ID fails
  immediately.
- **Multiple remotes.** Add as many remotes as you have.

## What this does NOT do

These are deliberate omissions, not TODOs:

- **No auto-discovery of the hub.** The Neo Smart Controller doesn't
  advertise itself over mDNS or SSDP, and there's no documented UDP
  broadcast probe. You need to enter its IP. If you don't already pin
  it via your router's DHCP reservation, do that first.
- **No "sync from hub".** The hub is a stateless command relay — it has
  no concept of which blinds exist; all of that metadata lives in the
  Neo app, with no public API to extract it. Blinds are added by hand.
- **No position slider / percentage open.** Most Neo-controlled rollers
  don't actually report their position back, so any percentage shown in
  the UI is at best a guess. This integration just doesn't pretend.
- **No cloud account.** Talks to the hub only over your LAN.

## Installation

### Via HACS (recommended)

1. HACS → Integrations → ⋮ → Custom repositories.
2. Add this repository's URL. Category: Integration.
3. Install **Louvelite Blinds (Neo Smart Controller)**.
4. Restart Home Assistant.

### Manual

Copy `custom_components/louvelite_blinds/` into your HA config's
`custom_components/` directory and restart HA.

## Setup

1. Settings → Devices & Services → **+ Add Integration** → search for
   **Louvelite Blinds**.
2. Enter:
    - **Hub IP address** — e.g. `192.168.1.50`.
    - **Hub ID** — 24-character ID from the Neo app
      (Menu → Controllers → tap the controller). Looks like
      `440036000447393032323330`.
    - **Protocol** — TCP (default) or HTTP.
    - **Port** — 8839 for TCP, 8838 for HTTP.
    - **Motor code** — leave blank unless your hub explicitly requires
      one (most don't).
3. After save, open the integration's **Configure** page. From there:
    - **Add a remote** — give it a name (e.g. "Living-room remote") and
      enter its `ID1.ID2` prefix. The prefix is the part of any blind
      code in the Neo app **before** the dash — e.g. for blind code
      `021.230-04`, the prefix is `021.230`.
    - **Add a blind** — pick the remote, enter the channel (1-15), name,
      optional room, type, and close-time.
        - Channel **15** is the broadcast channel — pressing it on the
          remote moves every blind paired to that remote at once. Add a
          "channel 15" entry per remote if you want a single
          `cover.kitchen_all` style entity.
4. Repeat **Add a blind** for each blind.

## Notes on close-time

`close_time` only affects travel estimation in HA's UI; this integration
doesn't drive blinds to a percentage. Stopwatch your blind once from
fully open to fully closed and use that number.

## Comparing to the existing integration

| | This integration | `mtgeekman/Home_Assistant_NeoSmartBlinds` |
|---|---|---|
| YAML required | No | Yes |
| Config flow + Options flow | Yes | No |
| Per-blind type selector | Roller / Venetian / TDBU | One implementation; tilt + percent always shown |
| Percentage open | Not exposed | Estimated from `close_time` |
| `motor_code` / `percent_support` / `parent_group` / `rail` | All hidden behind blind-type | All required in YAML |
| Group commands | Add a channel-15 blind | `parent_group` plus aggregation logic |

If you have venetians or use percentage positioning seriously, the
existing integration is more featureful. If you have rollers and want
the UI to stop offering controls that do nothing, this one is for you.
