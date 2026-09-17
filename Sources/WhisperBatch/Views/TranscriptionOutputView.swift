import SwiftUI
import AppKit
import WhisperBatchCore

struct TranscriptionOutputView: View {
    @Environment(TranscriptionViewModel.self) private var viewModel

    var body: some View {
        Group {
            if viewModel.transcripts.isEmpty && !viewModel.isRunning {
                ContentUnavailableView(
                    "No transcript yet",
                    systemImage: "text.alignleft",
                    description: Text("Run a transcription and the text appears here.")
                )
            } else {
                ScrollView {
                    VStack(alignment: .leading, spacing: 16) {
                        if !viewModel.runSummary.isEmpty {
                            Text(viewModel.runSummary)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                        }

                        ForEach(viewModel.transcripts) { item in
                            VStack(alignment: .leading, spacing: 7) {
                                HStack(spacing: 6) {
                                    Image(systemName: item.failed ? "exclamationmark.triangle.fill" : "text.alignleft")
                                        .font(.caption)
                                        .foregroundStyle(item.failed ? .red : .secondary)
                                    Text(item.filename)
                                        .font(.subheadline.weight(.semibold))
                                        .lineLimit(1)
                                        .truncationMode(.middle)
                                    Spacer()
                                    if !item.failed {
                                        Button {
                                            NSPasteboard.general.clearContents()
                                            NSPasteboard.general.setString(item.text, forType: .string)
                                        } label: {
                                            Image(systemName: "doc.on.doc")
                                        }
                                        .buttonStyle(.borderless)
                                        .foregroundStyle(.secondary)
                                        .help("Copy transcript")
                                    }
                                }
                                Text(item.text)
                                    .font(.body)
                                    .foregroundStyle(item.failed ? .red : .primary)
                                    .textSelection(.enabled)
                                    .fixedSize(horizontal: false, vertical: true)
                            }
                            .padding(14)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(RoundedRectangle(cornerRadius: 10).fill(Color(nsColor: .textBackgroundColor)))
                        }

                        if viewModel.isRunning {
                            HStack(spacing: 8) {
                                ProgressView().controlSize(.small)
                                Text("Transcribing…")
                                    .font(.caption)
                                    .foregroundStyle(.secondary)
                            }
                            .padding(.top, 2)
                        }
                    }
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background(Color(nsColor: .windowBackgroundColor))
    }
}
