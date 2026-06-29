package com.autolife.shared.db

import app.cash.sqldelight.db.SqlDriver
import app.cash.sqldelight.driver.native.NativeSqliteDriver

fun createNativeDriver(): SqlDriver {
    return NativeSqliteDriver(AutoLifeDatabase.Schema, "autolife_db")
}
