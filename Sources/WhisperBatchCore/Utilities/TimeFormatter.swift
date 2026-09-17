import Foundation

public struct TimeFormatter {
    /// Format a duration in seconds as "Xh Ym Zs" or "Ym Zs" or "Zs".
    public static func formatDuration(_ seconds: TimeInterval) -> String {
        let total = Int(seconds)
        if total < 0 { return "0s" }
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let secs = total % 60
        if hours > 0 {
            return "\(hours)h \(minutes)m \(secs)s"
        } else if minutes > 0 {
            return "\(minutes)m \(secs)s"
        } else {
            return "\(secs)s"
        }
    }

    /// Format a duration in seconds as "MM:SS" or "H:MM:SS".
    public static func formatDurationCompact(_ seconds: TimeInterval) -> String {
        let total = Int(seconds)
        if total < 0 { return "0:00" }
        let hours = total / 3600
        let minutes = (total % 3600) / 60
        let secs = total % 60
        if hours > 0 {
            return String(format: "%d:%02d:%02d", hours, minutes, secs)
        } else {
            return String(format: "%d:%02d", minutes, secs)
        }
    }

    /// Estimate remaining time based on speed and remaining duration.
    public static func estimateRemainingTime(
        remainingAudioDuration: TimeInterval,
        modelSpeed: Double
    ) -> TimeInterval {
        guard modelSpeed > 0 else { return 0 }
        return remainingAudioDuration / modelSpeed
    }
}
