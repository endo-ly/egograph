use std::path::PathBuf;

use thiserror::Error;

#[derive(Debug, Error)]
pub enum EgoPulseError {
    #[error(transparent)]
    Config(#[from] ConfigError),
    #[error(transparent)]
    Provider(#[from] ProviderError),
    #[error(transparent)]
    Logging(#[from] LoggingError),
    #[error("shutdown_requested: received Ctrl+C while waiting for provider response")]
    ShutdownRequested,
}

#[derive(Debug, Error)]
pub enum ConfigError {
    #[error("config_not_found: config file does not exist: {path}")]
    ConfigNotFound { path: PathBuf },
    #[error("config_read_failed: failed to read config file {path}: {source}")]
    ConfigReadFailed {
        path: PathBuf,
        #[source]
        source: std::io::Error,
    },
    #[error("config_parse_failed: failed to parse config file {path}: {source}")]
    ConfigParseFailed {
        path: PathBuf,
        #[source]
        source: toml::de::Error,
    },
    #[error("invalid_model: model must not be empty")]
    InvalidModel,
    #[error("invalid_base_url: base_url must not be empty")]
    MissingBaseUrl,
    #[error("invalid_base_url: {value}")]
    InvalidBaseUrl { value: String },
    #[error("missing_api_key: api_key is required for non-local base_url")]
    MissingApiKey,
}

#[derive(Debug, Error)]
pub enum ProviderError {
    #[error("provider_request_failed: {0}")]
    RequestFailed(#[from] reqwest::Error),
    #[error("provider_api_error: status={status} body={body}")]
    ApiError {
        status: reqwest::StatusCode,
        body: String,
    },
    #[error("provider_invalid_response: {0}")]
    InvalidResponse(String),
}

#[derive(Debug, Error)]
pub enum LoggingError {
    #[error("logging_init_failed: {0}")]
    InitFailed(String),
}
