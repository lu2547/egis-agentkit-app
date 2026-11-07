# Review fixes and verification

- Snapshot asset keys include version. Previously approved snapshots with old asset keys are normalized when loaded or merged. Colliding nodes with the same identity but different content fail closed; different asset versions remain separate. Resource access from a team member starts at that member's `agent_node_key` when supplied.
- MCP publishing stores the canonical digest of the HTTP transport and endpoint; installation and execution validate the fetched Nacos card against the nonempty stored digest before returning a client. `egis_agentkit.services.resources.mcp_config_checksum` is the shared seed helper. Missing, stale, or old-format checksums fail closed and require a trusted migration or republishing; a previously corrupted snapshot cannot be reconstructed automatically.
- `ResourceService.download_skill` authorizes the requested version, bounds and validates the ZIP, checks its stored digest when present, and closes the upstream stream. HTTP route wiring is owned by the App workstream.

Regression evidence: the three initial tests for shared member collision, endpoint drift, and sibling-resource scope were run against the previous implementation and failed for the expected behaviors; each passed after the fix. The same-version differing-content merge and Skill download tests were also run first and failed before implementation. An additional disposable PostgreSQL schema test builds two actually approved experts with different Skill versions, approves their team, and verifies both frozen edges and recipient authorization.

Final targeted command (with `PYTHONPATH=egis/egis-agentkit-framework/src:egis/egis-agentkit-app/src:egis/egis-agentkit-framework/tests`):

```
demo/agentscope-demo/.venv/bin/python -m pytest -q egis/egis-agentkit-framework/tests/test_permission_paths.py egis/egis-agentkit-framework/tests/test_resources.py egis/egis-agentkit-framework/tests/test_domain.py egis/egis-agentkit-framework/tests/test_assembly.py egis/egis-agentkit-framework/tests/test_teams.py egis/egis-agentkit-framework/tests/test_app_http.py egis/egis-agentkit-framework/tests/test_nacos_hubs.py egis/egis-agentkit-framework/tests/test_workspace_mcp.py egis/egis-agentkit-framework/tests/test_tasks.py egis/egis-agentkit-framework/tests/test_asset_sharing.py
```

Result: **40 passed, 2 skipped**. The skipped tests require explicit live-service acceptance. The full suite and live Nacos/MCP acceptance were not rerun. An earlier attempted targeted command included a nonexistent `test_hubs.py`; pytest collected no tests, and the corrected run above uses `test_nacos_hubs.py`.
