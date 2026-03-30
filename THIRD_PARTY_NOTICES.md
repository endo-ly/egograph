# Third Party Notices

## MicroClaw

- Project: https://github.com/microclaw/microclaw
- License: MIT
- Reference commit: `6c7aa19ff14917c84484fc5e9424aec847f10945` (2026-03-30, `ci: add automated skill review for SKILL.md pull requests (#311)`)

### Incorporated ideas and structure

- `Cargo.toml` workspace split between root and app crate
- CLI entrypoint separation from runtime bootstrap
- config/runtime/provider boundary naming inspired by `src/main.rs`, `src/runtime.rs`, `src/config.rs`, and `src/llm.rs`

