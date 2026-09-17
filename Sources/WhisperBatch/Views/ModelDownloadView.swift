import SwiftUI
import WhisperBatchCore

struct ModelDownloadView: View {
    @Environment(ModelManagerViewModel.self) private var viewModel
    @State private var modelToDelete: WhisperModelType?

    var body: some View {
        List {
            ForEach(viewModel.models) { model in
                HStack {
                    VStack(alignment: .leading, spacing: 4) {
                        Text(model.type.displayName)
                            .font(.headline)
                        Text(model.type.useCase)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text("\(model.type.sizeDescription) · \(model.type.speedDescription)")
                            .font(.caption2)
                            .foregroundStyle(.tertiary)
                    }

                    Spacer()

                    if model.isDownloaded {
                        HStack(spacing: 10) {
                            Label("Downloaded", systemImage: "checkmark.circle.fill")
                                .font(.caption)
                                .foregroundStyle(.green)

                            Button {
                                modelToDelete = model.type
                            } label: {
                                Image(systemName: "trash")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .buttonStyle(.plain)
                            .help("Remove model")
                        }
                    } else if viewModel.downloadingModel == model.type {
                        HStack(alignment: .center, spacing: 8) {
                            if viewModel.downloadProgress > 0 {
                                ProgressView(value: viewModel.downloadProgress)
                                    .frame(width: 100)
                                Text("\(Int(viewModel.downloadProgress * 100))%")
                                    .font(.caption2)
                                    .monospacedDigit()
                            } else {
                                ProgressView()
                                    .controlSize(.small)
                                Text("Connecting...")
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                            }

                            Button {
                                viewModel.cancelDownload()
                            } label: {
                                Image(systemName: "xmark.circle.fill")
                                    .foregroundStyle(.secondary)
                            }
                            .buttonStyle(.plain)
                            .help("Cancel download")
                        }
                    } else {
                        Button("Download") {
                            Task { await viewModel.download(model.type) }
                        }
                        .disabled(viewModel.downloadingModel != nil)
                    }
                }
                .padding(.vertical, 4)
            }
        }
        .task { await viewModel.refresh() }
        .alert("Remove Model?", isPresented: Binding(
            get: { modelToDelete != nil },
            set: { if !$0 { modelToDelete = nil } }
        )) {
            Button("Remove", role: .destructive) {
                if let model = modelToDelete {
                    Task { await viewModel.delete(model) }
                }
                modelToDelete = nil
            }
            Button("Cancel", role: .cancel) {
                modelToDelete = nil
            }
        } message: {
            if let model = modelToDelete {
                Text("This will delete the \(model.displayName) model from disk. You can re-download it later.")
            }
        }

        if let error = viewModel.errorMessage {
            Text(error)
                .foregroundStyle(.red)
                .font(.caption)
                .padding(.horizontal)
        }
    }
}
