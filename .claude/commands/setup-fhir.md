You are helping the user register a new FHIR server connection profile for `healthcarecli`.

Follow these steps exactly, in order. Do not skip steps or bundle questions together.

---

## Step 1 — Collect connection details

Use the AskUserQuestion tool to ask each question one at a time:

1. **Profile name** — "What do you want to call this FHIR server profile? (e.g. hapi, epic-sandbox, production-fhir)"
2. **Base URL** — "What is the FHIR server base URL? (e.g. https://hapi.fhir.org/baseR4 — must end with the FHIR version path like /baseR4 or /fhir/r4)"
3. **Authentication** — "Does this server require authentication? (none / basic / bearer-token / smart)"
   - If **none**: skip to Step 2.
   - If **basic**: ask for username and password.
   - If **bearer-token**: ask "What is the bearer token (or environment variable name that holds it, e.g. $MY_FHIR_TOKEN)?"
   - If **smart**: tell the user "SMART on FHIR OAuth2 requires a client ID and secret. Ask for: client_id, client_secret, token_url."

---

## Step 2 — Confirm

Show a summary and ask: "Ready to save this profile?"

```
Profile name : <name>
Base URL     : <url>
Auth         : <auth_type>
```

If the user says no or wants to change something, go back to Step 1 for that field.

---

## Step 3 — Save the profile

Run:

```bash
healthcarecli fhir profile add <name> --url <url>
```

For basic auth, append `--username <u> --password <p>`.
For bearer token, append `--token <token>`.

---

## Step 4 — Verify connectivity

Run a capability statement check:

```bash
healthcarecli fhir search CapabilityStatement --profile <name> --output json
```

- If it returns results: confirm the server is reachable and show the FHIR version.
- If it fails: show the error and suggest common causes (wrong URL, missing auth, CORS, firewall).

---

## Done

Tell the user:
- Example commands to try:
  ```bash
  healthcarecli fhir search Patient --profile <name> --param "family=Smith"
  healthcarecli fhir search Observation --profile <name> --param "subject=Patient/123"
  ```
