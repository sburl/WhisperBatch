import SwiftUI
import WhisperBatchCore

struct ToolbarView: ToolbarContent {
    @Environment(FileQueueViewModel.self) private var fileQueueVM
    @Environment(TranscriptionViewModel.self) private var transcriptionVM

    @Binding var selectedModel: WhisperModelType
    @Binding var selectedFormat: OutputFormat
    @Binding var includeTimestamps: Bool
    var onStartRequested: () -> Void

    var body: some ToolbarContent {
        ToolbarItemGroup(placement: .principal) {
            Menu {
                Section("Model") {
                    // Only offer models the active engine can actually run.
                    // MLX-only models (the Metal "Turbo") are excluded unless the
                    // MLX backend is selected — and that backend doesn't exist in
                    // the App Store build, so they never appear there.
                    ForEach(WhisperModelType.allCases.filter {
                        AppSettings.shared.transcriptionBackend == .mlxWhisper || !$0.requiresMLX
                    }) { model in
                        Button {
                            selectedModel = model
                        } label: {
                            let title = "\(model.displayName)  ·  \(model.speedDescription)"
                            if model == selectedModel {
                                Label(title, systemImage: "checkmark")
                            } else {
                                Text(title)
                            }
                        }
                    }
                }
            } label: {
                Label(selectedModel.displayName, systemImage: "cpu")
                    .font(.callout)
            }
            .help("\(selectedModel.displayName): \(selectedModel.useCase)")

            Menu {
                Section("Format") {
                    ForEach(OutputFormat.allCases) { format in
                        Button {
                            selectedFormat = format
                        } label: {
                            if format == selectedFormat {
                                Label(format.displayName, systemImage: "checkmark")
                            } else {
                                Text(format.displayName)
                            }
                        }
                    }
                }
            } label: {
                Label(selectedFormat.displayName, systemImage: "doc.text")
                    .font(.callout)
            }
            .help("Output format")

            Menu {
                Section("Timestamps") {
                    Button {
                        includeTimestamps = true
                    } label: {
                        if includeTimestamps {
                            Label("On", systemImage: "checkmark")
                        } else {
                            Text("On")
                        }
                    }
                    Button {
                        includeTimestamps = false
                    } label: {
                        if !includeTimestamps {
                            Label("Off", systemImage: "checkmark")
                        } else {
                            Text("Off")
                        }
                    }
                }
            } label: {
                Label(includeTimestamps ? "Timestamps" : "No Timestamps", systemImage: "text.quote")
                    .font(.callout)
            }
            .disabled(selectedFormat.forcesTimestamps)
            .help(includeTimestamps ? "Timestamps on" : "Timestamps off")
        }

        ToolbarItemGroup(placement: .primaryAction) {
            if transcriptionVM.canStart {
                Button {
                    onStartRequested()
                } label: {
                    Label("Start", systemImage: "play.fill")
                }
                .disabled(fileQueueVM.pendingFiles.isEmpty)
                .keyboardShortcut("r", modifiers: .command)
                .help("Start transcription (Cmd+R)")
            }

            if transcriptionVM.canPause {
                Button {
                    transcriptionVM.pause()
                } label: {
                    Label("Pause", systemImage: "pause.fill")
                }
                .keyboardShortcut("p", modifiers: .command)
                .help("Pause (Cmd+P)")
            }

            if transcriptionVM.canResume {
                Button {
                    transcriptionVM.resume()
                } label: {
                    Label("Resume", systemImage: "play.fill")
                }
                .keyboardShortcut("p", modifiers: .command)
                .help("Resume (Cmd+P)")
            }

            if transcriptionVM.canStop {
                Button {
                    transcriptionVM.stop()
                } label: {
                    Label("Stop", systemImage: "stop.fill")
                }
                .keyboardShortcut(".", modifiers: .command)
                .help("Stop (Cmd+.)")
            }
        }
    }
}
