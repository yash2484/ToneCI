# Voice → CRM Router — Weekend Build Spec

**Purpose:** A scope-locked side project that answers ElevenLabs' application question "Have you used ElevenLabs?" with something better than a voice chatbot. Built in a weekend, demoable in 30 seconds, and mapped to the Internal AI Transformation and Forward Deployed Engineer roles.

**Working name:** VoiceRouter (rename if something better lands)

---

## 1. THE ONE-LINER

Speak an update after a call. The system transcribes it, decides which action it implies, and writes the result to a live tracker.

Not a transcription tool. The decision step is the point.

---

## 2. WHY THIS PROJECT AND NOT ANOTHER

The ElevenLabs Internal AI Transformation JD asks for someone who can "co-design and ship agentic AI workflows that eliminate manual toil" and who will be "integrating AI systems with our core business stack — Salesforce, Slack, Ashby, and more."

This project is that sentence, built small. Voice in, agent decides, business system updated. It also closes the one real gap in the ElevenLabs application: no prior voice work.

What it deliberately avoids: another eval harness. AgentProof already carries that story. This one shows range.

---

## 3. SCOPE LOCK (read this before writing any code)

**Build exactly this. Nothing more.**

IN SCOPE:
- One voice input path (record or upload an audio file)
- ElevenLabs Speech-to-Text for transcription
- One LLM call that extracts structured fields AND picks an action
- Three routing branches, no more
- One write target (Airtable or Google Sheets)
- A minimal CLI or single-page UI showing what it decided and why
- A README with a demo GIF

