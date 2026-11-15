"""Persistence in PostgreSQL (spec §2). The broker stays the source of truth for positions,
orders and cash (§8); this store keeps Jarvis's own state and history."""
