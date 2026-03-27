package com.google.mediapipe.examples.llminference.data

import android.content.Context
import androidx.room.Dao
import androidx.room.Database
import androidx.room.Entity
import androidx.room.Insert
import androidx.room.PrimaryKey
import androidx.room.Query
import androidx.room.Room
import androidx.room.RoomDatabase
import kotlinx.coroutines.flow.Flow

@Entity(tableName = "sensor_logs")
data class SensorLog(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val timestamp: Long,
    val type: String, // "MOTION", "LOCATION", "WIFI"
    val content: String // JSON or raw string
)

@Entity(tableName = "journal_entries")
data class JournalEntry(
    @PrimaryKey(autoGenerate = true) val id: Long = 0,
    val createdTimestamp: Long,
    val periodStart: Long,
    val periodEnd: Long,
    val content: String
)

@Dao
interface LogDao {
    @Insert
    suspend fun insertLog(log: SensorLog)

    @Insert
    suspend fun insertJournal(journal: JournalEntry)

    // Get logs for a specific time range to fuse
    @Query("SELECT * FROM sensor_logs WHERE timestamp BETWEEN :start AND :end ORDER BY timestamp ASC")
    suspend fun getLogsBetween(start: Long, end: Long): List<SensorLog>

    // Observe logs for the "Live Dashboard"
    @Query("SELECT * FROM sensor_logs ORDER BY timestamp DESC LIMIT 50")
    fun observeRecentLogs(): Flow<List<SensorLog>>

    // Observe journals
    @Query("SELECT * FROM journal_entries ORDER BY createdTimestamp DESC")
    fun observeJournals(): Flow<List<JournalEntry>>

    @Query("SELECT * FROM journal_entries ORDER BY createdTimestamp ASC")
    suspend fun getAllJournals(): List<JournalEntry>

    @Query("DELETE FROM sensor_logs")
    suspend fun deleteAllLogs()
}

@Database(entities = [SensorLog::class, JournalEntry::class], version = 1, exportSchema = false)
abstract class AppDatabase : RoomDatabase() {
    abstract fun logDao(): LogDao

    companion object {
        @Volatile
        private var INSTANCE: AppDatabase? = null

        fun getDatabase(context: Context): AppDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    AppDatabase::class.java,
                    "autolife_db"
                ).fallbackToDestructiveMigration().build()
                INSTANCE = instance
                instance
            }
        }
    }
}
