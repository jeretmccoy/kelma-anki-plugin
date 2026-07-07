# Kelma Dual Sync (Anki add-on)

Keeps your Anki/Kelma desktop collection synced to **KelmaSync** and/or
**AnkiWeb**, with **per-deck routing** — each deck can go to both services or just
one.

## Source and license

This repository contains the source code for the Kelma add-on for Anki. It is
distributed under the GNU Affero General Public License v3.0; see
[`LICENSE`](LICENSE).

## How it works

You study in your normal collection (the *master*). For each service the add-on
keeps a background **shadow collection** that contains only the decks routed to
that service, and:

1. **pushes** the master's routed decks into the shadow (newest-wins),
2. **two-way syncs** the shadow with its server (real Anki sync — so edits from
   your phone/other devices merge back),
3. **pulls** the shadow's decks back into the master (newest-wins).

Reconciliation uses Anki's own package import/export with `If Newer`, so merging
(by note GUID, with scheduling + media) reuses Anki's battle-tested logic instead
of a hand-rolled merge. **Deletions** are propagated separately by replaying each
collection's `graves` (deleted note/card ids) into the other.

```
            study here
          ┌───────────┐
          │  MASTER   │  (all decks)
          └─────┬─────┘
      push/pull │ (per routed deck, newest-wins)
        ┌───────┴────────┐
        ▼                ▼
 ┌────────────┐   ┌────────────┐
 │Kelma shadow│   │Anki shadow │
 └─────┬──────┘   └─────┬──────┘
       ▼ two-way        ▼ two-way
   KelmaSync          AnkiWeb
```

## Routing (per deck)

Open **Tools → Kelma → Settings & deck routing**:

- Log in to KelmaSync and/or AnkiWeb.
- In the deck table, tick **KelmaSync** and/or **AnkiWeb** for each deck (filter
  box + bulk buttons make it quick). A deck with neither ticked syncs nowhere.
- Each cloud column also shows that deck's **pending state** since the cloud last
  synced: `+n` cards added, `~n` changed, `✓` in sync. A summary line above the
  table totals it per cloud (plus collection-wide pending deletions). **Refresh**
  recomputes after studying.
- New decks default to **KelmaSync only**.
- **Enable dual sync** is the master off-switch (off ⇒ stock AnkiWeb sync).

There is no global mode — routing is entirely per deck.

## Separate services + KelmaSync sync modes

KelmaSync and AnkiWeb are synced as **two distinct operations** — the progress
bar shows `KelmaSync: …` then `AnkiWeb: …`, never a merged "dual sync". If one
service fails, the other still runs; a combined summary is shown.

**Per-deck badges on the deck list.** Each deck on Anki's main screen shows a
small badge per cloud it's routed to — `K`/`W` for KelmaSync/AnkiWeb — with its
pending state (`+n` added, `~n` changed, `✓` in sync) since that cloud last
synced. Badges update after syncing or studying.

**The Sync button is a split menu.** Clicking Sync opens a small menu with a
details header (per service: account · routed decks · mode · last sync) and three
choices: *Sync KelmaSync + AnkiWeb*, *Sync KelmaSync only*, *Sync AnkiWeb only*.
The same actions live under **Tools → Kelma**.

**Only changed decks move (in one transfer).** Each deck has a cheap fingerprint
(card count + newest card/note mod), stored in `kelma_state.json`. A sync diffs
fingerprints against the last baseline and exports **all** changed decks in a
single batched apkg — never one-deck-at-a-time. If nothing changed, it transfers
nothing. The first sync after upgrading does one full pass to establish the
baseline.

KelmaSync has two sync paths (set in **Settings → KelmaSync mode**):

- **Standard** (incremental) — fingerprints the collection in two quick SQL
  queries, then moves only the decks that actually changed since the last sync,
  all in **one** batched transfer. Routine syncs are near-instant.
- **Legacy** — moves every routed deck every time; maximal compatibility with
  **AnkiMobile** and stock Anki sync servers. Slower.
- **Auto** (default) — probes the server (`GET /kelma/capabilities`) and picks
  one; a server that advertises `{"legacy": true}` forces legacy. Manual choice
  always wins.

AnkiWeb is always legacy — real AnkiWeb only speaks the stock protocol.

## Install (development)

```bash
cd plugin
./build.sh dev      # symlink src/ into your Anki addons folder
# FULLY QUIT Anki (⌘Q — the red ● only hides the window), then relaunch.
# Tools → Kelma → Settings & deck routing  (log in + tick decks)
```

Package for distribution:

```bash
./build.sh          # creates dist/kelma.ankiaddon
```

## Status & limitations (v1)

- Requires modern Anki (Rust backend, ~23.10+).
- First sync of a new shadow seeds from the server, then converges.
- Note/card **deletions are propagated** (via graves). *Deck* deletions are not
  auto-propagated (left to avoid destructive surprises).
- **Not yet handled:** truly excluding an `AnkiWeb only` deck *from* KelmaSync
  (the master holds all decks).
- Treat host keys in the config as secrets.
