package dev.egograph.shared.features.chat.components

import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import dev.egograph.shared.core.domain.model.LLMModel

@Composable
fun ChatComposer(
    models: List<LLMModel>,
    selectedModelId: String?,
    isLoadingModels: Boolean,
    modelsError: String?,
    onModelSelected: (String) -> Unit,
    onSendMessage: (String) -> Unit,
    isLoading: Boolean = false,
    onVoiceInputClick: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    var text by remember { mutableStateOf("") }

    ChatComposerField(
        text = text,
        onTextChange = { text = it },
        isLoading = isLoading,
        models = models,
        selectedModelId = selectedModelId,
        isLoadingModels = isLoadingModels,
        modelsError = modelsError,
        onModelSelected = onModelSelected,
        onSendMessage = {
            onSendMessage(text)
            text = ""
        },
        onVoiceInputClick = onVoiceInputClick,
        modifier =
            modifier
                .fillMaxWidth()
                .padding(
                    horizontal = ChatComposerMetrics.outerHorizontalPadding,
                    vertical = ChatComposerMetrics.outerVerticalPadding,
                ),
    )
}
