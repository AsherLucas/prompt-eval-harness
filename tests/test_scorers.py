from prompt_eval.models import Expectation
from prompt_eval.scorers import score_expectation


def check(type_, output, **params):
    return score_expectation(output, Expectation(type=type_, params=params))


def test_exact_pass_fail_and_case_flag():
    assert check("exact", "hello", value="hello").passed
    assert not check("exact", "hello!", value="hello").passed
    assert check("exact", "YES", value="yes", case_sensitive=False).passed
    assert not check("exact", "YES", value="yes").passed
    assert check("exact", "  padded  ", value="padded").passed  # strip default


def test_regex_pass_fail_and_invalid():
    assert check("regex", "code E1234", pattern=r"E\d{4}").passed
    assert not check("regex", "no code", pattern=r"E\d{4}").passed
    assert not check("regex", "x", pattern="[").passed  # invalid regex -> fail, not crash


def test_json_schema_subset():
    assert check("json_schema", '{"a": 1}',
                schema={"type": "object", "required": ["a"],
                        "properties": {"a": {"type": "integer"}}}).passed
    assert not check("json_schema", '{"a": "x"}',
                     schema={"type": "object", "properties": {"a": {"type": "integer"}}}).passed
    assert not check("json_schema", '{"b": 1}',
                     schema={"type": "object", "required": ["a"]}).passed
    assert not check("json_schema", "not json", schema={"type": "object"}).passed
    # bool is not an integer in this implementation
    assert not check("json_schema", '{"a": true}',
                     schema={"type": "object", "properties": {"a": {"type": "integer"}}}).passed
    assert check("json_schema", '[1, 2]',
                schema={"type": "array", "items": {"type": "integer"}, "minItems": 2}).passed
    # Unsupported keywords are ignored by design (documented subset)
    assert check("json_schema", '{"a": 1}',
                schema={"type": "object", "properties": {"a": {"type": "integer"}},
                        "description": "ignored"}).passed


def test_length():
    assert check("length", "one two three", min_words=2, max_words=5).passed
    assert not check("length", "short", min_length=10).passed
    assert not check("length", "toolongword", max_length=5).passed


def test_format_kinds():
    assert check("format", '{"a": 1}', kind="json").passed
    assert not check("format", "{bad", kind="json").passed
    assert check("format", "a@b.co", kind="email").passed
    assert not check("format", "not-an-email", kind="email").passed
    assert check("format", "https://example.com", kind="url").passed
    assert not check("format", "ftp://example.com", kind="url").passed
    assert check("format", "lower case", kind="lowercase").passed
    assert not check("format", "Mixed", kind="lowercase").passed
    assert check("format", "UPPER", kind="uppercase").passed
    assert not check("format", "x", kind="mystery").passed


def test_contains_all():
    assert check("contains_all", "quick brown fox", strings=["quick", "fox"]).passed
    assert not check("contains_all", "quick fox", strings=["quick", "brown"]).passed
    assert check("contains_all", "HELLO", strings=["hello"], case_sensitive=False).passed


def test_citation():
    assert check("citation", "Claim [1].", min_citations=1).passed
    assert not check("citation", "No cites.", min_citations=1).passed
    assert check("citation", "A [1] B [2]", min_citations=2).passed
    assert not check("citation", "A [1] B [2]", min_citations=3).passed
    assert check("citation", "See [source: guide].",
                required_sources=["guide"]).passed
    assert not check("citation", "See [source: guide].",
                     required_sources=["other"]).passed


def test_unknown_scorer_fails_not_crashes():
    assert not check("nope", "anything").passed

def test_forbidden_scorer():
    from prompt_eval.models import Expectation
    from prompt_eval.scorers import score_expectation
    ok = score_expectation("hello world", Expectation(type="forbidden", params={"strings": ["secret", "password"]}))
    assert ok.passed
    bad = score_expectation("my password is x", Expectation(type="forbidden", params={"strings": ["password"]}))
    assert not bad.passed


def test_numeric_close_scorer():
    from prompt_eval.models import Expectation
    from prompt_eval.scorers import score_expectation
    ok = score_expectation("The total is 42.1 dollars", Expectation(type="numeric_close", params={"value": 42.0, "tolerance": 0.5}))
    assert ok.passed
    bad = score_expectation("The total is 50 dollars", Expectation(type="numeric_close", params={"value": 42.0, "tolerance": 0.5}))
    assert not bad.passed
    none = score_expectation("no numbers here", Expectation(type="numeric_close", params={"value": 1}))
    assert not none.passed


def test_tool_call_contract():
    from prompt_eval.scorers import score_expectation
    from prompt_eval.models import Expectation
    ok = score_expectation('{"tool": "get_weather", "arguments": {"city": "Cupertino"}}', Expectation(type="tool_call", params={"name": "get_weather", "required_args": ["city"]}))
    assert ok.passed
    bad = score_expectation('{"tool": "get_weather", "arguments": {}}', Expectation(type="tool_call", params={"name": "get_weather", "required_args": ["city"]}))
    assert not bad.passed


def test_retrieval_recall():
    from prompt_eval.scorers import score_expectation
    from prompt_eval.models import Expectation
    ok = score_expectation("Based on doc-1 and doc-2.", Expectation(type="retrieval", params={"expected_docs": ["doc-1", "doc-2"]}))
    assert ok.passed
    partial = score_expectation("Based on doc-1.", Expectation(type="retrieval", params={"expected_docs": ["doc-1", "doc-2"], "min_recall": 0.5}))
    assert partial.passed
    fail = score_expectation("Based on doc-1.", Expectation(type="retrieval", params={"expected_docs": ["doc-1", "doc-2"]}))
    assert not fail.passed
