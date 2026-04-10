package com.autolife.shared.db

import android.content.Context
import app.cash.sqldelight.db.SqlDriver
import app.cash.sqldelight.driver.android.AndroidSqliteDriver

fun createAndroidDriver(context: Context): SqlDriver {
    return AndroidSqliteDriver(AutoLifeDatabase.Schema, context, "autolife_db")
}
