# Parent Space — Phase 6 (§6.1, §4, §5, §8)
# Authenticated dashboard. Replaces static unauthenticated HTML stub.

PARENT_DASHBOARD_SPEC = {
    "authentication": True,
    "replaces_static_unauthenticated_stub": True,
    "child_facing_invisible": True,
    "no_in_app_watching_indicator": True,
    "sections": ["reports", "config_controls", "approval_queue"],
}
