"""No statistic is computed ACROSS replicates, and this is what checks it.

THE RULE AND ITS SCOPE, BECAUSE THE SCOPE IS THE WHOLE DIFFICULTY
------------------------------------------------------------------
FORBIDDEN: aggregating across RUNS. A mean of the replicates, a standard
deviation over them, a ratio quoted as a value plus a spread. Those operations
destroy the disagreement replication was taken to find, which is the one thing
replication produces that a single run cannot.

PERMITTED, and wrong to delete: a distribution statistic WITHIN a single run.
The arithmetic mean of one run's own measured lookup latencies, beside that
run's p50, p95, p99 and max, is a property of one measured population. Removing
it so that a text search comes out empty would destroy a real measurement in
order to make a checker green.

WHY THIS IS A TEST RATHER THAN A ONE-OFF SCRIPT
-------------------------------------------------
A classifier that certifies a document clean and then disappears certifies
nothing about the NEXT version of that document. These documents are going to be
rewritten - the results document and the README both still describe a single run
- and the property has to survive that rewrite. So it lives in the suite, where
a later edit that introduces a cross-run mean fails rather than passes.

FIVE CLASSES, NOT TWO, AND EVERY COUNT PRINTS
-----------------------------------------------
    FORBIDDEN-CROSS-RUN  the thing the rule forbids. Must be zero.
    WITHIN-RUN-STAT      a distribution statistic over one run's own population.
    ENGLISH-VERB         "make the number mean something". Not a statistic.
    FROZEN               a quotation of superseded wording, kept as a record.
    PROHIBITION          a line that STATES the rule rather than breaking it.

A class that only printed when non-empty would leave a reader unable to tell an
empty class from a class that stopped being looked for, so all five print and
their sum is asserted against the raw hit count.

THREE THINGS HERE WERE ADDED BECAUSE A CONTROL CAUGHT THEM, NOT BECAUSE THEY
WERE FORESEEN. Each is worth a sentence, because each is a way a scan like this
reports a confident zero over a document that violates the rule:

  1. THE BARE TABLE CELL. The obvious needle requires a determiner, an operator
     or a following noun. `| p50 | p95 | mean | max |` has none of them, so the
     literal `mean` COLUMN HEADER of a latency table is invisible to it.
  2. THE INFLECTIONS. `\\baverage\\b` does not match "averaged", so "the three
     replicates averaged 5,995 rps" would never enter the population at all and
     no class could be assigned to it.
  3. THE PROHIBITION CLASS. Without it, this very module's own description of
     the rule is reported as a violation of it. It is told from a real aggregate
     by a test that cannot launder one: a prohibition NEGATES the operation and
     carries NO NUMERAL, because a reported average has to carry the number it
     reports. "No fewer than 3 replicates; the mean across them was 41 ms" is
     negated AND numeric, and is a control below.
"""
from __future__ import annotations

import io
import os
import re

import pytest

ARTIFACT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCUMENTS = ("RUN-RECORD.md", "results/RESULTS.md", "README.md")

BROAD = re.compile(r"(?i)\b(mean|means|average|averages|averaged|averaging"
                   r"|std ?dev|standard deviation)\b")

STATISTIC = re.compile(
    r"(?i)("
    r"\b(?:the|a|an|arithmetic|geometric|weighted|sample|running|moving|overall)"
    r"\s+(?:mean|means|average|averages)\b"
    r"|\b(?:mean|average)\s*[=:]"
    r"|\b(?:mean|means|average|averages)"
    r"\s+(?:of|over|across|value|rps|latency|ms|p99|p95|p50)\b"
    r"|\bon\s+average\b"
    r"|\b(?:averaged|averaging)\b"
    r"|\bstd\s?dev\b|\bstandard\s+deviation\b|\b(?:mean|average)\s*\+/-"
    r"|\|\s*\**\s*(?:mean|average)\s*\**\s*\|"
    r")")

CROSS_RUN = re.compile(
    r"(?i)("
    r"\breplicates?\b|\bacross\s+runs?\b|\bover\s+the\s+(?:three|3)\b"
    r"|\bof\s+the\s+(?:three|3)\s+runs?\b|\bcampaign\b|\bper[- ]arm\s+mean\b"
    r"|\bstd\s?dev\b|\bstandard\s+deviation\b|\+/-"
    r")")

FROZEN_MARK = re.compile(r"(?i)\b(FROZEN|SUPERSEDED|quoted verbatim from the "
                         r"(?:July|first) run)\b")

NEGATION = re.compile(r"(?i)\b(no|not|never|nothing|none|without|forbidden|"
                      r"refuses?|must not|cannot|neither|nor)\b")
NUMERAL = re.compile(r"[0-9]")

