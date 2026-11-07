# Final targeted review

**Disposition:** Both findings below have been fixed in the current code. Scoped re-review found no remaining issue in these changes. The implementation team reports 40 targeted tests passed and one live test skipped; this re-review did not independently rerun them.

## Fixed P2: Native hub reads expose a registry version that has not been authorized

- **Location:** `egis-agentkit-app/src/egis_agentkit_app/security.py:79`; `egis-agentkit-framework/src/egis_agentkit/services/resources.py:208`; `egis-agentkit-framework/src/egis_agentkit/hubs/nacos.py:72` and `:160`.
- **Trigger:** A user has USE access to an enabled system Skill or MCP version registered in PostgreSQL, while Nacos contains a newer version of the same source name that is unregistered or disabled in PostgreSQL. The user calls the native GET `/hub/skill/nacos-skills/cards/{name}` or `/hub/mcp/nacos-mcps/cards/{name}`.
- **Evidence and impact:** The identity guard allows native hub GETs. `authorize_hub` accepts the name if *any* enabled matching asset is usable; it has no version parameter. The native card routes call `get_skill` or `get_mcp`, both of which query Nacos without a version and return the latest registry content. Therefore the response can disclose the newer Skill markdown or MCP endpoint even though that exact version has not passed the managed resource check. Lists likewise expose latest metadata. This is a read exposure; native installation writes remain blocked by the guard.
- **Remedy:** Restrict native hub GETs and serve the managed version-aware APIs, or authorize and validate the exact version returned before exposing its content or metadata.

The previously reported snapshot merge and MCP execution digest checks are present in the current implementation. This was a targeted code review; a full test suite was not rerun.

## Fixed P1: A shared asset grant permits binding and executing another owner's unapproved version

- **Location:** `egis-agentkit-framework/src/egis_agentkit/services/agents.py:77`; `services/snapshots.py:103`; `services/permissions.py:112`; `services/resources.py:162` and `:178`.
- **Trigger:** Bob has shared Skill or MCP version 1, and keeps an enabled version 2 private. Alice creates a private Agent that references Bob's resource ID with `resource_view_type=shared` and `resource_version=2`. Alice has the automatically granted shared USE on the resource ID.
- **Evidence:** `_validate_bindings` checks that version 2 exists, then asks `PermissionService.explain` about the resource ID and shared view without passing the version. A current approved review of version 1 satisfies that authorization. Snapshot capture reads the version 2 row directly from `assets`, and `validate_snapshot` checks shared permission by ID and verifies only that version 2 is enabled. During execution `_scope_allows` matches the snapshot's version 2 and `_usable` returns before `_review_asset` performs its exact approved-version check.
- **Impact:** Alice can execute an unapproved private Skill or connect to an unapproved private MCP endpoint, contrary to the sharing boundary. This route can also put the unapproved version into a parent sharing review.
- **Remedy:** Validate each newly constructed direct shared asset edge against the exact approved asset version and pinned content, rather than using resource-ID authorization alone. Existing approved parent closures need to retain their own previously reviewed frozen edges if a dependency's current standalone share changes.

The native `/hub/` routes are now denied in `IdentityGuard`; the earlier native hub read finding above is fixed by the current code. This follow-up conclusion is based on tracing the implementation; no integration test was run for the new P1.

**Shared-edge fix verification:** New Agent bindings and fresh snapshot edges now compare the entire asset to the current approved asset snapshot, including version and owner. Previously approved parent closures are loaded from their frozen review without re-resolving those edges. Regression cases cover both resource types, unapproved versions, changed owner and digest, and parent closure preservation.

**Preflight failure follow-up:** Fixed on scoped re-review. Deferred domain failures are raised at workspace resolution, after native Team identity resolution and before tools or model assembly; the native handler can therefore report the worker failure to its leader. Expected package loading `ValueError` and `OSError` are translated to a safe domain conflict. The implementation team reports focused Team notification and package failure regressions passed; these tests were not independently rerun in this re-review.

**Skill cache concurrent materialization:** Fixed on scoped re-review. Competing destination errors (`EEXIST` and `ENOTEMPTY`) are handled, and the winning directory is validated for type, symlinks, special files, and full content digest before use. Regression coverage exercises simultaneous independent service instances and rejects invalid or symlinked winners. The implementation team reports the targeted tests passed; this re-review did not rerun them.
