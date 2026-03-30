use async_trait::async_trait;

use crate::error::ProviderError;

use super::Provider;

pub struct FakeProvider {
    response: String,
}

impl FakeProvider {
    pub fn new(response: impl Into<String>) -> Self {
        Self {
            response: response.into(),
        }
    }
}

#[async_trait]
impl Provider for FakeProvider {
    async fn ask(&self, _prompt: &str) -> Result<String, ProviderError> {
        Ok(self.response.clone())
    }
}

#[cfg(test)]
mod tests {
    use super::{FakeProvider, Provider};

    #[tokio::test]
    async fn returns_configured_response() {
        let provider = FakeProvider::new("hello from fake");

        let response = provider.ask("ping").await.expect("fake response");

        assert_eq!(response, "hello from fake");
    }
}
