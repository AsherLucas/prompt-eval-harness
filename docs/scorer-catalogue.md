# Scorer catalogue (v0.2.0)

All scorers are deterministic and offline: none of them calls a
model, and none of them needs the network. A case passes only if
every expectation in its `expected` list passes. An unknown scorer
`type` fails that expectation with an "unknown scorer type" detail.

Parameter defaults below are the v0.2.0 code defaults, read from
`src/prompt_eval/scorers.py`. Where a parameter is not listed for a
scorer, it is ignored by that scorer.

> **Honest status: this is an early-stage tool** with no stars,
> downloads, or users claimed, and it does not yet qualify for any
> six-month maintainer programme. In v0.2.0, `json_schema` is full
> JSON Schema validation (via the `jsonschema` package), custom
> scorers can be registered via `register_scorer()` or the
> `prompt_eval.scorers` entry-point group (see
> `examples/plugin_example.py`), and an LLM-as-judge scorer exists
> as an advisory-only result — it never counts toward the CI gate
> (see the README).

## `exact` — output equals a value

| Parameter | Type | Default | Meaning |
| --------- | ---- | ------- | ------- |
| `value` | string | `""` | The expected output. |
| `case_sensitive` | boolean | `true` | Compare case-sensitively when `true`; both sides are lowercased when `false`. |
| `strip` | boolean | `true` | Strip surrounding whitespace from both sides before comparing when `true`. |

Example:

```yaml
- type: exact
  value: "Hello, world!"
```

- Pass: output `Hello, world!`
- Fail: output `Hello, World!` — detail: `expected exactly
  'Hello, world!', got 'Hello, World!'` (default
  `case_sensitive: true`).

With `case_sensitive: false`, output `YES` passes against
`value: "yes"`. With `strip: true` (the default), output
`"  padded  "` passes against `value: "padded"`.

## `regex` — output matches a pattern

| Parameter | Type | Default | Meaning |
| --------- | ---- | ------- | ------- |
| `pattern` | string | `""` | Regular expression searched for anywhere in the output (`re.search`, not a full match). |
| `ignore_case` | boolean | `false` | Add `re.IGNORECASE` when truthy. |
| `multiline` | boolean | `false` | Add `re.MULTILINE` when truthy. |

Example:

```yaml
- type: regex
  pattern: "[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}"
```

- Pass: output `Contact us at team@example.com for help.` (the
  pattern is found inside the output; the output need not be only
  an email address — for that, use `format` with `kind: email`).
- Fail: output `Contact us for help.` — detail: `no match for
  '<pattern>' in output`.

An invalid pattern fails the expectation with an `invalid regex`
detail instead of crashing the run.

## `json_schema` — output parses as JSON and matches a full schema

| Parameter | Type | Default | Meaning |
| --------- | ---- | ------- | ------- |
| `schema` | mapping | `{}` | Schema to check, validated in full. |

This is **full JSON Schema validation** via the `jsonschema`
package (Draft 2020-12), not the v0.1.0 subset — the subset
description in older versions of this catalogue was outdated and
has been corrected. Keywords such as `allOf`/`anyOf`/`oneOf`/
`not`, nested schemas, and format-independent keywords are all
checked. An invalid schema fails the expectation with an
`invalid schema: ...` detail instead of passing, and a non-JSON
output fails with `output is not valid JSON: ...`.

Example:

```yaml
- type: json_schema
  schema:
    type: object
    required: [name, age]
    properties:
      name: {type: string}
      age: {type: integer, minimum: 0}
```

- Pass: output `{"name": "Ada", "age": 36}`.
- Fail: output `{"name": "Ada"}` — detail: `$: 'age' is a
  required property`. A non-JSON output fails with `output is
  not valid JSON: ...`.

Other subset examples: `{"status": "done"}` against an `enum:
[pending, done, failed]` property passes, while `"other"` fails
with a `not in enum` detail; `[1, 2, 3]` against `type: array,
items: {type: integer}, minItems: 2` passes.

## `length` — character / word bounds

