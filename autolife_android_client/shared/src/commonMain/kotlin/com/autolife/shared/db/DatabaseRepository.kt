package com.autolife.shared.db

import app.cash.sqldelight.coroutines.asFlow
import app.cash.sqldelight.coroutines.mapToList
import app.cash.sqldelight.db.SqlDriver
import com.autolife.shared.model.JournalEntry
import com.autolife.shared.model.SensorLog
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.IO
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map

/**
 * Cross-platform database repository wrapping SQLDelight.
 * Call [init] once at app startup with a platform-specific SqlDriver.
 */
object DatabaseRepository {

    private var database: AutoLifeDatabase? = null

    fun init(driver: SqlDriver) {
        database = AutoLifeDatabase(driver)
    }

    private val queries: AutoLifeQueries
        get() = database?.autoLifeQueries
            ?: error("DatabaseRepository not initialized. Call init(driver) first.")

    // ── Inserts ─────────────────────────────────────────────────────

    fun insertLog(log: SensorLog) {
        queries.insertLog(
            timestamp = log.timestamp,
            type = log.type,
            content = log.content
        )
    }

    fun insertJournal(journal: JournalEntry) {
        queries.insertJournal(
            createdTimestamp = journal.createdTimestamp,
            periodStart = journal.periodStart,
            periodEnd = journal.periodEnd,
            content = journal.content
        )
    }

    // ── Queries ─────────────────────────────────────────────────────

    fun getLogsBetween(start: Long, end: Long): List<SensorLog> {
        return queries.getLogsBetween(start, end).executeAsList().map { row ->
            SensorLog(id = row.id, timestamp = row.timestamp, type = row.type, content = row.content)
        }
    }

    fun observeRecentLogs(): Flow<List<SensorLog>> {
        return queries.getRecentLogs().asFlow().mapToList(Dispatchers.IO).map { rows ->
            rows.map { row ->
                SensorLog(id = row.id, timestamp = row.timestamp, type = row.type, content = row.content)
            }
        }
    }

    fun getLogsByType(type: String): List<SensorLog> {
        return queries.getLogsByType(type).executeAsList().map { row ->
            SensorLog(id = row.id, timestamp = row.timestamp, type = row.type, content = row.content)
        }
    }

    fun observeJournals(): Flow<List<JournalEntry>> {
        return queries.getAllJournalsDesc().asFlow().mapToList(Dispatchers.IO).map { rows ->
            rows.map { row ->
                JournalEntry(
                    id = row.id,
                    createdTimestamp = row.createdTimestamp,
                    periodStart = row.periodStart,
                    periodEnd = row.periodEnd,
                    content = row.content
                )
            }
        }
    }

    fun getAllJournals(): List<JournalEntry> {
        return queries.getAllJournalsAsc().executeAsList().map { row ->
            JournalEntry(
                id = row.id,
                createdTimestamp = row.createdTimestamp,
                periodStart = row.periodStart,
                periodEnd = row.periodEnd,
                content = row.content
            )
        }
    }

    // ── Deletes ─────────────────────────────────────────────────────

    fun deleteAllLogs() {
        queries.deleteAllLogs()
    }

    fun deleteAllJournals() {
        queries.deleteAllJournals()
    }
}
