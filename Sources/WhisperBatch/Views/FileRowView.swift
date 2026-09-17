import SwiftUI
import WhisperBatchCore

struct FileRowView: View {
    let file: AudioFile
    @State private var showCropSheet = false

    var body: some View {
        HStack(spacing: 10) {
            fileIcon

            VStack(alignment: .leading, spacing: 2) {
                Text(file.filename)
                    .font(.body)
                    .lineLimit(1)
                    .truncationMode(.middle)

                HStack(spacing: 6) {
                    if let duration = file.duration {
                        Text(TimeFormatter.formatDurationCompact(duration))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    if file.hasCrop, let start = file.cropStart, let end = file.cropEnd {
                        Label(
                            "\(TimeFormatter.formatDurationCompact(start))-\(TimeFormatter.formatDurationCompact(end))",
                            systemImage: "scissors"
                        )
                        .font(.caption2)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 1)
                        .background(.orange.opacity(0.18))
                        .clipShape(RoundedRectangle(cornerRadius: 3))
                    }

                    if let modelOverride = file.modelOverride {
                        Text(modelOverride.displayName)
                            .font(.caption2)
                            .padding(.horizontal, 4)
                            .padding(.vertical, 1)
                            .background(.blue.opacity(0.15))
                            .clipShape(RoundedRectangle(cornerRadius: 3))
                    }
                }
            }

            Spacer()

            if file.duration != nil && (file.status == .pending || file.status == .complete) {
                Button {
                    showCropSheet = true
                } label: {
                    Image(systemName: file.hasCrop ? "scissors.circle.fill" : "scissors")
                        .foregroundStyle(file.hasCrop ? .orange : .secondary)
                }
                .buttonStyle(.borderless)
                .help("Crop region to transcribe")
            }

            statusBadge
        }
        .padding(.vertical, 2)
        .sheet(isPresented: $showCropSheet) {
            CropSheet(file: file)
        }
    }

    @ViewBuilder
    private var fileIcon: some View {
        let ext = file.url.pathExtension.lowercased()
        let isVideo = ["mp4", "mkv", "mov", "avi", "flv", "webm", "wmv", "mpeg", "mpg", "ts", "3gp", "m4v"].contains(ext)
        Image(systemName: isVideo ? "film" : "waveform")
            .font(.title3)
            .foregroundStyle(.secondary)
            .frame(width: 24)
    }

    @ViewBuilder
    private var statusBadge: some View {
        switch file.status {
        case .pending:
            Image(systemName: "clock")
                .foregroundStyle(.secondary)
        case .processing:
            HStack(spacing: 6) {
                if file.progress > 0 {
                    ProgressView(value: file.progress)
                        .frame(width: 60)
                    Text("\(Int(file.progress * 100))%")
                        .font(.caption2)
                        .monospacedDigit()
                        .foregroundStyle(.secondary)
                } else {
                    ProgressView()
                        .controlSize(.small)
                }
            }
        case .complete:
            Image(systemName: "checkmark.circle.fill")
                .foregroundStyle(.green)
        case .error:
            Image(systemName: "exclamationmark.triangle.fill")
                .foregroundStyle(.red)
                .help(file.errorMessage ?? "Error")
        case .invalid:
            Image(systemName: "xmark.circle.fill")
                .foregroundStyle(.orange)
                .help(file.errorMessage ?? "Invalid file")
        case .notAccessible:
            Image(systemName: "icloud.slash")
                .foregroundStyle(.orange)
                .help("File not accessible")
        }
    }
}
