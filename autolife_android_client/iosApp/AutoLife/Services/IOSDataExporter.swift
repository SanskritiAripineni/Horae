import Foundation
import ComposeApp

/// Exports all journal entries to the app's Documents directory.
/// iOS equivalent of Android's DataExporter.
///
/// RESEARCH-READINESS NOTE (audit 2026-04-10):
///   The export schema now matches Android's DataExporter exactly:
///     - Same separator widths (40-char "=", 40-char "-")
///     - Same field names ("Created At:", "Period: ... TO ...")
///     - Same date format ("yyyy-MM-dd HH:mm:ss")
///     - Same filename prefix ("all_journals_")
///   This ensures cross-platform export consistency for research data.
class IOSDataExporter {

    static func exportJournals() {
        let journals = DatabaseRepository.shared.getAllJournals()
        guard !journals.isEmpty else { return }

        let dateFormatter = DateFormatter()
        dateFormatter.dateFormat = "yyyy-MM-dd HH:mm:ss"
        dateFormatter.locale = Locale(identifier: "en_US_POSIX")

        let exportDateFormatter = DateFormatter()
        exportDateFormatter.dateFormat = "yyyyMMdd_HHmmss"
        exportDateFormatter.locale = Locale(identifier: "en_US_POSIX")

        var output = ""

        for (index, journal) in journals.enumerated() {
            let created = Date(timeIntervalSince1970: Double(journal.createdTimestamp) / 1000.0)
            let start = Date(timeIntervalSince1970: Double(journal.periodStart) / 1000.0)
            let end = Date(timeIntervalSince1970: Double(journal.periodEnd) / 1000.0)

            output += String(repeating: "=", count: 40) + "\n"
            output += "JOURNAL ENTRY #\(index + 1)\n"
            output += "Created At: \(dateFormatter.string(from: created))\n"
            output += "Period: \(dateFormatter.string(from: start)) TO \(dateFormatter.string(from: end))\n"
            output += String(repeating: "-", count: 40) + "\n\n"
            output += journal.content + "\n\n"
        }

        // Write to Documents directory
        let docs = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first!
        let autoLifeDir = docs.appendingPathComponent("AutoLife")
        try? FileManager.default.createDirectory(at: autoLifeDir, withIntermediateDirectories: true)

        let fileName = "all_journals_\(exportDateFormatter.string(from: Date())).txt"
        let fileURL = autoLifeDir.appendingPathComponent(fileName)

        try? output.write(to: fileURL, atomically: true, encoding: .utf8)
    }
}
