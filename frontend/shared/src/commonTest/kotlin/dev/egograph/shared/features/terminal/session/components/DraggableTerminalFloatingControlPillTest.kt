package dev.egograph.shared.features.terminal.session.components

import kotlin.test.Test
import kotlin.test.assertEquals

class DraggableTerminalFloatingControlPillTest {
    @Test
    fun `default position stays centered horizontally and above bottom margin`() {
        // Arrange
        val bounds =
            TerminalFloatingControlBounds(
                containerWidthPx = 360f,
                containerHeightPx = 800f,
                controlWidthPx = 140f,
                controlHeightPx = 48f,
                horizontalMarginPx = 20f,
                verticalMarginPx = 16f,
            )

        // Act
        val position = defaultTerminalFloatingControlPosition(bounds)

        // Assert
        assertEquals(110f, position.xPx)
        assertEquals(736f, position.yPx)
    }

    @Test
    fun `default position respects system bar insets`() {
        // Arrange
        val bounds =
            TerminalFloatingControlBounds(
                containerWidthPx = 360f,
                containerHeightPx = 800f,
                controlWidthPx = 140f,
                controlHeightPx = 48f,
                horizontalMarginPx = 20f,
                verticalMarginPx = 16f,
                topInsetPx = 24f,
                bottomInsetPx = 34f,
            )

        // Act
        val position = defaultTerminalFloatingControlPosition(bounds)

        // Assert
        assertEquals(110f, position.xPx)
        assertEquals(702f, position.yPx)
    }

    @Test
    fun `clamp keeps control inside top left bounds`() {
        // Arrange
        val bounds =
            TerminalFloatingControlBounds(
                containerWidthPx = 360f,
                containerHeightPx = 800f,
                controlWidthPx = 140f,
                controlHeightPx = 48f,
                horizontalMarginPx = 20f,
                verticalMarginPx = 16f,
                topInsetPx = 24f,
                bottomInsetPx = 34f,
            )
        val position = TerminalFloatingControlPosition(xPx = -80f, yPx = -20f)

        // Act
        val clamped = clampTerminalFloatingControlPosition(position = position, bounds = bounds)

        // Assert
        assertEquals(20f, clamped.xPx)
        assertEquals(40f, clamped.yPx)
    }

    @Test
    fun `clamp keeps control inside bottom right bounds`() {
        // Arrange
        val bounds =
            TerminalFloatingControlBounds(
                containerWidthPx = 360f,
                containerHeightPx = 800f,
                controlWidthPx = 140f,
                controlHeightPx = 48f,
                horizontalMarginPx = 20f,
                verticalMarginPx = 16f,
                topInsetPx = 24f,
                bottomInsetPx = 34f,
            )
        val position = TerminalFloatingControlPosition(xPx = 400f, yPx = 900f)

        // Act
        val clamped = clampTerminalFloatingControlPosition(position = position, bounds = bounds)

        // Assert
        assertEquals(200f, clamped.xPx)
        assertEquals(702f, clamped.yPx)
    }

    @Test
    fun `resolve display position keeps saved position when obstacle does not overlap`() {
        // Arrange
        val bounds =
            TerminalFloatingControlBounds(
                containerWidthPx = 360f,
                containerHeightPx = 800f,
                controlWidthPx = 140f,
                controlHeightPx = 48f,
                horizontalMarginPx = 20f,
                verticalMarginPx = 16f,
            )
        val position = TerminalFloatingControlPosition(xPx = 32f, yPx = 120f)
        val obstacle =
            TerminalFloatingControlObstacle(
                leftPx = 0f,
                topPx = 620f,
                rightPx = 360f,
                bottomPx = 800f,
            )

        // Act
        val resolved =
            resolveTerminalFloatingControlDisplayPosition(
                position = position,
                bounds = bounds,
                obstacle = obstacle,
                relocationGapPx = 16f,
            )

        // Assert
        assertEquals(position, resolved)
    }

    @Test
    fun `resolve display position relocates to right above obstacle when overlapping`() {
        // Arrange
        val bounds =
            TerminalFloatingControlBounds(
                containerWidthPx = 360f,
                containerHeightPx = 800f,
                controlWidthPx = 140f,
                controlHeightPx = 48f,
                horizontalMarginPx = 20f,
                verticalMarginPx = 16f,
            )
        val position = TerminalFloatingControlPosition(xPx = 110f, yPx = 736f)
        val obstacle =
            TerminalFloatingControlObstacle(
                leftPx = 0f,
                topPx = 620f,
                rightPx = 360f,
                bottomPx = 800f,
            )

        // Act
        val resolved =
            resolveTerminalFloatingControlDisplayPosition(
                position = position,
                bounds = bounds,
                obstacle = obstacle,
                relocationGapPx = 16f,
            )

        // Assert
        assertEquals(200f, resolved.xPx)
        assertEquals(556f, resolved.yPx)
    }

    @Test
    fun `drag clamp stops at top edge of obstacle`() {
        // Arrange
        val bounds =
            TerminalFloatingControlBounds(
                containerWidthPx = 360f,
                containerHeightPx = 800f,
                controlWidthPx = 140f,
                controlHeightPx = 48f,
                horizontalMarginPx = 20f,
                verticalMarginPx = 16f,
            )
        val obstacle =
            TerminalFloatingControlObstacle(
                leftPx = 0f,
                topPx = 620f,
                rightPx = 360f,
                bottomPx = 800f,
            )
        val position = TerminalFloatingControlPosition(xPx = 120f, yPx = 700f)

        // Act
        val clamped = clampTerminalFloatingControlDragPosition(position = position, bounds = bounds, obstacle = obstacle)

        // Assert
        assertEquals(120f, clamped.xPx)
        assertEquals(572f, clamped.yPx)
    }

    @Test
    fun `relocated position clamps to top safe area when obstacle is high`() {
        // Arrange
        val bounds =
            TerminalFloatingControlBounds(
                containerWidthPx = 360f,
                containerHeightPx = 800f,
                controlWidthPx = 140f,
                controlHeightPx = 48f,
                horizontalMarginPx = 20f,
                verticalMarginPx = 16f,
                topInsetPx = 24f,
            )
        val obstacle =
            TerminalFloatingControlObstacle(
                leftPx = 0f,
                topPx = 80f,
                rightPx = 360f,
                bottomPx = 800f,
            )

        // Act
        val relocated = relocatedTerminalFloatingControlPosition(bounds = bounds, obstacle = obstacle, relocationGapPx = 16f)

        // Assert
        assertEquals(200f, relocated.xPx)
        assertEquals(40f, relocated.yPx)
    }
}
