import SwiftUI
import WhisperBatchCore

enum SettingsTab: Hashable {
    case general
    case models
}

struct SettingsView: View {
    @Environment(ModelManagerViewModel.self) private var modelManagerVM
    @State private var selectedTab: SettingsTab = .general

    var body: some View {
        TabView(selection: $selectedTab) {
            GeneralSettingsTab()
                .tabItem {
                    Label("General", systemImage: "gear")
                }
                .tag(SettingsTab.general)

            ModelDownloadView()
                .tabItem {
                    Label("Models", systemImage: "arrow.down.circle")
                }
                .tag(SettingsTab.models)
        }
        .frame(width: 500, height: 400)
        .onChange(of: modelManagerVM.downloadingModel) { _, newValue in
            if newValue != nil {
                selectedTab = .models
            }
        }
        .onAppear {
            if modelManagerVM.downloadingModel != nil {
                selectedTab = .models
            }
        }
    }
}

private struct GeneralSettingsTab: View {
    @State private var settings = AppSettings.shared
    @State private var showFolderPicker = false

    var body: some View {
        Form {
            // The MLX/Metal engine shells out to a user-installed Python
            // (`mlx-whisper`), which a sandboxed App Store build cannot launch.
            // So it's compiled out of the App Store build entirely — the app
            // ships as a single offline whisper.cpp engine.
            #if !APP_STORE
            Section("Transcription Backend") {
                Picker("Engine", selection: Binding(
                    get: { settings.transcriptionBackend },
                    set: { settings.transcriptionBackend = $0 }
                )) {
                    ForEach(TranscriptionBackend.allCases) { backend in
                        Text(backend.displayName).tag(backend)
                    }
                }
                if settings.transcriptionBackend == .mlxWhisper {
                    Text("Requires: pip install mlx-whisper")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

            }
            #endif

            Section {
                Picker("Model", selection: Binding(
                    get: { settings.defaultModel },
                    set: { settings.defaultModel = $0 }
                )) {
                    // Only show models compatible with the active backend.
                    // MLX-only models (e.g. Turbo) are hidden when swiftWhisper
                    // is selected so users cannot reach an invalid combination.
                    ForEach(WhisperModelType.allCases.filter { model in
                        settings.transcriptionBackend == .mlxWhisper || !model.requiresMLX
                    }) { model in
                        Text(model.displayName).tag(model)
                    }
                }

                Picker("Format", selection: Binding(
                    get: { settings.defaultOutputFormat },
                    set: { settings.defaultOutputFormat = $0 }
                )) {
                    ForEach(OutputFormat.allCases) { format in
                        Text(format.displayName).tag(format)
                    }
                }

                Toggle("Include Timestamps", isOn: Binding(
                    get: { settings.includeTimestamps },
                    set: { settings.includeTimestamps = $0 }
                ))
                .disabled(settings.defaultOutputFormat.forcesTimestamps)
            } header: {
                Text("Default Output")
            } footer: {
                VStack(alignment: .leading, spacing: 4) {
                    Text("\(settings.defaultModel.displayName): \(settings.defaultModel.useCase) · \(settings.defaultModel.sizeDescription), \(settings.defaultModel.speedDescription).")
                    Text(settings.defaultOutputFormat.formatDescription
                        + (settings.defaultOutputFormat.forcesTimestamps
                           ? " Timestamps are always included for this format." : ""))
                }
                .font(.caption)
                .foregroundStyle(.secondary)
            }

            Section("Long Recordings") {
                Toggle("Skip Silence", isOn: Binding(
                    get: { settings.silenceSkippingEnabled },
                    set: { settings.silenceSkippingEnabled = $0 }
                ))
            }

            Section {
                Toggle("Enhance Audio", isOn: Binding(
                    get: { settings.enhanceAudio },
                    set: { settings.enhanceAudio = $0 }
                ))

                Toggle("Filter Hallucinations", isOn: Binding(
                    get: { settings.hallucinationFilterEnabled },
                    set: { settings.hallucinationFilterEnabled = $0 }
                ))
            } header: {
                Text("Audio Quality")
            } footer: {
                Text("Enhancement applies speech band-pass and denoise processing. Hallucination filtering removes noise-only tokens and repeated segment loops after transcription.")
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }

            Section("Save Location") {
                Picker("Save To", selection: Binding(
                    get: { settings.saveNextToSource },
                    set: { newValue in
                        if newValue {
                            settings.customOutputDirectory = nil
                        } else {
                            showFolderPicker = true
                        }
                    }
                )) {
                    Text("Next to Source File").tag(true)
                    Text("Custom Folder…").tag(false)
                }

                if let dir = settings.customOutputDirectory {
                    HStack {
                        Image(systemName: "folder.fill")
                            .foregroundStyle(.secondary)
                        Text(dir.path(percentEncoded: false))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                            .truncationMode(.middle)
                        Spacer()
                        Button("Change…") {
                            showFolderPicker = true
                        }
                        .font(.caption)
                    }
                }
            }
        }
        .formStyle(.grouped)
        .padding()
        // When the user switches away from MLX, reset the model if it requires
        // MLX so the saved default stays in a valid state.
        .onChange(of: settings.transcriptionBackend) { _, newBackend in
            if newBackend != .mlxWhisper && settings.defaultModel.requiresMLX {
                settings.defaultModel = .largeV3Turbo
            }
        }
        .fileImporter(
            isPresented: $showFolderPicker,
            allowedContentTypes: [.folder],
            allowsMultipleSelection: false
        ) { result in
            if case .success(let urls) = result, let url = urls.first {
                if url.startAccessingSecurityScopedResource() {
                    settings.customOutputDirectory = url
                    url.stopAccessingSecurityScopedResource()
                }
            } else if settings.customOutputDirectory == nil {
                // User cancelled and there was no previous folder — stay on "Next to Source"
            }
        }
    }
}
