package com.autolife.composeapp

import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import com.autolife.composeapp.ui.AutoLifeNavHost
import com.autolife.composeapp.ui.theme.AutoLifeTheme

@Composable
fun AutoLifeApp(
    onServiceToggle: (Boolean) -> Unit = {},
    modifier: Modifier = Modifier,
) {
    AutoLifeTheme {
        AutoLifeNavHost(
            onServiceToggle = onServiceToggle,
            modifier = modifier,
        )
    }
}
