# Reaction datafeed investigation

Date: 7 October 2026 (Europe/London).

## Scope and state

- Lane: bug-triage; investigation only, no product implementation requested.
- Owner lenses: Staff Engineer, DevOps/SRE, QA/Test Engineer; handled in one session.
- Skills: Compound V Engineering, Root-Cause Debugging, Risk-Based Testing, Fintech Secure Delivery.
- Selected orchestration skill: `/Users/vinay/.local/share/compound-v/skills/compound-v-engineering/SKILL.md`.
- Installed skill revision: `6ad81df875ea045f734fcdece62cdfa2c169f076`, matching published GitHub main at inspection. Local factory checkout is on a different revision; no skill refresh performed.
- Stage: investigation complete for available evidence; controlled runtime reproduction remains unverified.
- Local tracking artifact: this handoff. No GitHub issue or PR requested or created.
- Intended labels if later tracked: `compound-v`, `lane:bug-triage`, `stage:backlog`.
- Next gate: review investigation evidence and approve any product implementation separately. Fresh controlled UI actions are needed to establish transport behaviour.
- AI eval impact: none; this investigation concerns deterministic transport/parsing/dispatch. No test/eval harness found in the product repository.

## Question

When a user adds, replaces, or removes an emoji reaction in a conversation containing the bot, does an event reach the official Agent Datafeed API and then disappear during SDK parsing, filtering, or dispatch?

## Findings supported by local evidence

1. The running bot uses Python 3.14 and installed `symphony-bdk-python` 3.0.0. Its datafeed is V2, using the official v5 endpoints. The active bot process was left running.
2. `src/__main__.py:66` implements only `on_message_sent` for message logging. The connection listener handles connection requests/acceptances. Registered activities handle commands and form submissions; there is no reaction listener.
3. SDK `RealTimeEvent` in `abstract_datafeed_loop.py` has no reaction mapping and also no `GENERICSYSTEMEVENT` mapping. Generated `V4Payload` nevertheless models `genericSystemEvent`.
4. SDK dispatch logs `Received event with an unknown type: <type>` at INFO for an accepted event whose type is missing from the enum. Missing an enum entry does not silently erase the type.
5. `RealTimeEventListener.is_accepting_event` rejects bot-initiated events and events without `initiator.user.userId`, before dispatch. Those events need not produce an unknown-type log.
6. Generated model parsing preserves an unfamiliar `V4Event.type` but drops unfamiliar payload fields. Diagnosing using only `event.to_dict()` can therefore lose the evidence.
7. Initial `bdk.log` inspection found no reaction mentions or unknown-type records. The 7 October run started at 09:17:52; the V2 loop started at 09:17:53; a normal message was logged at 09:18:26. No raw successful-response logging or periodic read logging is configured, so absence of log entries does not prove absence on the wire. Previous events are acknowledged and cannot be reconstructed from these logs.

## Primary-source API findings

