import Foundation
import WhisperBatchCore

@main
struct WhisperBatchCLI {
    static func main() async {
        do {
            let options = try CLIOptions.parse(Array(CommandLine.arguments.dropFirst()))
            try await run(options)
        } catch CLIParseError.helpRequested {
            print(CLIUsage.text)
        } catch {
            fputs("whisperbatch-cli: \(error.localizedDescription)\n", stderr)
            exit(1)
        }
    }

    private static func run(_ options: CLIOptions) async throws {
        guard !options.model.requiresMLX else {
            throw CLIError.unsupportedModel(options.model)
        }

        let inputURLs = try expandInputs(options.inputs)
        guard !inputURLs.isEmpty else {
            throw CLIError.noSupportedInputs
        }

        let outputBase = options.output.map { URL(filePath: $0) }
        let engine = TranscriptionEngine()
        // WhisperKit downloads the CoreML model on first use; this can take a
        // while the first time for a given model.
        if !(await ModelManager.shared.isModelDownloaded(options.model)) {
            fputs("whisperbatch-cli: \(options.model.displayName) not cached — downloading from WhisperKit…\n", stderr)
        }
        try await engine.loadModel(options.model, language: options.language)

        var failures = 0
        for inputURL in inputURLs {
            do {
                _ = try await FileValidator.validate(url: inputURL)
                let segments = try await engine.transcribe(
                    audioURL: inputURL,
                    enhanceAudio: options.enhance,
                    hallucinationFilterEnabled: options.hallucinationFilter,
                    silenceSkippingEnabled: options.skipSilence
                )
                let outputURLs = try outputDestinations(
                    for: inputURL,
                    formats: options.format.formats,
                    outputBase: outputBase,
                    totalInputCount: inputURLs.count
                )

                for (format, outputURL) in outputURLs {
                    let text = OutputRenderer.renderOutputText(
                        segments,
                        format: format,
                        includeTimestamps: options.includeTimestamps
                    )
                    try FileManager.default.createDirectory(
                        at: outputURL.deletingLastPathComponent(),
                        withIntermediateDirectories: true
                    )
                    try text.write(to: outputURL, atomically: true, encoding: .utf8)
                    print(outputURL.path)
                }
            } catch {
                failures += 1
                fputs("whisperbatch-cli: \(inputURL.path): \(error.localizedDescription)\n", stderr)
            }
        }

        if failures > 0 {
            throw CLIError.fileFailures(failures)
        }
    }

    private static func expandInputs(_ inputs: [String]) throws -> [URL] {
        var results: [URL] = []
        for input in inputs {
            let url = URL(filePath: input)
            var isDirectory: ObjCBool = false
            guard FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory) else {
                throw CLIError.inputMissing(url)
            }

            if isDirectory.boolValue {
                let contents = try FileManager.default.contentsOfDirectory(
                    at: url,
                    includingPropertiesForKeys: [.isRegularFileKey],
                    options: [.skipsHiddenFiles]
                )
                results.append(contentsOf: contents.filter { AudioFile.isSupported($0) }.sorted { $0.path < $1.path })
            } else {
                results.append(url)
            }
        }
        return results
    }

    private static func outputDestinations(
        for inputURL: URL,
        formats: [OutputFormat],
        outputBase: URL?,
        totalInputCount: Int
    ) throws -> [(OutputFormat, URL)] {
        if let outputBase, formats.count == 1, totalInputCount == 1, !isDirectory(outputBase) {
            return [(formats[0], outputBase)]
        }

        let directory = outputDirectory(for: inputURL, outputBase: outputBase)
        let stem = inputURL.deletingPathExtension().lastPathComponent
        return formats.map { format in
            (format, OutputRenderer.buildOutputFilePath(directory: directory, stem: stem, format: format))
        }
    }

    private static func outputDirectory(for inputURL: URL, outputBase: URL?) -> URL {
        guard let outputBase else {
            return inputURL.deletingLastPathComponent()
        }
        if isDirectory(outputBase) || outputBase.pathExtension.isEmpty {
            return outputBase
        }
        return outputBase.deletingLastPathComponent()
    }

    private static func isDirectory(_ url: URL) -> Bool {
        var isDirectory: ObjCBool = false
        return FileManager.default.fileExists(atPath: url.path, isDirectory: &isDirectory) && isDirectory.boolValue
    }
}

enum CLIError: LocalizedError {
    case inputMissing(URL)
    case noSupportedInputs
    case unsupportedModel(WhisperModelType)
    case modelMissing(WhisperModelType, URL)
    case fileFailures(Int)

    var errorDescription: String? {
        switch self {
        case .inputMissing(let url):
            "Input not found: \(url.path)"
        case .noSupportedInputs:
            "No supported audio/video files found."
        case .unsupportedModel(let model):
            "\(model.displayName) requires the MLX backend, which is not supported by this headless SwiftWhisper CLI yet."
        case .modelMissing(let model, let path):
            "Model \(model.rawValue) is not downloaded. Expected GGML model at \(path.path). Download it in the app first."
        case .fileFailures(let count):
            "\(count) file(s) failed."
        }
    }
}