OUT OF SCOPE (resist these):
- Real-time streaming audio
- Multi-turn conversation
- Salesforce or HubSpot OAuth (auth will eat the weekend)
- A vector store or RAG layer
- Authentication, multi-user, deployment to a cloud host
- More than three routing branches
- Any eval harness (that is AgentProof's job)

If a feature is not in the IN SCOPE list, it goes in a "Future work" section of the README instead of the codebase.

---

## 4. THE FLOW

```
Audio file
   |
   v
ElevenLabs STT  ->  raw transcript
   |
   v
LLM extraction + routing call
   |  returns: {action, fields, confidence, reasoning}
   v
Router (3 branches)
   |
   +-- CREATE   -> new row in tracker
   +-- UPDATE   -> find existing record, patch fields
   +-- FLAG     -> low confidence or ambiguous, write to a review queue
   |
   v
Confirmation (text, or ElevenLabs TTS read-back if time allows)
```

The FLAG branch matters more than it looks. An agent that knows when it is unsure is a better engineering story than one that always acts. Build it.

---

## 5. THE THREE BRANCHES

**CREATE** — the update describes a new contact, deal, or account not already in the tracker.
Example input: "Just got off a call with Acme Corp, new lead, they want the enterprise tier, decision maker is their CTO Priya."

**UPDATE** — the update refers to something already in the tracker.
Example input: "Acme moved to contract review, pushing the close date to end of month."

**FLAG** — the model is not confident which record is meant, or the transcript is too vague to act on.
Example input: "Good call today, they seemed interested, follow up soon."

Route on the model's own confidence score plus whether a matching record exists. Keep the matching simple: a case-insensitive company-name lookup is enough. Fuzzy matching is out of scope.

---

## 6. STACK

Pick boring tools. The project is the idea, not the infrastructure.

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.11+ | Your default |
| Audio in | Local file upload | Skips mic permissions and browser audio plumbing |
| Transcription | ElevenLabs Speech-to-Text API | The whole point of the project |
| Extraction + routing | Claude (Anthropic SDK), structured output | One call, JSON schema out |
| Write target | Airtable API | Simple token auth, visible result, no OAuth dance |
| Interface | CLI first. Streamlit only if you have spare hours | A CLI that prints the decision is enough to demo |
| Optional | ElevenLabs TTS for spoken confirmation | Nice-to-have, cut it without guilt |

**Fallback if Airtable fights you:** write to a local SQLite table and show it in the terminal. The routing decision is what matters, not the destination.

---

## 7. THE EXTRACTION SCHEMA

Ask the model for one JSON object. Keep the field list short.

```json
{
  "action": "CREATE | UPDATE | FLAG",
  "confidence": 0.0,
  "reasoning": "one sentence on why this action",
  "company": "string or null",
  "contact_name": "string or null",
  "contact_role": "string or null",
  "stage": "string or null",
  "next_step": "string or null",
  "due_date": "YYYY-MM-DD or null",
  "notes": "string"
}
```

Two rules for the prompt:
- The model must return null rather than guess. A hallucinated close date is worse than a missing one.
- The model must set action to FLAG when confidence drops below a threshold you pick and state in the README.

---

## 8. BUILD ORDER (two days, roughly)

**Saturday morning — get audio to text.**
Record three voice notes on your phone. One clean CREATE, one clean UPDATE, one deliberately vague. Wire ElevenLabs STT and print the transcripts. Stop when all three transcribe correctly.

**Saturday afternoon — get text to structure.**
Write the extraction prompt. Feed it the three transcripts. Iterate until the CREATE and UPDATE notes produce clean JSON and the vague one produces FLAG. This is where most of the thinking lives.

**Saturday evening — get structure to the tracker.**
Set up the Airtable base with the fields above. Wire CREATE. Confirm a row appears.

**Sunday morning — the other two branches.**
Wire UPDATE with company-name lookup. Wire FLAG to a separate review table or a flagged column.

**Sunday afternoon — make it demoable.**
Print the decision, the reasoning, and the record it touched. Record a 20-second GIF: play the voice note, show the terminal output, show the new row in Airtable.

**Sunday evening — README and stop.**
Write it up. Push it. Do not add features.

If you fall behind, cut in this order: TTS confirmation, then the UPDATE branch (ship CREATE and FLAG only, note UPDATE as future work), then the GIF. Never cut the README.

---

## 9. WHAT TO LOG WHILE BUILDING

ElevenLabs asks "how did you know it worked?" and their culture rewards "here's what broke." Keep a running note as you go. Capture:

- Anything the transcription got wrong, and whether it mattered downstream
- The first version of the extraction prompt that failed, and why
- A case where the model picked the wrong branch, and what you changed
- Whatever you got wrong about the Airtable API on the first try

One real failure with a specific fix beats a paragraph saying it went smoothly.

---

## 10. HOW YOU TEST IT

Not a full eval harness. Ten voice notes, hand-labelled with the action you expect, run through the pipeline, count how many route correctly. That is a table in the README, and it is a legitimate answer to "how did you know it worked."

Suggested spread:
- 4 clear CREATE
- 3 clear UPDATE
- 3 deliberately vague, expecting FLAG

Report the number that routed correctly. If it is 8 out of 10, say 8 out of 10 and say which two failed. Do not round up, do not tune the ten cases until they pass and then report ten.

---

## 11. README STRUCTURE

Keep it under 150 lines.

1. One-line description
2. The demo GIF, near the top
3. What it does — the flow diagram from section 4
4. Why the FLAG branch exists (this is your judgment paragraph)
5. Stack
6. How to run it
7. Routing accuracy on the 10-note test set, including the failures
8. Known limitations, stated plainly
9. Future work (everything you cut)

Section 7 and 8 are what separate this from a weekend toy. State the limits before a reviewer finds them.

---

## 12. KNOWN LIMITATIONS TO STATE UP FRONT

Write these into the README yourself:

- Ten test notes is a small sample, all recorded by one speaker, all in one accent
- Company matching is exact-string, so "Acme" and "Acme Corp" are different records
- No streaming; audio is uploaded as a file
- Single user, no auth, runs locally
- The confidence threshold for FLAG was chosen by hand, not calibrated

Stating these costs nothing and buys credibility. A reviewer who finds an unstated limit assumes you missed it. A reviewer who reads your list assumes you know your system.

---

## 13. HOW THIS ANSWERS THE APPLICATION QUESTIONS

**"Have you used ElevenLabs, even in a personal or side project? What did you build or explore?"**
The direct answer. Built a voice-driven CRM router on ElevenLabs STT. Describe the routing decision, not the transcription.

**"What's the most impactful thing you've built? What was your specific contribution?"**
Still AgentProof. This project does not compete with that answer.

**"How did you know it worked? What did success actually look like?"**
Two layers, and mention both. AgentProof for the deep version, the variance decomposition story. This project for the small honest version, 10 labelled notes and the routing accuracy including failures.

**"Why ElevenLabs, and why now?"**
This project is evidence, not the answer itself. Build it, then reference it in one clause.

---

## 14. THE CLAUDE CODE KICKOFF PROMPT

Paste this when you start:

```
I'm building a weekend project called VoiceRouter. Scope is locked and
I want you to hold me to it.

WHAT IT DOES
Take an audio file of someone speaking a post-call update. Transcribe it
with the ElevenLabs Speech-to-Text API. Send the transcript to Claude with
a structured-output schema that extracts CRM fields AND decides one of
three actions: CREATE a new record, UPDATE an existing one, or FLAG for
human review when confidence is low or the company is ambiguous. Route to
the chosen branch and write to Airtable. Print the decision, the model's
reasoning, and the record touched.

STACK
Python 3.11+, ElevenLabs STT, Anthropic SDK with structured outputs,
Airtable API, CLI only. No web framework, no streaming, no OAuth, no
vector store, no eval harness.

HARD SCOPE RULES
- Exactly three routing branches. Do not add a fourth.
- Company matching is exact-string, case-insensitive. No fuzzy matching.
- If I ask for a feature outside this description, remind me it's out of
  scope and offer to note it as future work instead.
- The extraction prompt must return null for missing fields rather than
  guessing, and must set action=FLAG below a stated confidence threshold.

BUILD ORDER
1. Audio file to transcript. Verify on three sample notes before moving on.
2. Transcript to structured JSON with action + confidence + reasoning.
3. CREATE branch writing to Airtable.
4. UPDATE branch with exact-string company lookup.
5. FLAG branch to a review table.
6. CLI output showing decision, reasoning, and record.

Start with step 1 only. Show me working transcription before writing any
routing code. Tell me if you think any part of this design is wrong before
you build it.
```

---

## 15. THE ONE THING THAT MAKES THIS GOOD

Anyone can transcribe audio. The FLAG branch is what a reviewer at a company building agent infrastructure will notice, because it means you thought about what happens when the agent is wrong. Build that branch first if you have to cut something, and write a paragraph in the README about why it exists.
