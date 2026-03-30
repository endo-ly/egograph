# EgoPulse

EgoPulse は EgoGraph 向けの Rust runtime foundation です。  
この MVP では、OpenAI-compatible endpoint に対して単発の `ask` を実行する最小土台だけを提供します。

## Prerequisites

- Rust stable
- `cargo fmt`
- `cargo clippy`

## Config

`.env` は使いません。環境変数または TOML 設定ファイルを使います。

### Environment variables

```bash
export EGOPULSE_MODEL="gpt-5-mini"
export EGOPULSE_API_KEY="sk-..."
export EGOPULSE_BASE_URL="https://api.openai.com/v1"
export EGOPULSE_LOG_LEVEL="info"
```

ローカルの OpenAI-compatible server を使う場合は、`localhost` / `127.0.0.1` / `::1` の base URL に限り `EGOPULSE_API_KEY` を省略できます。

### Config file

サンプルは [`egopulse.example.toml`](./egopulse.example.toml) を参照してください。

```bash
cargo run -p egopulse -- --config egopulse/egopulse.example.toml ask "hello"
```

## Usage

```bash
cargo run -p egopulse -- ask "hello"
```

期待する出力:

```text
assistant: ...
```

## Local checks

```bash
cargo fmt --check
cargo check
cargo clippy --all-targets --all-features -- -D warnings
cargo test
```

