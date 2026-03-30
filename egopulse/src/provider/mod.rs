mod fake;
mod openai_compatible;

use async_trait::async_trait;

use crate::config::AppConfig;
use crate::error::ProviderError;

pub use fake::FakeProvider;
pub use openai_compatible::OpenAiCompatibleProvider;

#[async_trait]
pub trait Provider: Send + Sync {
    async fn ask(&self, prompt: &str) -> Result<String, ProviderError>;
}

pub fn create_provider(config: AppConfig) -> Box<dyn Provider> {
    Box::new(OpenAiCompatibleProvider::new(config))
}
