package com.autolife.shared.db

import android.content.Context
import androidx.sqlite.db.SupportSQLiteDatabase
import app.cash.sqldelight.db.SqlDriver
import app.cash.sqldelight.driver.android.AndroidSqliteDriver

fun createAndroidDriver(context: Context): SqlDriver {
    return AndroidSqliteDriver(
        schema = AutoLifeDatabase.Schema,
        context = context,
        name = "autolife_db",
        callback = object : AndroidSqliteDriver.Callback(AutoLifeDatabase.Schema) {
            override fun onDowngrade(db: SupportSQLiteDatabase, oldVersion: Int, newVersion: Int) {
                db.execSQL("DROP TABLE IF EXISTS sensor_logs")
                db.execSQL("DROP TABLE IF EXISTS journal_entries")
                db.execSQL("DROP TABLE IF EXISTS user_consent")
                db.execSQL("DROP TABLE IF EXISTS auth_tokens")
                onCreate(db)
            }
        },
    )
}
