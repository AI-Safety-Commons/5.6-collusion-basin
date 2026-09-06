# Context review — 6 September 2026

## Luka thread

Read all 39 messages in [personal-threads / Luka](https://glove.she-llac.com/republisher/messages?channel=1545936578013175848), through 6 September 2026 01:47 UTC. The mirror returned `Continue reading: null` and reported complete history at retrieval.

The initial proposal is to generate wiki-like messages using a base model, preserve observed records, and add hypothetical text between observations. Replies suggest Llama 3.1 405B and an Arcee Trinity base checkpoint, and point to ACS for access. Messages 24 and 28 explicitly agree that message generation is a separate contribution from arranging messages in an environment. Message 23 says ACS access was requested. The user has since reaffirmed that this repository's implemented component should only produce messages.

The thread's suggestions about a later editor model, HPIM's identity, fooling another model, and reproducing a behavioral “basin” are proposals or hypotheses, not established facts. This implementation does not implement editor-model calls, target-model experiments, or optimize for a target model's participation. It supplies inspectable synthetic messages and records their origin.

## DseWiki evidence

A [community archive announcement](https://glove.she-llac.com/republisher/messages/1545695402148237372/context) led to [WikiAgentSwarmInvestigation](https://github.com/JoshuaDavid/WikiAgentSwarmInvestigation). We pinned commit `774ea465e2957a5e3581a47a8cdb0f8e2395bea2` rather than following its moving main branch.

Two exports must be distinguished:

- [`agent-logs/dse/manifest.json`](https://github.com/JoshuaDavid/WikiAgentSwarmInvestigation/blob/774ea465e2957a5e3581a47a8cdb0f8e2395bea2/agent-logs/dse/manifest.json) describes 22,385 recent-change records with **zero body bytes**. It is useful metadata, not 22,385 preserved messages. Its minute-resolution timestamps have a stated 60-second uncertainty and use the scraper's year-round +01:00 assumption.
- [`agent-logs/prowiki/`](https://github.com/JoshuaDavid/WikiAgentSwarmInvestigation/tree/774ea465e2957a5e3581a47a8cdb0f8e2395bea2/agent-logs/prowiki) includes 14,591 stored revisions across four wikis, including DSE source bodies. This is the selected input. The revisions file matches its published SHA256SUMS. Body verification also found 250 rows labeled `utf8` whose JSON strings carry the original bytes as Latin-1 codepoints; all match their published hashes via Latin-1 encoding. The importer records these encoding discrepancies without changing the strings. A revision is a page snapshot, potentially containing several messages. These exports overlap; their counts must not be added.

The default example uses `AgentChatGPTConstructionAug11X` revisions 2 and 3, dated 17 June 2026, and an earlier `AgentAug27OAI` example. Observed features include CamelCase page references, signed notes, questions about task timing, state sequences, short reporting requests, and replies embedded in cumulative page text. Displayed editor labels sometimes differ from signatures in the body. Labels are not verified model identities.

Source clocks and uncertainty fields remain intact in the local import. Dates in handles and claimed task clocks are not substituted for archive timestamps. The configured gap is an **experimental interval**, not a finding that records were lost. Generated times are assigned within it, not recovered.

Read-only checks of [RecentChanges](https://www.wikiservice.at/dse/wiki2.cgi?action=rc&all=1&days=180), [ForumSeite](https://www.wikiservice.at/dse/wiki2.cgi?ForumSeite), and [AgentZzzHighMapJun21](https://www.wikiservice.at/dse/wiki2.cgi?AgentZzzHighMapJun21) show why live scraping is a poor default: later researcher conversations, moderator activity, and a one-word restored page are present. The sampled `AgentLinksBridge` diff returned a new-page stub, not a recovered body. No live wiki was edited.

The body archive is community-collected evidence; its provenance and classifications are not independently authenticated here. The [METR/Redwood report](https://www.redwoodresearch.org/research/hugging-face-incident) principally discusses the later Artifactory message board and July HF attack. It does not establish that every June DSE author belongs to that incident or to either named model. DSE and the Artifactory board must remain distinct surfaces.

## ACS integration

Checked [ACS's tutorial](https://infra.acsresearch.org/tutorial) and [API documentation](https://infra.acsresearch.org/llms.txt). ACS serves raw `/v1/completions`, without a chat template. Its documented short IDs include `llama-8b`, `llama-405b`, and `trinity-truebase`; `/v1/models` is the live authority. Trinity's documented checkpoint is **Trinity-Large-TrueBase**, distinct from the thread's earlier Large-Base link.

The client uses a 960-second read timeout for cold starts, marks calls as batch work, and recognizes error payloads even under HTTP 200. It does not automatically retry ambiguous calls. No paid or authenticated model request was made during setup. Model quality, context-window fit, and access remain unverified until a real key is available.

## Follow-up: message-only continuation (version 2)

After inspecting the user's first 8B run, the prompt was changed to three individual posts extracted from revisions 1–3 of `AgentChatGPTConstructionAug11X`, in order. The earlier interval/retrospective setup above describes version 1. Version 2 has no gap constraint, unrelated example, instructional preamble or supplied author. Each actual post ends with the API stop delimiter. Provenance remains in saved metadata. The first real run confirmed API connectivity; the new prompt and larger-model access still await the user's next tests.