- [Python BDK PR #414](https://github.com/finos/symphony-bdk-python/pull/414) is a draft adding react/unreact/list operations against `/maestro/reactions/v1/message`. Its file changes do not add datafeed callbacks, enum entries, or event models. An internal client endpoint working with a bot session token does not establish a supported API or datafeed event.
- [Official API-spec issue #232](https://github.com/finos/symphony-api-spec/issues/232) requests published reaction endpoints and explicitly asks whether reactions are visible to datafeed. That question remains unanswered in the inspected issue.
- [Official real-time event catalogue](https://docs.developers.symphony.com/bots/datafeed/real-time-events) lists no reaction event. It documents `GENERICSYSTEMEVENT`, but no reaction subtype. Do not infer that reactions use generic events merely because that category exists.
- Fresh downloads of the published [Agent spec](https://raw.githubusercontent.com/finos/symphony-api-spec/master/agent/agent-api-public.yaml) (25.8.1) and [Pod spec](https://raw.githubusercontent.com/finos/symphony-api-spec/master/pod/pod-api-public.yaml) (20.17.1) contained zero case-insensitive `reaction` mentions and zero reaction paths.
- Agent spec SHA256: `952ae33c284da4e695c04192db1559b1c18ad23ad65ce2057bef538337c115ed`.
- Pod spec SHA256: `f105e5d18ae66f852e76e159f8c010c6ffcd8e029e050e8d3093340afbe843a3`.
- [Create Datafeed](https://rest-api.symphony.com/main/datafeed/create-datafeed-v5) supports separately tagged feeds. [Read Datafeed](https://rest-api.symphony.com/main/datafeed/read-datafeed-v5) requires an empty first ackId, followed by the ackId from the previous response. `includeInvisible` concerns invisible rooms, not enabling reaction delivery.

## Ranked hypotheses and distinguishing evidence

| Rank | Hypothesis | Evidence needed |
| --- | --- | --- |
| 1 | Reaction changes are not surfaced through this pod/Agent's public datafeed. | Healthy raw official datafeed receives a control message from the same conversation but no correlated events for confirmed add/change/remove actions. Even then, limit the finding to this tested environment and window. |
| 2 | Reactions arrive as an unhandled type, potentially a generic system event. | Raw response shows a correlated type/subtype; compare generated model and dispatch behaviour. No actual reaction type/subtype has yet been observed. |
| 3 | A new reaction payload is discarded by generated deserialization. | Compare raw payload keys with the corresponding model; unfamiliar fields disappearing confirms this boundary. Synthetic probe demonstrates that this loss is possible. |
| 4 | Event acceptance filters hide the event before dispatch/logging. | Raw correlated event has no initiator or is bot-initiated; acceptance probe rejects it. |
| 5 | The action is outside the bot's conversation scope, or the feed is unhealthy. | Confirm bot membership and successful normal-message control in the exact same conversation during the capture. |

## Offline isolation probes (passed)

Executed directly against installed SDK without network calls or importing `src.__main__`:

- Synthetic unfamiliar event type remains unchanged after `V4Event.from_dict`.
- Its unfamiliar `reactionProbe` payload disappears from `V4Payload.to_dict`.
- A synthetic other-user initiator passes listener acceptance and dispatch produces the unknown-type INFO log.
- Synthetic `GENERICSYSTEMEVENT` parameters survive parsing but dispatch produces the unknown-type INFO log.
- A synthetic event without initiator is rejected before dispatch.

The synthetic names are test inputs; they are not observed Symphony reaction event names. No business behaviour or SDK files were changed.

## Live capture method

Created one uniquely tagged temporary feed through the official API, without starting a second bot loop or reusing/acknowledging the running bot's feed. Read via `DatafeedApi.read_datafeed_without_preload_content` to inspect JSON before generated model deserialization. Initial ackId was empty; later reads used the returned ackId. Presence updates were disabled for probe reads.

Capture outputs only timestamps, types, payload field names, generic subtype/source, parameter names, and salted opaque correlation references. No message content, user identities, authentication tokens, or raw response bodies are retained in this artifact. Temporary feed deletion is performed in `finally` and its outcome must be recorded below.

Requested manual control: send a normal message in a conversation containing the bot, then add, replace, and remove a reaction on a bot message and confirm completion. An empty capture without confirmed controls is inconclusive.

## Official implementation route, conditional on evidence

- If no reaction event is delivered in a controlled test: ask Symphony to publish and support reaction delivery through Datafeed, with a documented payload, permissions, scope, ordering/replay behaviour, and add/change/remove semantics. Adding a local enum or callback cannot cause the server to emit an event.
- If raw delivery is confirmed: obtain Symphony's supported contract, update the API specification/generated models as necessary, then implement the SDK mapping/listener and application callback. A documented generic subtype would require generic dispatch support rather than inventing an undocumented reaction type.
- Sending and listing reactions also require published supported endpoints. PR #414 remains an internal-endpoint workaround until that contract exists.

## Proposed verification before any fix

Use a fixture derived from a sanitized observed event; prove payload preservation and callback dispatch. Exercise add, replace, remove, duplicate/replayed events, missing initiator, bot self-events, unknown generic subtype, and unaffected normal message/form handlers where supported by the actual contract. Verify in a bot-member direct chat and room, with same-conversation message controls and entitlement restrictions. Do not assert invented event names or semantics.

## Remaining limits

Raw capture cannot recover reaction events already acknowledged by the running bot before the new temporary feed existed. Published documentation cannot prove runtime behaviour on a particular pod. No user confirmation of the earlier reaction time/conversation or capture controls had arrived at initial drafting. Implementation remains outside the requested investigation scope.

## Live capture result

- Capture ready: 09:24:23 BST on 7 October 2026.
- Last response / summary: 09:27:36 BST (a final outstanding long poll completed after the nominal three-minute deadline).
- Ten successful HTTP 200 read responses; every batch had zero events.
- No normal-message control was received. No confirmation of add/change/remove UI actions during this window arrived. The running bot log also had no new message-receive entries beyond 09:18:26.
- Interpretation: API access and polling succeeded, but the capture is inconclusive about reaction delivery because the required live controls were not established. Do not report zero events as proof that Symphony never publishes reactions.
- Cleanup: the generated deletion method raised a `ValidationError` after its HTTP request. Inspection shows it maps HTTP 204 to `V2Error`, attempting to deserialize a no-content success as an error model. A subsequent official list-datafeeds call found zero feeds with the investigation tag prefix and one other feed remaining. Temporary feed absence is verified; no original feed was deleted or read by the probe.
- Product code, dependencies, config and existing local edits were left unchanged. The only repository addition is this investigation handoff.

## Next controlled experiment

Start a fresh isolated official feed, retaining its exact unique tag/ID locally for cleanup, and capture raw JSON before model parsing. Once READY is confirmed, perform a normal-message control followed by reaction add/change/remove on a bot message in the same bot-member conversation. Record UI action times and obtain a completion confirmation. Inspect all event types, generic subtypes and payload keys rather than filtering on an invented reaction name. Verify cleanup with the official feed list. Use the raw/no-preload deletion method or verify absence if generated parsing raises after HTTP 204.

Current conclusion: there is no evidence that the user's reactions reached the bot, and no published reaction event contract was found. SDK dispatch/parsing gaps are proven, but none has been linked to an observed reaction event. Official reaction support needs a Symphony-supported event/API contract; server transport and SDK handling must be verified separately.

