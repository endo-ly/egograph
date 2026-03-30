use std::path::PathBuf;

use clap::{Args, Parser, Subcommand};

use crate::config::{AppConfig, ConfigOverrides};
use crate::error::EgoPulseError;
use crate::logging::init_logging;
use crate::runtime::RuntimeBootstrap;

#[derive(Debug, Parser)]
#[command(name = "egopulse", version, about = "EgoPulse runtime foundation")]
pub struct Cli {
    #[command(flatten)]
    global: GlobalOptions,
    #[command(subcommand)]
    command: Commands,
}

#[derive(Debug, Args, Clone)]
pub struct GlobalOptions {
    /// Optional TOML config file.
    #[arg(long, value_name = "PATH")]
    pub config: Option<PathBuf>,

    /// OpenAI-compatible model name.
    #[arg(long, env = "EGOPULSE_MODEL")]
    pub model: Option<String>,

    /// OpenAI-compatible API key.
    #[arg(long, env = "EGOPULSE_API_KEY")]
    pub api_key: Option<String>,

    /// OpenAI-compatible base URL.
    #[arg(long, env = "EGOPULSE_BASE_URL")]
    pub base_url: Option<String>,

    /// Log level for tracing subscriber.
    #[arg(long, env = "EGOPULSE_LOG_LEVEL")]
    pub log_level: Option<String>,
}

#[derive(Debug, Subcommand)]
pub enum Commands {
    /// Send a single prompt to the configured OpenAI-compatible endpoint.
    Ask { prompt: String },
}

impl From<&GlobalOptions> for ConfigOverrides {
    fn from(value: &GlobalOptions) -> Self {
        Self {
            config_path: value.config.clone(),
            model: value.model.clone(),
            api_key: value.api_key.clone(),
            base_url: value.base_url.clone(),
            log_level: value.log_level.clone(),
        }
    }
}

pub async fn run() -> Result<(), EgoPulseError> {
    let cli = Cli::parse();
    let config = AppConfig::load(ConfigOverrides::from(&cli.global))?;
    init_logging(config.log_level())?;

    let runtime = RuntimeBootstrap::new(config);

    match cli.command {
        Commands::Ask { prompt } => {
            let response = runtime.ask(&prompt).await?;
            println!("assistant: {response}");
        }
    }

    Ok(())
}