FORBIDDEN = "FORBIDDEN-CROSS-RUN"
WITHIN_RUN = "WITHIN-RUN-STAT"
VERB = "ENGLISH-VERB"
FROZEN = "FROZEN"
PROHIBITION = "PROHIBITION"
CLASSES = (FORBIDDEN, WITHIN_RUN, VERB, FROZEN, PROHIBITION)


def classify(line):
    if not STATISTIC.search(line):
        return VERB
    if FROZEN_MARK.search(line):
        return FROZEN
    if NEGATION.search(line) and not NUMERAL.search(line):
        return PROHIBITION
    if CROSS_RUN.search(line):
        return FORBIDDEN
    return WITHIN_RUN


# The needle's own controls. A probe's zero is only a measurement when the probe
# carries live controls that MUST match and live controls that must NOT.
IS_A_STATISTIC = (
    "the mean of the three replicates was 5,995 rps",
    "capacity averaged over the run: average = 5995.1",
    "uncached p99 mean +/- stddev: 58.1 +/- 3.2 ms",
    "reported as a standard deviation across replicates",
    "on average the cached arm served 1.9x the uncached arm",
    "mean: 41",
    "a weighted average of both arms",
    "average of the nine boundary runs",
    "the three replicates averaged 5,995 rps",
    "capacity, averaging across the campaign, was 5,995 rps",
    "| | p50 | **p95** | p99 | mean | max |",
    "| **before** | 63.63 ms | **81.63 ms** | 63.06 ms | average |",
    "| p50 | p95 | average | max |",
)

IS_NOT_A_STATISTIC = (
    "## The guards that make the number mean something",
    "a verdict with no count beside it cannot mean anything",
    "that would mean the cache was pre-seeded",
    "one number cannot mean two things",
    "### The check that makes the latency number mean something",
    "## The guard that makes the number mean something",
    "a verdict with no count beside it means nothing",
    "a strict mapping means the index refuses an unknown field",
)

CLASS_CONTROLS = (
    (PROHIBITION,
     "**What is NOT done with the three.** No mean across replicates."),
    (PROHIBITION, "Nothing is averaged across the replicates, ever."),
    (PROHIBITION,
     "never a mean with a spread over runs; no standard deviation either"),
    (FORBIDDEN, "No fewer than 3 replicates; the mean across them was 41 ms"),
    (FORBIDDEN, "the mean of the three replicates was 5,995 rps"),
    (FORBIDDEN, "uncached p99 mean +/- stddev: 58.1 +/- 3.2 ms"),
    (WITHIN_RUN, "| | p50 | **p95** | p99 | mean | max |"),
    (WITHIN_RUN, "mean: 41"),
    (VERB, "## The guard that makes the number mean something"),
)


@pytest.fixture(scope="module")
def hits():
    """Every line in the three documents that the BROAD needle matches, classified."""
    found = []
    present = 0
    for relative in DOCUMENTS:
        path = os.path.join(ARTIFACT_ROOT, relative)
        assert os.path.isfile(path), (
            "%s is absent, so this scan would report a clean zero over a "
            "document it never opened" % relative)
        present += 1
        text = io.open(path, encoding="utf-8").read()
        for index, line in enumerate(text.splitlines(), start=1):
            if BROAD.search(line):
                found.append((relative, index, classify(line), line.strip()))
    assert present == len(DOCUMENTS)
    return found


def test_the_needle_matches_every_line_that_is_a_statistic():
    missed = [s for s in IS_A_STATISTIC if not STATISTIC.search(s)]
    assert missed == [], "the needle does not match: %s" % missed


def test_the_needle_matches_no_line_that_is_only_english():
    caught = [s for s in IS_NOT_A_STATISTIC if STATISTIC.search(s)]
    assert caught == [], "the needle wrongly matches: %s" % caught


def test_every_class_control_lands_in_the_class_it_should():
    wrong = [(expected, classify(line), line)
             for expected, line in CLASS_CONTROLS
             if classify(line) != expected]
    assert wrong == [], "misclassified: %s" % wrong


def test_the_documents_carry_no_cross_run_aggregate(hits, capsys):
    counts = dict((name, 0) for name in CLASSES)
    for _relative, _index, verdict, _line in hits:
        counts[verdict] += 1
    with capsys.disabled():
        print("\n[no-cross-run] documents=%d raw hits=%d"
              % (len(DOCUMENTS), len(hits)))
        for name in CLASSES:
            print("[no-cross-run]   %-20s %d" % (name, counts[name]))
    offenders = [(r, i, line) for r, i, verdict, line in hits
                 if verdict == FORBIDDEN]
    assert offenders == [], offenders
    assert sum(counts.values()) == len(hits)


def test_the_scan_examined_a_non_zero_population(hits):
    """A scan over zero lines cannot fail, so it must not be allowed to pass."""
    assert len(hits) > 0, (
        "the needle matched nothing at all across %d document(s). That is not "
        "a clean result, it is an unrun check: these documents describe "
        "latency distributions and are expected to contain the word."
        % len(DOCUMENTS))