| Parameter | Type | Default | Meaning |
| --------- | ---- | ------- | ------- |
| `min_length` | integer | (none) | Minimum character count (`len(output)`). |
| `max_length` | integer | (none) | Maximum character count. |
| `min_words` | integer | (none) | Minimum word count (`len(output.split())`). |
| `max_words` | integer | (none) | Maximum word count. |

Only the bounds you set are checked; all set bounds must hold.
Character and word counts are counted on the raw output (no
stripping).

Example:

```yaml
- type: length
  min_length: 10
  max_length: 100
```

- Pass: output `This sentence is long enough.` (29 characters).
- Fail: output `Too short` (9 characters) — detail: `9 chars <
  min_length 10`.

A words example: `one two three four five` passes
`min_words: 4, max_words: 10` (5 words).

## `format` — output is well-formed

| Parameter | Type | Default | Meaning |
| --------- | ---- | ------- | ------- |
| `kind` | string | `""` | One of `json`, `email`, `url`, `lowercase`, `uppercase`. |

The output is stripped before checking (except that `json` also
parses the stripped text). Unknown kinds fail the expectation.

Example:

```yaml
- type: format
  kind: email
```

- Pass: output `ada@example.org`.
- Fail: output `Contact us at ada@example.org` — the format check
  is about the whole (stripped) output, not a substring, so a
  sentence containing an email is **not** a valid email format.
  Detail: `'...' is not an email address`.

The other kinds:

- `json`: passes for `{"ok": true}`, fails for `{not json`.
- `url`: passes for `https://example.com/docs` (http or https
  only), fails for `example.com` or `ftp://example.com`.
- `lowercase`: passes for `all lowercase words here`, fails for
  `Hello there`.
- `uppercase`: passes for `ALL CAPS HERE`, fails for `All caps`.

To check both well-formedness and structure, combine scorers:
`format: {kind: json}` plus a `json_schema` expectation on the
same case.

## `contains_all` — output contains every listed string

| Parameter | Type | Default | Meaning |
| --------- | ---- | ------- | ------- |
| `strings` | list of strings | `[]` | Every string must appear in the output. |
| `case_sensitive` | boolean | `true` | Substring matching is case-sensitive when `true`; both sides are lowercased when `false`. |

Matching is by substring, not by word: `fox` matches inside
`foxes`.

Example:

```yaml
- type: contains_all
  strings: [quick, brown, fox]
```

- Pass: output `The quick brown fox jumps.`
- Fail: output `The quick brown dog jumps.` — detail: `missing
  strings: ['fox']`.

With `case_sensitive: false`, output `Hello WORLD` passes for
`strings: [hello]`.

## `citation` — RAG-style output cites sources

| Parameter | Type | Default | Meaning |
| --------- | ---- | ------- | ------- |
| `min_citations` | integer | `1` | Minimum number of citation markers found. |
| `pattern` | string | (default marker pattern) | Custom regular expression for citation markers. When empty/absent, the default pattern is used. |
| `required_sources` | list of strings | `[]` | Every string must appear somewhere in the output (plain substring check, not tied to a marker). |

Default marker pattern: `\[\d+\]|\[source:[^\]]+\]` — that is,
`[1]`, `[2]`, … or `[source: name]`, case-insensitive. When you
supply `pattern`, it **replaces** the default entirely; the count
is the number of matches of your pattern.

Example:

```yaml
- type: citation
  min_citations: 1
  required_sources: [user-guide]
```

- Pass: output `See the manual [source: user-guide] for details.`
  (1 marker found; `user-guide` appears in the output).
- Fail: output `See the manual for details.` — detail: `found 0
  citation(s), need >= 1`. Note the two checks are independent:
  an output can have enough markers but still fail if a required
  source string is missing, e.g. `[1]` alone fails the example
  above with `missing required sources: ['user-guide']`.

Two-marker example: `Claim A [1] and claim B [2].` passes
`min_citations: 2`. A custom pattern example: with
`pattern: 'Source:\s*\w+'`, output `The answer is Paris.
Source: wikipedia` passes `min_citations: 1`.
