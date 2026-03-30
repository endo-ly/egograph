use std::env;
use std::fmt;
use std::fs;
use std::path::PathBuf;

use secrecy::{ExposeSecret, SecretString};
use serde::Deserialize;
use url::Url;

use crate::error::ConfigError;

#[derive(Debug, Default, Clone)]
pub struct ConfigOverrides {
    pub config_path: Option<PathBuf>,
    pub model: Option<String>,
    pub api_key: Option<String>,
    pub base_url: Option<String>,
    pub log_level: Option<String>,
}

#[derive(Debug, Default, Deserialize)]
struct FileConfig {
    model: Option<String>,
    api_key: Option<String>,
    base_url: Option<String>,
    log_level: Option<String>,
}

#[derive(Clone)]
pub struct AppConfig {
    model: String,
    api_key: Option<SecretString>,
    base_url: Url,
    log_level: String,
}

impl fmt::Debug for AppConfig {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.debug_struct("AppConfig")
            .field("model", &self.model)
            .field(
                "api_key",
                &self
                    .api_key
                    .as_ref()
                    .map(|_| "<redacted>")
                    .unwrap_or("<none>"),
            )
            .field("base_url", &self.base_url)
            .field("log_level", &self.log_level)
            .finish()
    }
}

impl AppConfig {
    pub fn load(overrides: ConfigOverrides) -> Result<Self, ConfigError> {
        let file_config = read_file_config(overrides.config_path.as_ref())?;

        let model = first_non_empty([
            overrides.model,
            env_var("EGOPULSE_MODEL"),
            file_config.model,
        ])
        .ok_or(ConfigError::InvalidModel)?;

        let base_url_raw = first_non_empty([
            overrides.base_url,
            env_var("EGOPULSE_BASE_URL"),
            file_config.base_url,
        ])
        .ok_or(ConfigError::MissingBaseUrl)?;

        let base_url = Url::parse(&base_url_raw).map_err(|_| ConfigError::InvalidBaseUrl {
            value: base_url_raw.clone(),
        })?;

        let api_key = first_non_empty([
            overrides.api_key,
            env_var("EGOPULSE_API_KEY"),
            file_config.api_key,
        ])
        .map(|value| SecretString::new(value.into_boxed_str()));

        if !is_local_url(&base_url) && api_key.is_none() {
            return Err(ConfigError::MissingApiKey);
        }

        let log_level = first_non_empty([
            overrides.log_level,
            env_var("EGOPULSE_LOG_LEVEL"),
            file_config.log_level,
        ])
        .unwrap_or_else(|| "info".to_string());

        Ok(Self {
            model,
            api_key,
            base_url,
            log_level,
        })
    }

    pub fn model(&self) -> &str {
        &self.model
    }

    pub fn base_url(&self) -> &Url {
        &self.base_url
    }

    pub fn log_level(&self) -> &str {
        &self.log_level
    }

    pub fn authorization_token(&self) -> &str {
        self.api_key
            .as_ref()
            .map(ExposeSecret::expose_secret)
            .unwrap_or("local-dev")
    }

    pub fn is_local_base_url(&self) -> bool {
        is_local_url(&self.base_url)
    }
}

fn read_file_config(path: Option<&PathBuf>) -> Result<FileConfig, ConfigError> {
    let Some(path) = path else {
        return Ok(FileConfig::default());
    };

    if !path.exists() {
        return Err(ConfigError::ConfigNotFound { path: path.clone() });
    }

    let contents = fs::read_to_string(path).map_err(|source| ConfigError::ConfigReadFailed {
        path: path.clone(),
        source,
    })?;

    toml::from_str(&contents).map_err(|source| ConfigError::ConfigParseFailed {
        path: path.clone(),
        source,
    })
}

fn env_var(key: &str) -> Option<String> {
    env::var(key)
        .ok()
        .and_then(|value| normalize_string(Some(value)))
}

fn first_non_empty<const N: usize>(values: [Option<String>; N]) -> Option<String> {
    values.into_iter().find_map(normalize_string)
}

fn normalize_string(value: Option<String>) -> Option<String> {
    value.and_then(|candidate| {
        let trimmed = candidate.trim();
        if trimmed.is_empty() {
            None
        } else {
            Some(trimmed.to_string())
        }
    })
}

fn is_local_url(url: &Url) -> bool {
    matches!(
        url.host_str(),
        Some("localhost") | Some("127.0.0.1") | Some("::1")
    )
}

#[cfg(test)]
mod tests {
    use std::io::Write;

    use super::{AppConfig, ConfigOverrides};

    fn clear_env() {
        unsafe {
            std::env::remove_var("EGOPULSE_MODEL");
            std::env::remove_var("EGOPULSE_API_KEY");
            std::env::remove_var("EGOPULSE_BASE_URL");
            std::env::remove_var("EGOPULSE_LOG_LEVEL");
        }
    }

    #[test]
    fn loads_from_config_file() {
        clear_env();
        let temp_dir = tempfile::tempdir().expect("tempdir");
        let file_path = temp_dir.path().join("egopulse.toml");
        let mut file = std::fs::File::create(&file_path).expect("create config");
        writeln!(
            file,
            "model = \"gpt-5-mini\"\napi_key = \"sk-file\"\nbase_url = \"https://api.openai.com/v1\"\nlog_level = \"debug\""
        )
        .expect("write config");

        let config = AppConfig::load(ConfigOverrides {
            config_path: Some(file_path),
            ..ConfigOverrides::default()
        })
        .expect("load config");

        assert_eq!(config.model(), "gpt-5-mini");
        assert_eq!(config.authorization_token(), "sk-file");
        assert_eq!(config.base_url().as_str(), "https://api.openai.com/v1");
        assert_eq!(config.log_level(), "debug");
    }

    #[test]
    fn allows_local_base_url_without_api_key() {
        clear_env();

        let config = AppConfig::load(ConfigOverrides {
            model: Some("local-model".into()),
            base_url: Some("http://127.0.0.1:1234/v1".into()),
            ..ConfigOverrides::default()
        })
        .expect("load config");

        assert!(config.is_local_base_url());
        assert_eq!(config.authorization_token(), "local-dev");
    }

    #[test]
    fn cli_overrides_environment() {
        clear_env();
        unsafe {
            std::env::set_var("EGOPULSE_MODEL", "from-env");
            std::env::set_var("EGOPULSE_API_KEY", "sk-env");
            std::env::set_var("EGOPULSE_BASE_URL", "https://example.com/v1");
        }

        let config = AppConfig::load(ConfigOverrides {
            model: Some("from-cli".into()),
            api_key: Some("sk-cli".into()),
            base_url: Some("https://api.openai.com/v1".into()),
            ..ConfigOverrides::default()
        })
        .expect("load config");

        assert_eq!(config.model(), "from-cli");
        assert_eq!(config.authorization_token(), "sk-cli");
        clear_env();
    }

    #[test]
    fn redacts_api_key_in_debug_output() {
        clear_env();
        let config = AppConfig::load(ConfigOverrides {
            model: Some("gpt-5-mini".into()),
            api_key: Some("super-secret".into()),
            base_url: Some("https://api.openai.com/v1".into()),
            ..ConfigOverrides::default()
        })
        .expect("load config");

        let rendered = format!("{config:?}");

        assert!(rendered.contains("<redacted>"));
        assert!(!rendered.contains("super-secret"));
    }
}
