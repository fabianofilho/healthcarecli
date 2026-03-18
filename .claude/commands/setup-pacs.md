You are helping the user register a new DICOM PACS connection profile for `healthcarecli`.

Follow these steps exactly, in order. Do not skip steps or bundle questions together.

---

## Step 1 — Collect connection details

Use the AskUserQuestion tool to ask each question one at a time:

1. **Profile name** — "What do you want to call this PACS profile? (e.g. orthanc, dcm4chee, production-pacs)"
2. **Host** — "What is the hostname or IP address of the PACS?"
3. **Port** — "What port is the PACS listening on? (common values: 4242 for Orthanc, 11112 for dcm4chee, 104 for standard DICOM)"
4. **Remote AE title** — "What is the AE title of the remote PACS? (check your PACS admin console — e.g. ORTHANC, DCM4CHEE, CONQUESTSRV1)"
5. **Calling AE title** — "What AE title should this client use when connecting? (press Enter to keep the default: HEALTHCARECLI)"
   - If the user presses Enter or says "default" or "keep", use `HEALTHCARECLI`.

---

## Step 2 — Confirm

Show a summary table and ask: "Ready to save this profile?"

```
Profile name : <name>
Host         : <host>
Port         : <port>
Remote AE    : <ae_title>
Calling AE   : <calling_ae>
```

If the user says no or wants to change something, go back to Step 1 for that field.

---

## Step 3 — Save the profile

Run this command (substitute real values):

```bash
healthcarecli dicom profile add <name> \
  --host <host> \
  --port <port> \
  --ae-title <ae_title> \
  --calling-ae <calling_ae>
```

---

## Step 4 — Verify connectivity

Run a C-ECHO ping to confirm the PACS is reachable:

```bash
healthcarecli dicom ping --profile <name> --output json
```

- If it succeeds: tell the user the RTT and confirm the profile is ready.
- If it fails: show the error, suggest common causes (wrong AE title, firewall, PACS not running), and ask if they want to edit the profile or skip verification.

---

## Step 5 — Offer autotune (optional)

Ask: "Would you like to auto-tune the connection parameters for this PACS? This runs ~20 benchmarks to find the fastest PDU size, timeouts, and parallelism settings for your specific PACS. It takes about 2–5 minutes."

- If yes: run `healthcarecli dicom autotune sweep --profile <name> --n 20 --strategy random` and then `healthcarecli dicom autotune apply --profile <name> --from-best`
- If no: skip.

---

## Done

Tell the user:
- The profile name they can use in future commands (e.g. `--profile <name>`)
- Example commands to try:
  ```bash
  healthcarecli dicom query --profile <name> --level STUDY
  healthcarecli dicom ping --profile <name>
  ```
