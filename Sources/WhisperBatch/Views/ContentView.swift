import SwiftUI
import WhisperBatchCore

struct ContentView: View {
    @Environment(FileQueueViewModel.self) private var fileQueueVM
    @Environment(TranscriptionViewModel.self) private var transcriptionVM
    @Environment(ModelManagerViewModel.self) private var modelManagerVM
    @Environment(\.openSettings) private var openSettings

    @State private var selectedModel: WhisperModelType = AppSettings.shared.defaultModel
    @State private var selectedFormat: OutputFormat = AppSettings.shared.defaultOutputFormat
    @State private var includeTimestamps: Bool = AppSettings.shared.includeTimestamps
    @State private var showModelAlert = false

    /// The transcript panel only appears once there's something to show — otherwise
    /// the window is just the file queue at full width (no empty second pane, and
    /// the drop zone stays centered).
    private var showOutput: Bool {
        transcriptionVM.isRunning || transcriptionVM.isPaused || !transcriptionVM.transcripts.isEmpty
    }

    private var fileQueue: some View {
        FileQueueView()
            .onDrop(of: [.fileURL], isTargeted: nil) { providers in
                fileQueueVM.handleDrop(providers: providers)
            }
    }

    var body: some View {
        Group {
            if showOutput {
                HSplitView {
                    fileQueue
                        .frame(minWidth: 300, idealWidth: 380)
                    TranscriptionOutputView()
                        .frame(minWidth: 280, idealWidth: 380)
                }
            } else {
                fileQueue
            }
        }
            .toolbar {
                ToolbarView(
                    selectedModel: $selectedModel,
                    selectedFormat: $selectedFormat,
                    includeTimestamps: $includeTimestamps,
                    onStartRequested: handleStart
                )
            }
            .fileImporter(
                isPresented: Binding(
                    get: { fileQueueVM.showFilePicker },
                    set: { fileQueueVM.showFilePicker = $0 }
                ),
                allowedContentTypes: [.audio, .movie],
                allowsMultipleSelection: true
            ) { result in
                if case .success(let urls) = result {
                    Task { await fileQueueVM.addFiles(urls: urls) }
                }
            }
            .alert("Model Not Downloaded", isPresented: $showModelAlert) {
                Button("Download Now") {
                    openSettings()
                    Task { await modelManagerVM.download(selectedModel) }
                }
                Button("Cancel", role: .cancel) {}
            } message: {
                Text("The \(selectedModel.displayName) model (\(selectedModel.sizeDescription)) needs to be downloaded before transcribing.")
            }
            .task { await modelManagerVM.refresh() }
            .frame(minWidth: 460, idealWidth: showOutput ? 820 : 600, minHeight: 360, idealHeight: 480)
    }

    private func handleStart() {
        // The MLX backend (mlx-whisper) auto-downloads its HuggingFace weights on
        // first use, so we must NOT require a local GGML download for it. The
        // local-download gate only applies to the GGML (whisper.cpp) backend.
        let backend = AppSettings.shared.transcriptionBackend
        if backend == .swiftWhisper {
            if let modelInfo = modelManagerVM.models.first(where: { $0.type == selectedModel }),
               !modelInfo.isDownloaded {
                showModelAlert = true
                return
            }

            if modelManagerVM.models.isEmpty {
                showModelAlert = true
                return
            }
        }

        transcriptionVM.start(
            files: fileQueueVM.pendingFiles,
            model: selectedModel,
            format: selectedFormat,
            timestamps: includeTimestamps
        )
    }
}
