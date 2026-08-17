# TTS Snapshot CI Domain Glossary

## Core Terms

### Test Case

A versioned specification of speech behavior that the project protects. A test case states what should be rendered, what a listener should hear, which wording must survive, and how much measurable change requests review.

### Approved Baseline

The human-accepted reference audio and evidence for one test case.

### Candidate

Newly rendered audio under comparison with an approved baseline.

### Run

One immutable comparison attempt containing its candidates, evidence, and results.

### Review Threshold

A configured measurement boundary that requests human inspection. Crossing a review threshold does not prove that the candidate is defective.

### Approval

The explicit human decision to replace an approved baseline with a named candidate from a completed run.

### Transcript Fidelity

The degree to which a speech-to-text observation matches the expected spoken text. It is evidence for review, not ground truth about what the audio contains.

### Required Phrase

Wording that must remain observable in a rendered test case, such as a product name, number, URL, or safety instruction.

### Duration Drift

The difference between baseline and candidate playback duration.

### Silence Drift

The difference between baseline and candidate leading or trailing silence. The leading and trailing edges are independent measurements.

## Result States

### PASS

A valid comparison completed without crossing a review threshold.

### REVIEW_REQUIRED

A valid comparison completed and at least one review threshold crossed. A person must inspect the evidence before accepting or rejecting the candidate.

### ERROR

The system could not complete a valid comparison.

These are the only result states. The project does not use `FAIL`, `WARN`, or a numeric quality grade.

## Term Boundaries

- A **review threshold** requests inspection; it is not a quality verdict.
- **Transcript fidelity** measures an STT observation; it does not isolate TTS errors from STT errors.
- An **approved baseline** records accepted behavior; it does not claim ideal or universal speech quality.
- A **candidate** becomes an approved baseline only through explicit **approval**.
