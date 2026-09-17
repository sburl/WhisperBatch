import Foundation
import WhisperBatchCore

public enum CLIOutputSelection: Equatable {
    case single(OutputFormat)
    case all

    var formats: [OutputFormat] {
        switch self {
        case .single(let f): [f]
        case .all: [.txt, .srt, .vtt, .json]
        }
    }
}

public struct CLIOptions: Equatable {
    public let inputs: [String]
    public let model: WhisperModelType
    public let format: CLIOutputSelection
    public let output: String?
    public let language: String?
    public let includeTimestamps: Bool
    public let enhance: Bool
    public let hallucinationFilter: Bool
    public let skipSilence: Bool

    public init(
        inputs: [String],
        model: WhisperModelType,
        format: CLIOutputSelection,
        output: String?,
        language: String?,
        includeTimestamps: Bool,
        enhance: Bool,
        hallucinationFilter: Bool,
        skipSilence: Bool
    ) {
        self.inputs = inputs
        self.model = model
        self.format = format
        self.output = output
        self.language = language
        self.includeTimestamps = includeTimestamps
        self.enhance = enhance
        self.hallucinationFilter = hallucinationFilter
        self.skipSilence = skipSilence
    }

    public static func parse(_ arguments: [String]) throws -> CLIOptions {
        var inputs: [String] = []
        var model: WhisperModelType = .largeV3Turbo
        var format: CLIOutputSelection = .single(.txt)
        var output: String?
        var language: String?
        var includeTimestamps = false
        var enhance = false
        var hallucinationFilter = true
        var skipSilence = false

        var index = 0
        while index < arguments.count {
            let argument = arguments[index]
            switch argument {
            case "--help", "-h":
                throw CLIParseError.helpRequested
            case "--model":
                let value = try value(after: argument, in: arguments, at: &index)
                guard let parsed = WhisperModelType(rawValue: value) else {
                    throw CLIParseError.invalidModel(value)
                }
                model = parsed
            case "--format":
                let value = try value(after: argument, in: arguments, at: &index)
                switch value {
                case "txt":  format = .single(.txt)
                case "srt":  format = .single(.srt)
                case "vtt":  format = .single(.vtt)
                case "json": format = .single(.json)
                case "all", "both": format = .all
                default: throw CLIParseError.invalidFormat(value)
                }
            case "--output":
                output = try value(after: argument, in: arguments, at: &index)
            case "--language":
                language = try value(after: argument, in: arguments, at: &index)
            case "--timestamps":
                includeTimestamps = true
            case "--no-timestamps":
                includeTimestamps = false
            case "--enhance":
                enhance = true
            case "--no-hallucination-filter":
                hallucinationFilter = false
            case "--skip-silence":
                skipSilence = true
            default:
                if argument.hasPrefix("-") {
                    throw CLIParseError.unknownFlag(argument)
                }
                inputs.append(argument)
            }
            index += 1
        }

        guard !inputs.isEmpty else {
            throw CLIParseError.missingInput
        }

        return CLIOptions(
            inputs: inputs,
            model: model,
            format: format,
            output: output,
            language: language,
            includeTimestamps: includeTimestamps,
            enhance: enhance,
            hallucinationFilter: hallucinationFilter,
            skipSilence: skipSilence
        )
    }

    private static func value(after flag: String, in arguments: [String], at index: inout Int) throws -> String {
        let valueIndex = index + 1
        guard valueIndex < arguments.count else {
            throw CLIParseError.missingValue(flag)
        }
        let value = arguments[valueIndex]
        guard !value.hasPrefix("-") else {
            throw CLIParseError.missingValue(flag)
        }
        index = valueIndex
        return value
    }
}

public enum CLIParseError: LocalizedError, Equatable {
    case missingInput
    case missingValue(String)
    case invalidModel(String)
    case invalidFormat(String)
    case unknownFlag(String)
    case helpRequested

    public var errorDescription: String? {
        switch self {
        case .missingInput:
            "Missing input file or directory."
        case .missingValue(let flag):
            "Missing value for \(flag)."
        case .invalidModel(let model):
            "Invalid model '\(model)'. Valid models: \(WhisperModelType.ggmlDownloadable.map(\.rawValue).joined(separator: ", "))."
        case .invalidFormat(let format):
            "Invalid format '\(format)'. Valid formats: txt, srt, vtt, json, all."
        case .unknownFlag(let flag):
            "Unknown flag \(flag)."
        case .helpRequested:
            CLIUsage.text
        }
    }
}

public enum CLIUsage {
    public static let text = """
    Usage: swift run whisperbatch-cli <file-or-dir> [more...] [options]

    Options:
      --model <id>          tiny | small | large-v3-turbo | large-v3   (default: large-v3-turbo)
      --format <fmt>        txt | srt | vtt | json | all               (default: txt)
      --output <path>       output file (single) or directory          (default: alongside input)
      --language <code>     ISO code e.g. en; omit to auto-detect
      --timestamps          include per-segment timestamps in txt output
      --no-timestamps       plain text (default)
      --enhance             opt-in audio enhancement (currently a no-op)
      --no-hallucination-filter   disable the hallucination filter (on by default)
      --skip-silence        skip silent regions (VAD)

    Models download automatically from the WhisperKit CoreML repo on first use.
    """
}
