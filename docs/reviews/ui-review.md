# UI correction review

## P2 — Switching conversations during attachment upload sends the draft to the wrong session

`egis/egis-agentkit-frontend/src/views/ConversationView.vue:46` captures the current session only for `attachments.upload`, then calls `conversation.send` after the await. If the user switches from A to B while an upload is pending and B finishes loading, the message is sent to B even though its referenced files were uploaded to A. The subsequent cleanup can also clear B's typed draft and attachment selection. Capture and validate the originating session across the whole operation, and retain the draft when it no longer owns the view.

## P2 — A stale session load can consume and send another session's queued draft

`egis/egis-agentkit-frontend/src/views/ConversationView.vue:26` awaits `conversation.open(value)` without checking whether the route is still `value` before consuming `takeDraft(value)`. `open` returns early when superseded, so when A's load completes after a switch to B, A's queued draft is removed and `conversation.send` either sends it to B if B is ready or silently drops it if B is still loading. Keep the queued draft until its own session is still current and ready to send.
