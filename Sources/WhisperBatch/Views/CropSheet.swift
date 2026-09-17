import SwiftUI
import WhisperBatchCore

struct CropSheet: View {
    let file: AudioFile
    @Environment(\.dismiss) private var dismiss

    @State private var peaks: [Float] = []
    @State private var loading = true
    @State private var errorMessage: String?
    @State private var startFraction = 0.0
    @State private var endFraction = 1.0

    private var duration: TimeInterval { file.duration ?? 0 }
    private var startTime: TimeInterval { startFraction * duration }
    private var endTime: TimeInterval { endFraction * duration }
    private var selectedDuration: TimeInterval { max(0, endTime - startTime) }
    private var isFullRange: Bool { startFraction <= 0.001 && endFraction >= 0.999 }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 2) {
                Text("Crop \(file.filename)")
                    .font(.headline)
                    .lineLimit(1)
                    .truncationMode(.middle)
                Text("Drag the handles to pick the part you want to transcribe.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Group {
                if loading {
                    HStack(spacing: 8) {
                        ProgressView()
                            .controlSize(.small)
                        Text("Reading audio...")
                            .foregroundStyle(.secondary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 120)
                } else if let errorMessage {
                    Label(errorMessage, systemImage: "exclamationmark.triangle")
                        .foregroundStyle(.orange)
                        .frame(maxWidth: .infinity, minHeight: 120)
                } else {
                    WaveformView(peaks: peaks, startFraction: $startFraction, endFraction: $endFraction)
                        .frame(height: 120)
                }
            }

            HStack {
                timeLabel("Start", startTime)
                Spacer()
                VStack(spacing: 0) {
                    Text("Selected")
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                    Text(TimeFormatter.formatDurationCompact(selectedDuration))
                        .font(.callout.monospacedDigit().weight(.medium))
                }
                Spacer()
                timeLabel("End", endTime)
            }

            HStack {
                if file.hasCrop {
                    Button("Remove Crop", role: .destructive) {
                        file.cropStart = nil
                        file.cropEnd = nil
                        dismiss()
                    }
                }
                Spacer()
                Button("Cancel") { dismiss() }
                    .keyboardShortcut(.cancelAction)
                Button("Apply Crop") { apply() }
                    .keyboardShortcut(.defaultAction)
                    .disabled(loading || errorMessage != nil || isFullRange)
            }
        }
        .padding(18)
        .frame(width: 560)
        .task { await load() }
    }

    private func timeLabel(_ label: String, _ time: TimeInterval) -> some View {
        VStack(spacing: 0) {
            Text(label)
                .font(.caption2)
                .foregroundStyle(.secondary)
            Text(TimeFormatter.formatDurationCompact(time))
                .font(.callout.monospacedDigit())
        }
    }

    private func apply() {
        file.cropStart = startTime
        file.cropEnd = endTime
        dismiss()
    }

    private func load() async {
        if let start = file.cropStart, let end = file.cropEnd, duration > 0, end > start {
            startFraction = start / duration
            endFraction = end / duration
        }
        do {
            peaks = try await WaveformGenerator.generate(url: file.url)
            loading = false
        } catch {
            errorMessage = error.localizedDescription
            loading = false
        }
    }
}
