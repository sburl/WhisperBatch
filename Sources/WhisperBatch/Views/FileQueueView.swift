import SwiftUI
import WhisperBatchCore

struct FileQueueView: View {
    @Environment(FileQueueViewModel.self) private var viewModel
    @Environment(TranscriptionViewModel.self) private var transcriptionVM

    var body: some View {
        VStack(spacing: 0) {
            if viewModel.files.isEmpty {
                emptyState
            } else {
                fileList
            }

            queueFooter
        }
    }

    private var emptyState: some View {
        VStack(spacing: 18) {
            Image(systemName: "waveform.badge.plus")
                .font(.system(size: 52, weight: .regular))
                .symbolRenderingMode(.hierarchical)
                .foregroundStyle(.tint)

            VStack(spacing: 6) {
                Text("Drop audio or video to transcribe")
                    .font(.title2.weight(.semibold))
                Text("A whole folder works too — every file gets transcribed, on your Mac.")
                    .font(.callout)
                    .foregroundStyle(.secondary)
                    .multilineTextAlignment(.center)
            }

            Button("Choose Files…") {
                viewModel.showFilePicker = true
            }
            .buttonStyle(.borderedProminent)
            .controlSize(.large)
            .padding(.top, 2)
        }
        .padding(44)
        .frame(maxWidth: 480)
        .background(
            RoundedRectangle(cornerRadius: 18)
                .strokeBorder(style: StrokeStyle(lineWidth: 1.5, dash: [7, 6]))
                .foregroundStyle(.quaternary)
        )
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .contentShape(Rectangle())
        .onTapGesture {
            viewModel.showFilePicker = true
        }
    }

    private var fileList: some View {
        List(selection: Binding(
            get: { viewModel.selectedFileIDs },
            set: { viewModel.selectedFileIDs = $0 }
        )) {
            ForEach(viewModel.files) { file in
                FileRowView(file: file)
                    .tag(file.id)
            }
            .onMove { source, destination in
                viewModel.moveFiles(from: source, to: destination)
            }
        }
        .contextMenu(forSelectionType: AudioFile.ID.self) { ids in
            if !ids.isEmpty {
                let selectedFiles = viewModel.files.filter { ids.contains($0.id) }
                let completedFiles = selectedFiles.filter { $0.outputURL != nil }

                if completedFiles.count == 1, let url = completedFiles.first?.outputURL {
                    Button("Show Transcript in Finder") {
                        NSWorkspace.shared.activateFileViewerSelecting([url])
                    }
                } else if completedFiles.count > 1 {
                    Button("Show Transcripts in Finder") {
                        let urls = completedFiles.compactMap(\.outputURL)
                        NSWorkspace.shared.activateFileViewerSelecting(urls)
                    }
                }

                if selectedFiles.count == 1, let file = selectedFiles.first {
                    Button("Show Source in Finder") {
                        NSWorkspace.shared.activateFileViewerSelecting([file.url])
                    }
                }

                Divider()

                Button("Remove Selected") {
                    viewModel.selectedFileIDs = ids
                    viewModel.removeSelected()
                }
            }
        }
    }

    private var queueFooter: some View {
        VStack(spacing: 0) {
            // Batch progress (only during processing)
            if transcriptionVM.isRunning || transcriptionVM.isPaused {
                VStack(spacing: 4) {
                    ProgressView(value: transcriptionVM.overallProgress)

                    HStack {
                        Text("\(transcriptionVM.succeededCount + transcriptionVM.failedCount)/\(transcriptionVM.totalFileCount) files · \(Int(transcriptionVM.overallProgress * 100))%")
                            .font(.caption2)
                            .monospacedDigit()
                            .foregroundStyle(.secondary)

                        Spacer()

                        HStack(spacing: 4) {
                            Text(TimeFormatter.formatDuration(transcriptionVM.elapsedTime))
                                .font(.caption2)
                                .monospacedDigit()
                                .foregroundStyle(.secondary)

                            if let eta = transcriptionVM.estimatedTimeRemaining {
                                Text("· ~\(TimeFormatter.formatDuration(eta)) left")
                                    .font(.caption2)
                                    .monospacedDigit()
                                    .foregroundStyle(.tertiary)
                            }
                        }
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
            } else if transcriptionVM.batchState == .idle && (transcriptionVM.succeededCount > 0 || transcriptionVM.failedCount > 0) {
                // Summary after completion
                HStack(spacing: 8) {
                    Label("\(transcriptionVM.succeededCount) done", systemImage: "checkmark.circle.fill")
                        .font(.caption2)
                        .foregroundStyle(.green)
                    if transcriptionVM.failedCount > 0 {
                        Label("\(transcriptionVM.failedCount) failed", systemImage: "xmark.circle.fill")
                            .font(.caption2)
                            .foregroundStyle(.red)
                    }
                    Text("in \(TimeFormatter.formatDuration(transcriptionVM.elapsedTime))")
                        .font(.caption2)
                        .monospacedDigit()
                        .foregroundStyle(.tertiary)
                    Spacer()

                    let outputURLs = viewModel.files.compactMap(\.outputURL)
                    if !outputURLs.isEmpty {
                        Button("Show in Finder") {
                            NSWorkspace.shared.activateFileViewerSelecting(outputURLs)
                        }
                        .font(.caption)
                        .buttonStyle(.plain)
                        .foregroundStyle(.blue)
                    }

                    if !viewModel.files.isEmpty {
                        Button("Clear All") {
                            viewModel.removeAll()
                        }
                        .font(.caption)
                        .buttonStyle(.plain)
                        .foregroundStyle(.red)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
            } else {
                // Idle — file count only
                HStack {
                    Text("\(viewModel.files.count) files")
                        .font(.caption)
                        .foregroundStyle(.secondary)

                    if viewModel.totalDuration > 0 {
                        Text("(\(TimeFormatter.formatDurationCompact(viewModel.totalDuration)))")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer()

                    if !viewModel.files.isEmpty {
                        Button("Clear All") {
                            viewModel.removeAll()
                        }
                        .font(.caption)
                        .buttonStyle(.plain)
                        .foregroundStyle(.red)
                    }
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
            }
        }
        .background(.bar)
    }
}
