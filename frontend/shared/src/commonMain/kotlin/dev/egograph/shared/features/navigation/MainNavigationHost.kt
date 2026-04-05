package dev.egograph.shared.features.navigation

import androidx.compose.runtime.Composable

@Composable
fun MainNavigationHost(
    activeView: MainView,
    onSwipeToSidebar: () -> Unit,
    onSwipeToOther: () -> Unit,
    content: @Composable (MainView) -> Unit,
) {
    SwipeNavigationContainer(
        activeView = activeView,
        onSwipeToSidebar = onSwipeToSidebar,
        onSwipeToOther = onSwipeToOther,
    ) {
        MainViewTransition(
            activeView = activeView,
            content = content,
        )
    }
}
