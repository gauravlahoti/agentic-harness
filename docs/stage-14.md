# Stage 14 · Public Tour Mode: the tour, hosted for anyone

> The harness was built to run on your own machine, for you alone. To show it on a website,
> the same server needs a second mode: open to anyone, and unable to change or spend anything.

## What you have now

- **One switch.** `HARNESS_PUBLIC=1` turns on public tour mode. Without it nothing changes: the server still answers only `127.0.0.1` and `localhost`.
- **Read-only, by one rule.** In public mode the server answers only GET and HEAD. A POST, PUT, PATCH or DELETE gets **403**, whatever the route. So nobody can start a run, record over the voice, run the tests, approve, or delete.
- **No key.** `config.py` reads no key in public mode, even if one is in the environment or `.env`. The model can't be called, so the tour can't cost anything.
- **The page knows.** `/api/health` says `"mode": "public"`. The page opens on the tour and waits on **Start Tour** (browsers play sound only after a click). A note in the sidebar says it's read-only and links to the code. Tools a visitor can't use are hidden.
- **Hosting.** A `Dockerfile`, two allowlists (`.gcloudignore`, `.dockerignore`) and `make deploy-tour`.

## The files

| File | What changed |
|---|---|
| `config.py` | `public`, `allowed_hosts`, `port` on `Settings`; keys dropped when public |
| `cli.py` | Public mode listens on `0.0.0.0` and `$PORT`; there is still no `--host` option |
| `server/app.py` | Allowed names; the GET/HEAD-only middleware; `mode` and `repository` in health; clips cached by version |
| `web/` | The note, the tour opening on its own, hidden controls |
| `Dockerfile`, `.gcloudignore`, `.dockerignore`, `Makefile` | Build and deploy, with nothing secret in the upload |

## Why an allowlist for the upload

`gcloud run deploy --source .` uploads the folder. With no `.gcloudignore` it follows `.gitignore`. That would leave out the voice clips, which are git-ignored on purpose, and it still wouldn't promise to leave out everything else. An allowlist names what goes up (the Dockerfile, the lock files, `src/`, `workspaces/cloudco/`) and nothing else. `.env*` is excluded on top of that.

Check it before every deploy:

```bash
gcloud meta list-files-for-upload .   # the 10 clips are listed; .env is not
```

## Verify it yourself

1. `make check`. All green, including `tests/unit/test_public_mode.py`.
2. `HARNESS_PUBLIC=1 PORT=8091 uv run agentic-harness serve --workspace workspaces/cloudco`, then open http://127.0.0.1:8091. It opens on the tour. Start it and the voice plays. The note says it's read-only.
3. `curl -X POST -H 'X-Harness-Page: 1' http://127.0.0.1:8091/api/run`. You get 403, even though your `.env` holds a key.
4. `curl http://127.0.0.1:8091/api/health`. You see `"key": "missing"` and `"mode": "public"`.
