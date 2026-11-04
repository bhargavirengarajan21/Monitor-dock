"""Story 23 — cited answer with past fix and live status."""

from incident_memory_ai.answer import AnswerBuilder, MatchedIncident, LiveStatus
from incident_memory_ai.citations import Citation
from incident_memory_ai.config import load_config
from incident_memory_ai.meta_client import MetaModelClient


def _client(reply):
    def transport(url, headers, body):
        return {"choices": [{"message": {"content": reply}}]}

    return MetaModelClient(config=load_config({}), transport=transport)


MATCH = MatchedIncident(
    title="Payment 409 after idempotency change",
    cause="Deploy abc123 made the idempotency key non-unique.",
    fix="Reverted the key change in PR #42.",
    url="https://notion/incident-01",
    score=0.82,
)
LIVE = LiveStatus(error_code="ERR_PAYMENT_409", error_count=37, url="https://nr/err/1")


def test_answer_has_past_fix_live_status_and_citations():
    builder = AnswerBuilder(_client("Past cause ... [1] fix ... [1] now 37 errors [2]"))
    answer = builder.build("why is payment 409 firing?", [MATCH], LIVE)

    assert not answer.no_match
    kinds = [c.kind for c in answer.citations]
    assert "postmortem" in kinds
    assert "monitoring" in kinds
    # live error count is available via the monitoring citation label
    assert any("37" in c.label for c in answer.citations)


def test_answer_works_without_suspect_commits():
    builder = AnswerBuilder(_client("answer [1] [2]"))
    answer = builder.build("q", [MATCH], LIVE, suspect_commits=None)
    assert len(answer.citations) == 2  # postmortem + monitoring only


def test_answer_includes_suspect_commits_when_present():
    builder = AnswerBuilder(_client("answer [1] [2] [3]"))
    commits = [Citation(kind="commit", label="abc123 bad change", url="https://gh/commit/abc123")]
    answer = builder.build("q", [MATCH], LIVE, suspect_commits=commits)
    assert any(c.kind == "commit" for c in answer.citations)


def test_below_threshold_is_honest_no_match():
    builder = AnswerBuilder(_client("should not be used"), no_match_threshold=0.55)
    weak = MatchedIncident(title="x", cause="", fix="", url="u", score=0.2)
    answer = builder.build("q", [weak], LIVE)
    assert answer.no_match
    assert answer.text == "No similar incident found"
