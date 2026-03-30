use crate::config::AppConfig;
use crate::error::EgoPulseError;
use crate::provider::{Provider, create_provider};

pub struct RuntimeBootstrap {
    config: AppConfig,
}

impl RuntimeBootstrap {
    pub fn new(config: AppConfig) -> Self {
        Self { config }
    }

    pub async fn ask(&self, prompt: &str) -> Result<String, EgoPulseError> {
        let provider = self.build_provider();

        tokio::select! {
            response = provider.ask(prompt) => Ok(response?),
            _ = tokio::signal::ctrl_c() => Err(EgoPulseError::ShutdownRequested),
        }
    }

    fn build_provider(&self) -> Box<dyn Provider> {
        create_provider(self.config.clone())
    }
}
