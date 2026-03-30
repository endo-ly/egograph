use std::sync::OnceLock;

use tracing_subscriber::EnvFilter;

use crate::error::LoggingError;

static LOGGING_INITIALIZED: OnceLock<()> = OnceLock::new();

pub fn init_logging(level: &str) -> Result<(), LoggingError> {
    if LOGGING_INITIALIZED.get().is_some() {
        return Ok(());
    }

    let filter = EnvFilter::try_new(level)
        .or_else(|_| EnvFilter::try_new(level.to_ascii_lowercase()))
        .map_err(|error| LoggingError::InitFailed(error.to_string()))?;

    tracing_subscriber::fmt()
        .with_env_filter(filter)
        .with_target(false)
        .try_init()
        .map_err(|error| LoggingError::InitFailed(error.to_string()))?;

    let _ = LOGGING_INITIALIZED.set(());
    Ok(())
}
