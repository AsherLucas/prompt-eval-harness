# Provider guide (v0.2.0)

prompt-eval-harness v0.2.0 has three providers: `stub`, `openai`
(any OpenAI-compatible endpoint), and `ollama` (a local
OpenAI-compatible server, default `http://localhost:11434/v1`, no
API key required). Pick the provider with the `--provider` flag
(`stub` is the default). OpenAI-compatible providers retry
transient failures (HTTP 429/5xx, network errors) and report token
usage when the provider returns it.

> **Honest status: this is an early-stage tool** with no stars,
> downloads, or users claimed, and it does not yet qualify for any
> six-month maintainer programme.

## `stub` — offline, canned outputs

The stub provider never calls the network and never needs a key.
For each case, the runner uses the case's `stub_output` when one
is set; otherwise the stub provider returns a placeholder of the
form `stub response for <case-id>`.

```bash
python -m prompt_eval run --cases examples/cases.yaml --provider stub
```

Use stub for:

- Offline demos and first runs.
- Tests and CI smoke runs (free, reproducible, no secrets).
- Checking that a case file and its expectations are written
  correctly before spending money on a real model.

Do **not** use stub as evidence that a model is good: a stub run
only proves the harness and the case file work. In real use,
remove `stub_output` from your cases and run a real provider, so
outputs come from a model. Note the trap in the other direction:
if you leave `stub_output` in a case file and run with a real
provider, the `stub_output` is ignored — the real provider's
output is scored instead — so a passing stub file tells you
nothing about the real run.

## `openai` — any OpenAI-compatible `/chat/completions` endpoint

The `openai` provider is a minimal client (standard library only)
that POSTs to `{base-url}/chat/completions` with a JSON body of
`{"model": <model>, "messages": [{"role": "user", "content":
<prompt>}], "temperature": 0}` and reads the reply from
`choices[0].message.content`. That is the whole contract: if an
endpoint does not accept that shape or does not return it, the
case records a provider failure (see below).

### Flags

| Flag | Default | Meaning |
| ---- | ------- | ------- |
| `--provider openai` | `stub` | Select this provider. |
| `--base-url` | `https://api.openai.com/v1` | Base URL; `/chat/completions` is appended, and a trailing `/` is stripped first. Only used by the `openai` provider. |
| `--model` | `gpt-4o-mini` | Model name sent in the request body and recorded in reports. |
| `--api-key-env` | `OPENAI_API_KEY` | Name of the environment variable holding the API key. Only used by the `openai` provider. |

### API keys: environment variables only, never hardcoded

Set the key in the environment before running. Never put a key in
a case file, on the command line, in a workflow file, or in a log:

```bash
export OPENAI_API_KEY="..."   # from your provider, never commit it
python -m prompt_eval run --cases my-cases.yaml --provider openai \
  --model gpt-4o-mini --prompt-version v3
```

To use a different key variable, name it with `--api-key-env` —
do not paste the key itself into the flag:

```bash
export MY_API_KEY_ENV="..."
python -m prompt_eval run --cases my-cases.yaml --provider openai \
  --api-key-env MY_API_KEY_ENV
```

The key is read from the environment at call time, sent only as a
`Bearer` authorization header to the configured base URL, and
never logged: only the fact that a key was missing is reported.
In CI, pass the key as a secret into that environment variable.

### What happens when the provider fails

A provider failure does not crash the run. The affected case is
recorded with a single failed `provider` expectation and an empty
output, the other cases still run, and the gate fails (exit code
1). The failure detail tells you which of these happened:

- Key missing: `environment variable <NAME> is not set; set it
  (do not paste a key into a case file or log) or use --provider
  stub for offline runs`.
- HTTP error: `provider returned HTTP <code>` (the body is not
  shown, so a rejected key and a bad model name look the same
  here — check the base URL, model name, and key separately).
- Network error: `provider request failed: <reason>`.
- Unexpected response shape: `provider response had an unexpected
  shape` (the endpoint did not return
  `choices[0].message.content` as expected).

There is no retry, no timeout flag on the CLI (the client uses a
60-second request timeout internally), and no per-case model
override: one run uses one base URL and one model for all cases.

## Local OpenAI-compatible endpoints (e.g. Ollama-style)

Any locally served endpoint that speaks the OpenAI-compatible
`/chat/completions` API can be used by pointing `--base-url` at
it, exactly as for a hosted endpoint:

```bash
python -m prompt_eval run --cases my-cases.yaml --provider openai \
  --base-url http://localhost:11434/v1 --model <your-local-model>
```

Notes and limits, stated plainly:

- Only the base URL is configured here. This guide does not invent
  endpoint-specific behaviour: the harness still sends the same
  `{"model", "messages", "temperature": 0}` body and still reads
  `choices[0].message.content`, whatever server is behind the URL.
  If your local server needs different request fields or returns a
  different shape, v0.2.0 cannot adapt to it — the case will record
  a provider failure as above.
- A local endpoint usually needs no real key, but the client still
  requires the named environment variable to be set and sends it
  as a `Bearer` token. Set it to any placeholder value for a
  keyless local server rather than leaving it unset, or the run
  fails with the missing-key message above. Never use a real
  production key as that placeholder.
- The model name is passed through verbatim: it must be a model
  name your local server actually serves, or the server will
  reject the request and the case will fail as a provider error.

## Choosing between the two

| Situation | Provider |
| --------- | -------- |
| Demo, test, CI smoke run, case-file authoring | `stub` |
| Evaluating a real model or a real endpoint | `openai` (hosted or local base URL) |
| No key available, or no network | `stub` — the only option that works |

A healthy workflow uses both: author and smoke-test cases with
`stub`, then run the same case file (with `stub_output` removed)
against `openai` for real signal.
