# Current enterprise AgentKit review

Scope: current framework and App implementations against `V1执行计划.md` global constraints, particularly authorization paths, frozen shared closures, runtime assembly, and confined file access. This is a targeted read-only review, not a claim of exhaustive coverage. Two P1 findings were identified; no P0 finding was established.

## P1: Merging approved member snapshots silently replaces another member's pinned resource version

- **Location:** `egis/egis-agentkit-framework/src/egis_agentkit/services/snapshots.py:63`–`65`, `:75`–`79`; `services/resources.py:134`–`167`, `:401`–`410`.
- **Trigger:** A static team contains two approved shared expert members whose frozen snapshots refer to different versions of the same system Skill or MCP using the same view. This can occur when the experts were approved at different times.
- **Evidence:** Shared child nodes are merged with `snapshot["nodes"].update(sub["nodes"])`. Asset node keys contain type, view, and ID, but not version. The later child overwrites the earlier child's asset node. This merge bypasses the explicit conflicting-version check in the normal `_visit` asset branch. I executed the current `_visit` function in isolation with a private leader and two shared expert subgraphs pinned respectively to `1.0.0` and `2.0.0`: the first member's edge resolved to `2.0.0` after capture. This reproduction uses stubbed storage/child captures and does not modify data.
- **Impact:** The resulting graph no longer represents the approved closure. When the first member loads its configured `1.0.0` resource, `_scope_allows` looks up the overwritten node with `2.0.0` and rejects it, so the member cannot execute as approved. A team may also be submitted and approved with the already-corrupted graph. Reject conflicting nodes at *every* merge or represent versions/closures separately, preserving each approved edge.

## P1: MCP execution trusts mutable registry content rather than the pinned configuration

- **Location:** `egis/egis-agentkit-framework/src/egis_agentkit/services/resources.py:286`–`292`, `:401`–`410`; `hubs/nacos.py:163`–`168`; `hubs/management.py:100`; compare Skill checksum enforcement at `services/resources.py:373`–`374`.
- **Trigger:** The endpoint of an MCP version in Nacos is changed after an Agent or Team using that version has been reviewed or a turn snapshot captured. The Nacos management adapter exposes an update operation for a specified MCP version.
- **Evidence:** Saving an MCP records a hash of its submitted endpoint configuration, and the execution snapshot contains that stored hash. At assembly, `mcps_for_refs` fetches the version from Nacos and renders its current card directly; neither that method nor `NacosMCPHub.get_mcp_version` compares the fetched endpoint to the saved hash. The hub checks only that the registry reports the requested version. `_scope_allows` compares the snapshot hash to the PG asset hash, not the returned registry content.
- **Impact:** A changed same-version endpoint is used under the existing approved USE path and immutable snapshot, including for previously approved shared execution. This can redirect tool calls and their data to a different endpoint without a new enterprise review. Persist and use the reviewed canonical endpoint configuration or verify a canonical representation of the fetched configuration against the pinned digest before connecting, including HITL resume.

No source files were edited for this review. The focused snapshot reproduction ran without PostgreSQL or production data; full integration tests were not rerun.
