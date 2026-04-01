---
name: analyze-teams-messages
description: Fetches and analyzes Microsoft Teams chat or channel messages for a given time period. Use when the user wants to analyze a Teams conversation, identify questions and answers, summarize discussions, or examine a specific time period of Teams messages.
---

# Analyze Teams Messages

## Required information — collect before starting

Ask the user for anything that is missing:

1. **Teams URL** — full link to the channel or chat (e.g. copied from "Link kopieren" in Teams)
2. **Date range** — `from` and `to` in format `DD.MM.YYYY` (inclusive)
3. **No of messages** — how many messages should be fetched. The agent calculates the number of fetch-loops (needed as parameter for the python script). Each loop delivers 5 messages.
4. **Context file** *(optional)* — a path to an additional input file (e.g. a meeting invite, agenda document, or notes file). If provided, its content is used to generate a "What's this meeting about" section at the top of the output.

---

## Step 1: Fetch messages

Run `request_messages.py` from the project root to trigger the Power Automate export and wait for the file to appear:

```bash
py src/request_messages.py --url "<teams_url>" --output "export" --loops <loops>
```

The script will:

- Call the webhook and trigger the export
- Poll the OneDrive folder every 5 seconds (max 3 minutes)
- Print the full path of the created file when ready

Note the output file path printed by the script — you will need it in the next step.

---

## Step 2: Filter messages by date range

Run the filter script with the file path from Step 1:

```bash
py .cursor/skills/analyze-teams-messages/scripts/filter_messages.py "<json_file>" <from_date> <to_date>
```

Read the JSON output. The messages are sorted chronologically (oldest first). Replies are nested under their parent message in a `replies` array.

If the filtered result contains 0 messages, the date range may not be covered by the fetched data — ask the user to increase `no of messages` and repeat from Step 1.

---

## Step 3: Analyze the filtered messages

Analyze the conversation with focus on these two categories:

### Questions & Answers

- Identify all questions — both explicit (containing `?`) and implicit (requests, clarifications, uncertain statements)
- For each question, find the answer:
  - First look in the `replies` array of the message
  - If no replies, look at the chronologically next messages for an answer
  - If no clear answer was given, mark it as **unanswered**

### Additional information shared

- Identify messages that provide information without being a direct answer to a question (e.g. status updates, shared links, announcements)

---

## Step 4: Write output file

Create a markdown file at `output/<from_date>_<descriptive-topic-slug>.md` (e.g. `output/2026-03-11_brm-chat-analyse.md`). The `output/` directory must exist — create it if needed.

**Language:** Write the entire output file in **English**, regardless of the language of the source messages. Translate questions and answers into English.

### Structure without context file

```markdown
# Chat Analysis: [from_date]

**Source:** Microsoft Teams Chat ([context, e.g. channel or meeting name if identifiable])
**Date:** [from_date]
**Exported:** [today's date]
**Context:** [1-sentence summary of the meeting/chat topic]

---

## Questions & Answers

**Q: [question text]**
A: [answer text]

---

**Q: [question text]**
A: *(unanswered)*

---

## Additional Information

- **[Topic]:** [detail]
- **[Topic]:** [detail]
```

### Structure with context file

If the user provided a context file, read it and prepend a "What's this meeting about" section **before** the Q&A sections. Derive its content from the context file:

- Write a short paragraph summarising the purpose of the meeting/chat based on the file content.
- If the file contains agenda items (numbered or bulleted lists, sections labelled "Agenda", "Tagesordnung", "Topics", etc.), list **all of them** verbatim or closely paraphrased as a bullet list under an **Agenda** sub-heading.

```markdown
# Chat Analysis: [from_date]

**Source:** Microsoft Teams Chat ([context, e.g. channel or meeting name if identifiable])
**Date:** [from_date]
**Exported:** [today's date]
**Context:** [1-sentence summary of the meeting/chat topic]

---

## What's this meeting about

[Short paragraph describing the purpose of the meeting, derived from the context file.]

### Agenda

- [Agenda item 1]
- [Agenda item 2]
- ...

---

## Questions & Answers

**Q: [question text]**
A: [answer text]

---

**Q: [question text]**
A: *(unanswered)*

---

## Additional Information

- **[Topic]:** [detail]
- **[Topic]:** [detail]
```

> Omit the **Agenda** sub-heading if no agenda items are found in the context file.

Formatting rules:
- Each `A:` starts on a **new line** directly below its `**Q:**`
- Separate each Q&A block with `---`
- Follow-up questions within the same thread are placed directly below their parent Q&A, without an additional `---` separator between them
- Unanswered questions are marked with `A: *(unanswered)*`
- Use `**bold**` for the Q line, plain text for the A line

After writing the file, confirm the path to the user.

---

## Notes

- The export is **anonymous** — no sender information is available. Do not speculate about who sent which message.
- `msg: null` means the message had no text content (e.g. a file or reaction) — skip these unless they have replies.
- Messages with an unresolved `replyTo` (parent outside the date range) appear at top level — treat them as standalone messages.
