# ShipForOneAlbum

I have 13 published albums.  I think this is my best one.  It's Open Source, remix and plunder my pirate mateys!

I wanted to upload the entire Session as .7z of each track.  But github only accepts 25mb?!?!  WHat year is this?!?! 1999??!?!?!?

## What this repository holds

- **One album: Ship For One.** Its 16 track names are in [`Track List`](Track%20List), one line each, including the parenthetical notes.
- **The `Sleep Tight` session:** `SleepTight/` holds 64 WAV stems plus `SleepTight/BasicInfo.md` ("The track has a LOT of small pieces.  I'll try to upload them all separately?!?") and the Ardour project file `SleepTight/SleepTightB.ardour`. The largest committed stem is `SleepTight/rhY Lead-5.wav` at 16,237,204 bytes.
- **The website source for rhYmusic.com:** `website/` (HTML, CSS, one dependency-free script, Cloudflare `_headers` and `_redirects`, a `node:http` preview server) plus `scripts/build-website.sh`, `website/check.py` and `.github/workflows/deploy-website.yml`.

No other album is in this repository, and no finished master mixdown is committed for any track.

Two track names carry an unresolved question from me: `Friday, Saturday (Can we?  Licensing?  The Specials)` and `Margaritaville (Can we? Jimmy Buffet)`. They are shown as **licensing unresolved** on the site and are not presented as cleared.

## Preview

```sh
cd website && node dev-server.mjs        # http://127.0.0.1:3000
# or, if you would rather not use node:
python3 -m http.server 3000
```

`dev-server.mjs` is dependency-free (`node:http` only, no npm install, no network) and refuses any path outside `website/`. The site links to the stems where they already live on GitHub; nothing here plays audio, opens a window or records anything.

## Check

```sh
python3 website/check.py
```

Standard library only, no network. It fails with a message if a page is missing, if any internal `href`/`src` does not resolve, if any `github.com/crhy/ShipForOneAlbum/...` or `raw.githubusercontent.com/crhy/ShipForOneAlbum/...` link names a path that is not in this checkout (percent-decoded first, so `Drumz-2%25L.wav` must decode to `Drumz-2%L.wav`), if a committed stem is not linked, if a track name is invented or missing from the 16 lines of `Track List`, if any `http://` link or absolute local path appears, if `package.json` does not parse with `dev` set to `node dev-server.mjs`, or if the deploy workflow embeds a credential instead of reading `CF_ACCOUNT_ID` / `CLOUDFLARE_API_TOKEN` through `secrets.`.

## Stage

```sh
bash scripts/build-website.sh   # -> build/website
```

Only the public site is staged: HTML, CSS, JS, `_headers`, `_redirects`, `404.html`. `SleepTight/` audio, `.git` and the repository root are never copied, and the script fails if anything unpublished leaks into the bundle. `build/` is gitignored.

## Domain ownership

rhYmusic.com is connected in Cloudflare, and this repository publishes it through `.github/workflows/deploy-website.yml`: build, then check, then publish **only `build/website`** to Cloudflare Pages. The deploy is reproducible from the repository — no local machine, no one's desktop folder, no manual upload.

- **Credentials are least-privilege and read from GitHub secrets** (`secrets.CF_ACCOUNT_ID`, `secrets.CLOUDFLARE_API_TOKEN`). When they are absent the deploy step is skipped rather than failed, so a fork or a fresh clone cannot publish and cannot break the check.
- **HTTPS is enforced at the edge** by `website/_headers`: HSTS with `includeSubDomains; preload`, `upgrade-insecure-requests`, `nosniff`, a CSP that frames nothing and loads nothing third-party.
- **DNS and rollback belong to the domain owner.** The Cloudflare account, the DNS zone for rhYmusic.com, the token that may edit it, and the decision to roll back or restore the domain are rhY's, not this repository's. Rollback is reproducible: redeploy the previous commit's `build/website`.

## Not done here

- The Cloudflare link itself: the account, the Pages project, the DNS zone and the least-privilege token are not created or changed by this repository.
- The licence decision: this repository ships no `LICENSE` file and this page names none. The "Open Source, remix and plunder my pirate mateys!" line above is my own wording, quoted unchanged; choosing a licence belongs to the project owner.
- The other 12 albums, and the two unresolved track licences above.
- Any master mixdown of the `Sleep Tight` session: only stems are committed.
