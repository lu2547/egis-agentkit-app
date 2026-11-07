# UI backend review

- User workspace routes list and read only `work`, `artifacts`, and `uploads`, scoped to the authenticated user. Traversal and symlinks are rejected by the existing descriptor-based access. The upload route accepts an optional query or multipart `path` under `uploads`, defaults to `uploads`, and returns the user-root-relative file path. Existing task uploads also retain an original in `uploads`.
- Task deletion takes native session locks for the leader and all team members before the native storage cascade. A held lock returns 409; work, artifact and upload files survive. Cross-user session access remains forbidden.
- Unnamed tasks enable native automatic conversation naming; explicitly named tasks disable it. The task DTO exposes only `id`, `subject`, and `state` from persisted native task context as `plan`.
- Verification: `test_ui_backend.py`, `test_tasks.py`, `test_workspace.py`, and `test_app_http.py`: 10 passed against disposable PostgreSQL schemas. Native SQL storage emitted one existing deprecation warning during team cascade. New regressions were observed failing before implementation.
