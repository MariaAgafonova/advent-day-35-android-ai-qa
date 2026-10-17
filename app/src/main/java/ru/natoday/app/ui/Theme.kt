package ru.natoday.app.ui

import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.graphics.Color

private val Light = lightColorScheme(
    primary = Color(0xFF466751), onPrimary = Color.White,
    primaryContainer = Color(0xFFD7E9D7), onPrimaryContainer = Color(0xFF233D2C),
    background = Color(0xFFFAF9F5), surface = Color(0xFFFAF9F5),
    surfaceVariant = Color(0xFFEAEDE4), onSurface = Color(0xFF252C26),
)
private val Dark = darkColorScheme(
    primary = Color(0xFFB0D0B3), onPrimary = Color(0xFF1D3625),
    primaryContainer = Color(0xFF334D3B), onPrimaryContainer = Color(0xFFD7E9D7),
    background = Color(0xFF141A16), surface = Color(0xFF141A16),
    surfaceVariant = Color(0xFF303A32), onSurface = Color(0xFFE1E7DF),
)

@Composable fun PlannerTheme(content: @Composable () -> Unit) {
    MaterialTheme(colorScheme = if (isSystemInDarkTheme()) Dark else Light, content = content)
}
