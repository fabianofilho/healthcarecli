You are helping the user configure an HL7 v2 MLLP endpoint for `healthcarecli`.

Follow these steps exactly, in order. Do not skip steps or bundle questions together.

---

## Step 1 — Collect endpoint details

Use the AskUserQuestion tool to ask each question one at a time:

1. **Profile name** — "What do you want to call this HL7 endpoint? (e.g. lis-mllp, adt-listener, prod-hl7)"
2. **Host** — "What is the hostname or IP of the MLLP receiver?"
3. **Port** — "What port is the MLLP receiver on? (common default: 2575)"
4. **Message type** — "What type of HL7 messages will you send? (ADT / ORM / ORU / other)"
5. **HL7 version** — "What HL7 version? (2.5 / 2.6 / 2.7 / 2.8 — default: 2.5)"
   - If the user presses Enter or says "default", use `2.5`.

---

## Step 2 — Confirm

Show a summary and ask: "Ready to save this endpoint?"

```
Profile name  : <name>
Host          : <host>
Port          : <port>
Message type  : <msg_type>
HL7 version   : <version>
```

---

## Step 3 — Save the profile

Run:

```bash
healthcarecli hl7 profile add <name> \
  --host <host> \
  --port <port> \
  --version <version>
```

---

## Step 4 — Verify connectivity (optional)

Ask: "Do you have a sample HL7 message file to send as a connectivity test?"

- If yes: ask for the file path, then run:
  ```bash
  healthcarecli hl7 send --host <host> --port <port> <file>
  ```
- If no: skip verification and remind the user they can test later with:
  ```bash
  healthcarecli hl7 send --host <host> --port <port> message.hl7
  ```

---

## Done

Tell the user the profile is saved and show example commands:
```bash
healthcarecli hl7 send --profile <name> my_adt_message.hl7
```
