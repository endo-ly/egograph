use async_trait::async_trait;
use reqwest::header::{AUTHORIZATION, CONTENT_TYPE, HeaderMap, HeaderValue};
use serde::{Deserialize, Serialize};

use crate::config::AppConfig;
use crate::error::ProviderError;

use super::Provider;

pub struct OpenAiCompatibleProvider {
    client: reqwest::Client,
    config: AppConfig,
}

impl OpenAiCompatibleProvider {
    pub fn new(config: AppConfig) -> Self {
        let client = reqwest::Client::builder()
            .user_agent(format!("egopulse/{}", env!("CARGO_PKG_VERSION")))
            .build()
            .expect("reqwest client");

        Self { client, config }
    }
}

#[async_trait]
impl Provider for OpenAiCompatibleProvider {
    async fn ask(&self, prompt: &str) -> Result<String, ProviderError> {
        let mut headers = HeaderMap::new();
        let auth_value = format!("Bearer {}", self.config.authorization_token());
        let header_value = HeaderValue::from_str(&auth_value)
            .map_err(|error| ProviderError::InvalidResponse(error.to_string()))?;
        headers.insert(AUTHORIZATION, header_value);
        headers.insert(CONTENT_TYPE, HeaderValue::from_static("application/json"));

        let url = format!(
            "{}/chat/completions",
            self.config.base_url().as_str().trim_end_matches('/')
        );
        let payload = ChatCompletionRequest {
            model: self.config.model().to_string(),
            messages: vec![ChatMessage {
                role: "user".to_string(),
                content: prompt.to_string(),
            }],
        };

        let response = self
            .client
            .post(url)
            .headers(headers)
            .json(&payload)
            .send()
            .await?;

        let status = response.status();
        if !status.is_success() {
            let body = response
                .text()
                .await
                .unwrap_or_else(|_| "<unreadable>".into());
            return Err(ProviderError::ApiError { status, body });
        }

        let response_body: ChatCompletionResponse = response.json().await?;
        let choice = response_body
            .choices
            .into_iter()
            .next()
            .ok_or_else(|| ProviderError::InvalidResponse("choices[0] missing".into()))?;

        extract_message_text(choice.message.content)
    }
}

fn extract_message_text(content: MessageContent) -> Result<String, ProviderError> {
    let text = match content {
        MessageContent::Text(text) => text,
        MessageContent::Parts(parts) => parts
            .into_iter()
            .filter_map(|part| match part {
                ContentPart::Text { text } => Some(text),
                ContentPart::Refusal { refusal } => Some(refusal),
                ContentPart::Ignored => None,
            })
            .collect::<Vec<_>>()
            .join("\n"),
    };

    let trimmed = text.trim();
    if trimmed.is_empty() {
        return Err(ProviderError::InvalidResponse(
            "assistant content was empty".into(),
        ));
    }

    Ok(trimmed.to_string())
}

#[derive(Serialize)]
struct ChatCompletionRequest {
    model: String,
    messages: Vec<ChatMessage>,
}

#[derive(Serialize)]
struct ChatMessage {
    role: String,
    content: String,
}

#[derive(Deserialize)]
struct ChatCompletionResponse {
    choices: Vec<Choice>,
}

#[derive(Deserialize)]
struct Choice {
    message: AssistantMessage,
}

#[derive(Deserialize)]
struct AssistantMessage {
    content: MessageContent,
}

#[derive(Deserialize)]
#[serde(untagged)]
enum MessageContent {
    Text(String),
    Parts(Vec<ContentPart>),
}

#[derive(Deserialize)]
#[serde(tag = "type")]
enum ContentPart {
    #[serde(rename = "text")]
    Text { text: String },
    #[serde(rename = "refusal")]
    Refusal { refusal: String },
    #[serde(other)]
    Ignored,
}

#[cfg(test)]
mod tests {
    use wiremock::matchers::{body_partial_json, header, method, path};
    use wiremock::{Mock, MockServer, ResponseTemplate};

    use crate::config::{AppConfig, ConfigOverrides};

    use super::{OpenAiCompatibleProvider, Provider};

    #[tokio::test]
    async fn sends_openai_compatible_request() {
        let server = MockServer::start().await;
        Mock::given(method("POST"))
            .and(path("/v1/chat/completions"))
            .and(header("authorization", "Bearer sk-test"))
            .and(body_partial_json(serde_json::json!({
                "model": "gpt-5-mini",
                "messages": [{"role": "user", "content": "hello"}]
            })))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
                "choices": [{
                    "message": {
                        "content": "hello back"
                    }
                }]
            })))
            .mount(&server)
            .await;

        let config = AppConfig::load(ConfigOverrides {
            model: Some("gpt-5-mini".into()),
            api_key: Some("sk-test".into()),
            base_url: Some(format!("{}/v1", server.uri())),
            ..ConfigOverrides::default()
        })
        .expect("config");

        let provider = OpenAiCompatibleProvider::new(config);

        let response = provider.ask("hello").await.expect("provider response");

        assert_eq!(response, "hello back");
    }

    #[tokio::test]
    async fn parses_structured_content_blocks() {
        let server = MockServer::start().await;
        Mock::given(method("POST"))
            .and(path("/v1/chat/completions"))
            .respond_with(ResponseTemplate::new(200).set_body_json(serde_json::json!({
                "choices": [{
                    "message": {
                        "content": [
                            {"type": "text", "text": "first"},
                            {"type": "text", "text": "second"}
                        ]
                    }
                }]
            })))
            .mount(&server)
            .await;

        let config = AppConfig::load(ConfigOverrides {
            model: Some("gpt-5-mini".into()),
            api_key: Some("sk-test".into()),
            base_url: Some(format!("{}/v1", server.uri())),
            ..ConfigOverrides::default()
        })
        .expect("config");

        let provider = OpenAiCompatibleProvider::new(config);

        let response = provider.ask("hello").await.expect("provider response");

        assert_eq!(response, "first\nsecond");
    }
}
